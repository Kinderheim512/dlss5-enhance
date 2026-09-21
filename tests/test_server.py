import unittest

from dlss5_enhance.comfy_server import _parse_listener_pid, is_tunnel_process

NETSTAT = """Connexions actives

  Proto  Adresse locale         Adresse distante       Etat           PID
  TCP    127.0.0.1:4105         127.0.0.1:8188         TIME_WAIT       0
  TCP    127.0.0.1:8188         0.0.0.0:0              LISTENING       12000
  TCP    127.0.0.1:8189         0.0.0.0:0              LISTENING       42
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       2192
"""


class ListenerPidTests(unittest.TestCase):
    def test_finds_the_listening_pid(self):
        self.assertEqual(_parse_listener_pid(NETSTAT, 8188), 12000)

    def test_ignores_time_wait_rows_with_pid_zero(self):
        closed = (
            "  TCP    127.0.0.1:4105         127.0.0.1:8188         TIME_WAIT       0\n"
        )
        self.assertIsNone(_parse_listener_pid(closed, 8188))

    def test_ignores_other_ports(self):
        self.assertEqual(_parse_listener_pid(NETSTAT, 8189), 42)

    def test_returns_none_when_nothing_listens(self):
        other = "  TCP    0.0.0.0:135   0.0.0.0:0   LISTENING   4\n"
        self.assertIsNone(_parse_listener_pid(other, 8188))

    def test_empty_output(self):
        self.assertIsNone(_parse_listener_pid("", 8188))


class TunnelDetectionTests(unittest.TestCase):
    def test_ssh_is_a_tunnel(self):
        self.assertTrue(is_tunnel_process("ssh.exe"))
        self.assertTrue(is_tunnel_process("SSH.EXE"))
        self.assertTrue(is_tunnel_process("plink.exe"))

    def test_python_is_not_a_tunnel(self):
        self.assertFalse(is_tunnel_process("python.exe"))
        self.assertFalse(is_tunnel_process("ComfyUI.exe"))
        self.assertFalse(is_tunnel_process(None))
        self.assertFalse(is_tunnel_process(""))


if __name__ == "__main__":
    unittest.main()
