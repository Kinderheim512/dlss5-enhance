"""Follow one submitted prompt: WebSocket first, /history polling as the net."""

from __future__ import annotations

import contextlib
import json
import queue
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from .comfy_client import HISTORY_ERROR, HISTORY_SUCCESS, ComfyClient, history_outcome
from .i18n import tr

try:
    import websocket
except ImportError:  # pragma: no cover - the fallback path is exercised by design
    websocket = None  # type: ignore[assignment]

STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_TIMEOUT = "timeout"
STATUS_CRASHED = "crashed"
STATUS_CANCELLED = "cancelled"


@dataclass
class JobOutcome:
    status: str
    error: str = ""
    cached_nodes: set[str] = field(default_factory=set)
    frames_done: int = 0
    frames_total: int = 0
    ws_connected: bool = False
    ws_failed: bool = False

    @property
    def ok(self) -> bool:
        return self.status == STATUS_SUCCESS


class JobMonitor:
    """One prompt at a time: no queue is ever fed with a second job."""

    def __init__(
        self,
        client: ComfyClient,
        ws_url: str,
        prompt_id: str,
        client_id: str,
        target_node_id: str | None,
        logger,
    ) -> None:
        self.client = client
        self.ws_url = ws_url
        self.prompt_id = prompt_id
        self.client_id = client_id
        self.target_node_id = str(target_node_id) if target_node_id is not None else None
        self.logger = logger
        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._app: Any | None = None
        self._thread: threading.Thread | None = None
        self._finished = False

    def run(
        self,
        *,
        timeout: float,
        server_alive: Callable[[], bool],
        interrupt: Callable[[], bool],
        on_tick: Callable[[float, int, int, bool], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        poll_interval: float = 0.5,
        history_interval: float = 2.0,
    ) -> JobOutcome:
        outcome = JobOutcome(status=STATUS_SUCCESS)
        self._start_websocket()

        started = time.monotonic()
        next_history = started + history_interval
        finished = False

        try:
            while not finished:
                if self._drain(outcome):
                    finished = True
                    break
                if outcome.status == STATUS_ERROR:
                    finished = True
                    break

                elapsed = time.monotonic() - started
                if on_tick is not None:
                    on_tick(
                        elapsed,
                        outcome.frames_done,
                        outcome.frames_total,
                        bool(outcome.cached_nodes),
                    )

                if not server_alive():
                    outcome.status = STATUS_CRASHED
                    outcome.error = tr("r.server_gone")
                    finished = True
                    break

                if cancelled is not None and cancelled():
                    self.logger.warning(tr("r.cancelled", prompt=self.prompt_id))
                    interrupt()
                    outcome.status = STATUS_CANCELLED
                    outcome.error = tr("t.status.cancelled")
                    finished = True
                    break

                if elapsed > timeout:
                    self.logger.error(
                        tr("r.timeout", seconds=timeout, prompt=self.prompt_id)
                    )
                    interrupt()
                    outcome.status = STATUS_TIMEOUT
                    outcome.error = tr("r.timeout_error", seconds=timeout)
                    finished = True
                    break

                now = time.monotonic()
                if now >= next_history:
                    next_history = now + history_interval
                    status, message = self._poll_history()
                    if status == HISTORY_SUCCESS:
                        finished = True
                    elif status == HISTORY_ERROR:
                        outcome.status = STATUS_ERROR
                        outcome.error = message
                        finished = True

                time.sleep(poll_interval)
        finally:
            self._stop_websocket()
        return outcome

    def _poll_history(self) -> tuple[str, str]:
        try:
            entry = self.client.history(self.prompt_id)
        except Exception as exc:
            self.logger.debug("Polling /history failed: %s", exc)
            return "", ""
        if entry is None:
            return "", ""
        return history_outcome(entry)

    def _drain(self, outcome: JobOutcome) -> bool:
        while True:
            try:
                kind, payload = self._events.get_nowait()
            except queue.Empty:
                return self._finished
            if kind == "open":
                outcome.ws_connected = True
                self.logger.debug(tr("r.ws_connected"))
            elif kind == "error":
                outcome.ws_failed = True
                self.logger.debug(tr("r.ws_error", error=payload))
            elif kind == "message":
                self._handle_message(payload, outcome)

    def _handle_message(self, payload: Mapping[str, Any], outcome: JobOutcome) -> None:
        event = payload.get("type")
        data = payload.get("data") or {}
        prompt_id = data.get("prompt_id")
        if prompt_id and str(prompt_id) != self.prompt_id and event != "status":
            return

        if event == "execution_cached":
            nodes = {str(node) for node in data.get("nodes") or []}
            outcome.cached_nodes |= nodes
            if self.target_node_id and self.target_node_id in nodes:
                self.logger.info(tr("r.cache_node", node=self.target_node_id))
        elif event == "progress":
            outcome.frames_done = int(data.get("value") or 0)
            outcome.frames_total = int(data.get("max") or 0)
        elif event == "executing":
            if data.get("node") is None:
                outcome.status = STATUS_SUCCESS
                self._finished = True
        elif event in ("execution_error", "execution_interrupted"):
            outcome.status = STATUS_ERROR if event == "execution_error" else STATUS_TIMEOUT
            if event == "execution_error":
                exception = data.get("exception_type") or "Exception"
                message = data.get("exception_message") or ""
                node_type = data.get("node_type") or ""
                where = f" ({node_type})" if node_type else ""
                outcome.error = f"{exception}{where}: {message}".strip()
            else:
                outcome.error = "interrompu"
            self._finished = True

    def _start_websocket(self) -> None:
        if websocket is None:
            self.logger.info(tr("r.ws_missing"))
            return
        url = f"{self.ws_url}?clientId={self.client_id}"
        self._app = websocket.WebSocketApp(
            url,
            on_open=lambda _app: self._events.put(("open", None)),
            on_message=lambda _app, message: self._events.put(("message", _decode(message))),
            on_error=lambda _app, error: self._events.put(("error", str(error))),
            on_close=lambda _app, code, reason: self._events.put(("error", f"closed ({code})")),
        )
        self._thread = threading.Thread(target=self._run_forever, name="dlss5-ws", daemon=True)
        self._thread.start()

    def _run_forever(self) -> None:
        try:
            self._app.run_forever(ping_interval=0)
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _stop_websocket(self) -> None:
        if self._app is None:
            return
        with contextlib.suppress(Exception):
            self._app.close()
        if self._thread is not None:
            self._thread.join(timeout=3.0)


def _decode(message: Any) -> Mapping[str, Any]:
    if isinstance(message, (bytes, bytearray)):
        try:
            message = message.decode("utf-8", errors="replace")
        except Exception:
            return {}
    try:
        payload = json.loads(message)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def wait_for_completion(
    client: ComfyClient,
    prompt_id: str,
    timeout: float = 60.0,
    interval: float = 0.5,
) -> bool:
    """Wait until /history carries a terminal entry for *prompt_id*."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            entry = client.history(prompt_id)
        except Exception:
            entry = None
        if entry is not None:
            status, _ = history_outcome(entry)
            if status in (HISTORY_SUCCESS, HISTORY_ERROR):
                return True
        time.sleep(interval)
    return False
