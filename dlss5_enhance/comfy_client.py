"""Thin HTTP client for the ComfyUI API (system_stats, prompt, history, interrupt)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests

from .errors import ComfyError
from .i18n import tr

HISTORY_SUCCESS = "success"
HISTORY_ERROR = "error"
HISTORY_RUNNING = "running"


class ComfyClient:
    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def system_stats(self) -> dict[str, Any]:
        """GET /system_stats; raises ComfyError when the server does not answer."""
        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=self.timeout)
        except requests.RequestException as exc:
            raise ComfyError(tr("c.unreachable", url=self.base_url, error=exc)) from exc
        if response.status_code != 200:
            raise ComfyError(tr("c.stats_http", status=response.status_code))
        try:
            return response.json()
        except ValueError as exc:
            raise ComfyError(tr("c.stats_not_json")) from exc

    def is_alive(self) -> bool:
        try:
            self.system_stats()
        except ComfyError:
            return False
        return True

    def object_info(self, class_type: str) -> dict[str, Any] | None:
        try:
            response = requests.get(
                f"{self.base_url}/object_info/{class_type}", timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ComfyError(f"{self.base_url} injoignable : {exc}") from exc
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, Mapping):
            return None
        entry = payload.get(class_type)
        return dict(entry) if isinstance(entry, Mapping) else None

    def submit(self, prompt: Mapping[str, Any], client_id: str) -> str:
        """POST /prompt and return the prompt_id."""
        payload = {"prompt": prompt, "client_id": client_id}
        try:
            response = requests.post(f"{self.base_url}/prompt", json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise ComfyError(tr("c.submit_failed", url=self.base_url, error=exc)) from exc

        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code != 200:
            raise ComfyError(
                _describe_error(data) or tr("c.prompt_http", status=response.status_code)
            )

        node_errors = data.get("node_errors") or {}
        if node_errors:
            raise ComfyError(_describe_node_errors(node_errors))
        error = data.get("error")
        if error:
            raise ComfyError(_describe_error(data))
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyError(tr("c.prompt_no_id"))
        return str(prompt_id)

    def history(self, prompt_id: str) -> dict[str, Any] | None:
        """GET /history/{prompt_id}; None while the entry does not exist yet."""
        try:
            response = requests.get(
                f"{self.base_url}/history/{prompt_id}", timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise ComfyError(f"{self.base_url} injoignable : {exc}") from exc
        if response.status_code != 200:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, Mapping):
            return None
        entry = payload.get(prompt_id)
        return dict(entry) if isinstance(entry, Mapping) else None

    def queue_state(self) -> dict[str, Any]:
        try:
            response = requests.get(f"{self.base_url}/queue", timeout=self.timeout)
        except requests.RequestException as exc:
            raise ComfyError(f"{self.base_url} injoignable : {exc}") from exc
        if response.status_code != 200:
            return {}
        try:
            payload = response.json()
        except ValueError:
            return {}
        return dict(payload) if isinstance(payload, Mapping) else {}

    def interrupt(self) -> bool:
        """POST /interrupt: ask ComfyUI to stop the running prompt."""
        try:
            response = requests.post(f"{self.base_url}/interrupt", timeout=self.timeout)
        except requests.RequestException:
            return False
        return response.status_code == 200


def _describe_error(data: Mapping[str, Any]) -> str:
    error = data.get("error")
    if isinstance(error, Mapping):
        message = error.get("message") or error.get("details")
        if message:
            return str(message)
    if isinstance(error, str):
        return error
    return ""


def _describe_node_errors(node_errors: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for node_id, payload in node_errors.items():
        errors = (payload or {}).get("errors") or []
        for item in errors:
            message = item.get("message") or item.get("details") or tr("c.invalid_input")
            parts.append(tr("c.node_error", node=node_id, message=message))
    if not parts:
        return tr("c.rejected_plain")
    return tr("c.rejected", details="; ".join(parts))


def history_outcome(entry: Mapping[str, Any]) -> tuple[str, str]:
    """Classify a /history entry as success, error (with reason) or running."""
    status = entry.get("status") or {}
    status_str = str(status.get("status_str") or "").lower()
    if status_str == HISTORY_ERROR:
        return HISTORY_ERROR, _first_execution_error(status)
    if status_str == HISTORY_SUCCESS:
        return HISTORY_SUCCESS, ""
    if status.get("completed") is True:
        return HISTORY_SUCCESS, ""
    if status.get("completed") is False and status_str == "":
        return HISTORY_RUNNING, ""
    return HISTORY_RUNNING, ""


def _first_execution_error(status: Mapping[str, Any]) -> str:
    for kind, payload in status.get("messages") or []:
        if kind != "execution_error" or not isinstance(payload, Mapping):
            continue
        exception_type = payload.get("exception_type") or "Exception"
        message = payload.get("exception_message") or ""
        node_type = payload.get("node_type") or ""
        where = f" ({node_type})" if node_type else ""
        return f"{exception_type}{where}: {message}".strip()
    return tr("c.execution_error")
