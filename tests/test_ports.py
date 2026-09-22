"""Console hiding and the ComfyUI port fallback."""

import logging
import tempfile
import unittest
from pathlib import Path

from dlss5_enhance import spawn
from dlss5_enhance.comfy_client import ComfyClient
from dlss5_enhance.comfy_server import ComfyServer, is_tunnel_process
from dlss5_enhance.config import load_config
from dlss5_enhance.errors import ServerError

LOGGER = logging.getLogger("dlss5-tests")
LOGGER.addHandler(logging.NullHandler())
LOGGER.propagate = False


class SpawnTests(unittest.TestCase):
    def test_creation_flags_hide_the_window(self):
        options = spawn.hidden_kwargs()
        self.assertEqual(options["creationflags"], spawn.CREATE_NO_WINDOW)

    def test_startup_info_asks_for_a_hidden_window(self):
        options = spawn.hidden_kwargs()
        if "startupinfo" not in options:
            self.skipTest("no STARTUPINFO on this platform")
        info = options["startupinfo"]
        self.assertTrue(info.dwFlags & spawn.STARTF_USESHOWWINDOW)
        self.assertEqual(info.wShowWindow, spawn.SW_HIDE)

    def test_run_hidden_keeps_the_output(self):
        result = spawn.run_hidden(["cmd", "/c", "echo hello"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("hello", result.stdout)


def make_server(port: int = 8188, fallback=(8189, 8199)) -> ComfyServer:
    with tempfile.TemporaryDirectory() as tmp:
        config = load_config(
            path=Path(tmp) / "absent.yaml",
            base_dir=Path(tmp),
            overrides={"comfy": {"port": port, "port_fallback": list(fallback)}},
        )
    return ComfyServer(config.comfy, ComfyClient(config.comfy.base_url), LOGGER)


class FakeNetwork:
    """Answers, listeners and node availability, per port."""

    def __init__(self, server: ComfyServer) -> None:
        self.server = server
        self.answering: set[int] = set()
        self.listeners: dict[int, int] = {}
        self.names: dict[int, str] = {}
        self.with_node: set[int] = set()
        server.responds = self.responds
        server.listener_pid = self.listener_pid
        server.process_name = self.process_name
        server.has_dlss5_node = self.has_dlss5_node
        server.desktop_app = lambda: None

    def responds(self, port: int) -> bool:
        return port in self.answering

    def listener_pid(self, port: int | None = None) -> int | None:
        return self.listeners.get(port if port is not None else self.server.port)

    def process_name(self, pid: int | None) -> str | None:
        return self.names.get(pid) if pid else None

    def has_dlss5_node(self, port: int) -> bool:
        return port in self.with_node


class ReuseTests(unittest.TestCase):
    def test_tunnel_on_the_configured_port_is_never_used(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8188}
        net.listeners = {8188: 100}
        net.names = {100: "ssh.exe"}
        net.with_node = {8188}
        self.assertTrue(is_tunnel_process("ssh.exe"))
        self.assertFalse(server._reuse_configured())
        with self.assertRaises(ServerError):
            server.ensure(autostart=False)

    def test_local_comfyui_with_the_node_is_reused(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8188}
        net.listeners = {8188: 200}
        net.names = {200: "python.exe"}
        net.with_node = {8188}
        handle = server.ensure(autostart=False)
        self.assertFalse(handle.started_by_us)
        self.assertEqual(server.port, 8188)
        self.assertEqual(server.base_url, "http://127.0.0.1:8188")

    def test_local_comfyui_without_the_node_is_not_reused(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8188}
        net.listeners = {8188: 200}
        net.names = {200: "python.exe"}
        net.with_node = set()
        self.assertFalse(server._reuse_configured())

    def test_another_port_with_the_node_is_found(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8199}
        net.with_node = {8199}
        self.assertEqual(server._find_local_with_node(), 8199)

    def test_another_port_without_the_node_is_ignored(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8199}
        net.with_node = set()
        self.assertIsNone(server._find_local_with_node())

    def test_reuse_switches_the_client_to_the_found_port(self):
        server = make_server()
        net = FakeNetwork(server)
        net.answering = {8199}
        net.with_node = {8199}
        handle = server.ensure(autostart=False)
        self.assertFalse(handle.started_by_us)
        self.assertEqual(server.port, 8199)
        self.assertEqual(server.client.base_url, "http://127.0.0.1:8199")
        self.assertEqual(server.ws_url, "ws://127.0.0.1:8199/ws")


class FreePortTests(unittest.TestCase):
    def test_first_free_port_skips_the_occupied_configured_one(self):
        server = make_server()
        net = FakeNetwork(server)
        net.listeners = {8188: 1}
        self.assertEqual(server._first_free_port(), 8189)

    def test_first_free_port_prefers_the_configured_one(self):
        server = make_server()
        FakeNetwork(server)
        self.assertEqual(server._first_free_port(), 8188)

    def test_no_free_port(self):
        server = make_server()
        net = FakeNetwork(server)
        net.listeners = {8188: 1, 8189: 2, 8199: 3}
        net.answering = {8199}
        self.assertIsNone(server._first_free_port())

    def test_fallback_list_is_deduplicated(self):
        server = make_server(port=8189, fallback=(8189, 8199))
        self.assertEqual(server.fallback_ports(), [8189, 8199])

    def test_occupied_port_answers_but_is_not_a_comfyui(self):
        server = make_server()
        net = FakeNetwork(server)
        net.listeners = {8188: 42}
        net.names = {42: "someapp.exe"}
        net.answering = set()
        with self.assertRaises(ServerError):
            server.ensure(autostart=False)
        self.assertEqual(server._first_free_port(), 8189)


if __name__ == "__main__":
    unittest.main()
