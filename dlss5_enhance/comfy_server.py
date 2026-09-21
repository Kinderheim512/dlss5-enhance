"""ComfyUI server lifecycle: detect, start, wait for readiness, stop, restart."""

from __future__ import annotations

import contextlib
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import IO

from .comfy_client import ComfyClient
from .config import ComfyConfig
from .errors import ServerError
from .i18n import tr

CREATE_NO_WINDOW = 0x08000000

_NETSTAT_LINE = re.compile(
    r"^\s*TCP\s+(?P<local>\S+):(?P<port>\d+)\s+\S+\s+(?P<state>\S+)\s+(?P<pid>\d+)\s*$"
)
_DESKTOP_HINTS = ("comfyui", "comfyui-electron", "@comfyorgcomfyui-electron")
_TUNNEL_HINTS = ("ssh.exe", "sshd.exe", "plink.exe")


def is_tunnel_process(name: str | None) -> bool:
    """True for an SSH forwarder holding the port (a remote ComfyUI, not ours)."""
    if not name:
        return False
    lowered = name.lower()
    return any(hint in lowered for hint in _TUNNEL_HINTS)


def _parse_listener_pid(netstat_output: str, port: int) -> int | None:
    """PID actually LISTENING on *port*.

    TIME_WAIT rows carry the peer's port in the local column and a PID of 0, so
    only a LISTEN row counts — otherwise a closed server looks like a squatter.
    """
    for line in netstat_output.splitlines():
        match = _NETSTAT_LINE.match(line)
        if not match or int(match.group("port")) != port:
            continue
        if match.group("state").upper().startswith("LISTEN"):
            return int(match.group("pid"))
    return None


@dataclass
class ServerHandle:
    process: subprocess.Popen | None = None
    started_by_us: bool = False
    log_path: Path | None = None
    log_stream: IO[str] | None = field(default=None, repr=False)

    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None


class ComfyServer:
    def __init__(self, cfg: ComfyConfig, client: ComfyClient, logger) -> None:
        self.cfg = cfg
        self.client = client
        self.logger = logger
        self._handle = ServerHandle()
        self._last_http_check = 0.0
        self._http_failures = 0

    def listener_pid(self) -> int | None:
        """PID holding the ComfyUI port, from netstat."""
        try:
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return _parse_listener_pid(result.stdout, self.cfg.port)

    def process_name(self, pid: int | None) -> str | None:
        if not pid:
            return None
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        first = (result.stdout or "").splitlines()
        if not first or not first[0].startswith('"'):
            return None
        return first[0].split('","')[0].strip('"') or None

    def desktop_app(self) -> str | None:
        """Name of a running ComfyUI Desktop / Electron process, if any."""
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        for line in (result.stdout or "").splitlines():
            if not line.startswith('"'):
                continue
            name = line.split('","')[0].strip('"')
            lowered = name.lower()
            if any(hint in lowered for hint in _DESKTOP_HINTS):
                return name
        return None

    def stray_workers(self) -> list[str]:
        """Leftover DLSS5 native workers, which would keep the GPU busy."""
        try:
            result = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        found: list[str] = []
        for line in (result.stdout or "").splitlines():
            if not line.startswith('"'):
                continue
            fields = line.split('","')
            name = fields[0].strip('"')
            if "nvngx" in name.lower():
                pid = fields[1].strip('"') if len(fields) > 1 else "?"
                found.append(f"{name} (PID {pid})")
        return found

    def ensure(self, autostart: bool) -> ServerHandle:
        """Return a usable server, starting one when needed."""
        if self.client.is_alive():
            pid = self.listener_pid()
            name = self.process_name(pid)
            if is_tunnel_process(name):
                raise ServerError(
                    tr(
                        "v.tunnel_detected",
                        port=self.cfg.port,
                        name=name,
                        pid=pid,
                    )
                )
            owner = f"{name} (PID {pid})" if name else f"PID {pid}"
            self.logger.warning(
                tr("v.reuse", url=self.cfg.base_url, owner=owner)
            )
            desktop = self.desktop_app()
            if desktop:
                self.logger.warning(tr("v.desktop_shared", name=desktop))
            return ServerHandle(process=None, started_by_us=False, log_path=self._latest_log())

        pid = self.listener_pid()
        if pid is not None:
            name = self.process_name(pid)
            raise ServerError(
                tr(
                    "v.port_busy",
                    port=self.cfg.port,
                    name=name or tr("v.other_process"),
                    pid=pid,
                )
            )

        if not autostart:
            raise ServerError(tr("v.no_autostart", url=self.cfg.base_url))

        self._validate_launch()
        process, log_path, log_stream = self.start()
        self._handle = ServerHandle(
            process=process, started_by_us=True, log_path=log_path, log_stream=log_stream
        )
        if not self.wait_ready(self.cfg.startup_timeout):
            died = self._handle.process is not None and self._handle.process.poll() is not None
            tail = "\n".join(self.tail_log(20))
            self.stop(self._handle)
            if died:
                message = tr("v.start_died", url=self.cfg.base_url)
            else:
                message = tr(
                    "v.start_timeout",
                    url=self.cfg.base_url,
                    seconds=self.cfg.startup_timeout,
                )
            raise ServerError(f"{message}\n{tail}")
        self.logger.info(tr("v.ready", url=self.cfg.base_url, pid=process.pid))
        return self._handle

    def _validate_launch(self) -> None:
        if not self.cfg.root.is_dir():
            raise ServerError(tr("v.root_missing", path=self.cfg.root))
        if not self.cfg.python.is_file():
            raise ServerError(tr("v.python_missing", path=self.cfg.python))
        module = self.cfg.root / self.cfg.server_module
        if not module.is_file():
            raise ServerError(tr("v.module_missing", path=module))

    def start(self) -> tuple[subprocess.Popen, Path, IO[str]]:
        log_dir = self.cfg.server_log_dir or (self.cfg.root / "logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"comfyui-server-{datetime.now():%Y%m%d}.log"
        stream = open(log_path, "a", encoding="utf-8", errors="replace")
        stream.write(f"\n=== dlss5-enhance: start {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
        stream.flush()
        command = self.cfg.server_command()
        if self.cfg.extra_model_paths_config and not self.cfg.extra_model_paths_config.is_file():
            self.logger.warning(
                tr("v.extra_paths_missing", path=self.cfg.extra_model_paths_config)
            )
            command = self._without_option(command, "--extra-model-paths-config")
        self.logger.info(tr("v.starting", command=" ".join(command)))
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        try:
            process = subprocess.Popen(
                command,
                cwd=str(self.cfg.root),
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            stream.close()
            raise ServerError(tr("v.start_failed", error=exc)) from exc
        return process, log_path, stream

    @staticmethod
    def _without_option(command: list[str], option: str) -> list[str]:
        if option not in command:
            return command
        index = command.index(option)
        return command[:index] + command[index + 2 :]

    def wait_ready(self, timeout: float, interval: float = 0.5) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._handle.process is not None and not self._handle.alive():
                return False
            if self.client.is_alive():
                return True
            time.sleep(interval)
        return False

    def is_process_alive(self) -> bool:
        """False when the launched process died or the API stopped answering.

        ComfyUI's main process spawns the HTTP server as a child, so watching the
        Popen alone is not enough: the endpoint is polled too (throttled, and two
        consecutive failures are required so a hiccup is not read as a crash).
        """
        if self._handle.process is not None and self._handle.process.poll() is not None:
            return False
        now = time.monotonic()
        if now - self._last_http_check < 2.0:
            return True
        self._last_http_check = now
        try:
            self.client.system_stats()
        except Exception:
            self._http_failures += 1
            return self._http_failures < 2
        self._http_failures = 0
        return True

    def wait_queue_empty(self, timeout: float = 30.0, interval: float = 0.5) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.is_process_alive():
                return False
            try:
                state = self.client.queue_state()
            except Exception:
                return False
            running = state.get("queue_running") or []
            pending = state.get("queue_pending") or []
            if not running and not pending:
                return True
            time.sleep(interval)
        return False

    def stop(self, handle: ServerHandle | None = None) -> None:
        handle = handle or self._handle
        if handle.process is not None and handle.process.poll() is None:
            handle.process.terminate()
            try:
                handle.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                handle.process.kill()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    handle.process.wait(timeout=10)
        if handle.log_stream is not None:
            with contextlib.suppress(OSError):
                handle.log_stream.close()
            handle.log_stream = None
        if handle.started_by_us:
            self.logger.info(tr("v.stopped"))
        if handle is self._handle:
            self._handle = ServerHandle()

    def restart(self, autostart: bool = True) -> ServerHandle:
        self.stop()
        time.sleep(1.0)
        return self.ensure(autostart)

    def tail_log(self, lines: int = 30) -> list[str]:
        path = self._handle.log_path or self._latest_log()
        if path is None or not path.is_file():
            return []
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        return content[-lines:]

    def _latest_log(self) -> Path | None:
        log_dir = self.cfg.server_log_dir
        if log_dir is None or not log_dir.is_dir():
            return None
        candidates = sorted(log_dir.glob("comfyui-server-*.log"))
        return candidates[-1] if candidates else None
