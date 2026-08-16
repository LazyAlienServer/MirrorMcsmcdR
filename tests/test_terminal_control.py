import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

package = types.ModuleType("mirror_mcsmcdr")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "mirror_mcsmcdr")]
sys.modules.setdefault("mirror_mcsmcdr", package)

mcdr_module = types.ModuleType("mcdreforged")
mcdr_api_module = types.ModuleType("mcdreforged.api")
mcdr_all_module = types.ModuleType("mcdreforged.api.all")
mcdr_all_module.RconConnection = object
mcdr_all_module.RTextList = object
mcdr_all_module.ServerInterface = object
mcdr_all_module.RAction = object
sys.modules.setdefault("mcdreforged", mcdr_module)
sys.modules.setdefault("mcdreforged.api", mcdr_api_module)
sys.modules.setdefault("mcdreforged.api.all", mcdr_all_module)

from mirror_mcsmcdr.utils.proxy.system_proxy import LinuxProxy
from mirror_mcsmcdr.utils.screen_utils import Screen
from mirror_mcsmcdr.utils.server_utils import ServerProxy


class FakeLinuxProxy:
    terminal_name = "Mirror"

    def __init__(self, path):
        self.path = path


class LinuxProxyTest(unittest.TestCase):
    def make_proxy(self, is_mcdr=True):
        screen = Mock()
        with patch("mirror_mcsmcdr.utils.proxy.system_proxy.Screen", return_value=screen):
            proxy = LinuxProxy(
                "Mirror", "/tmp/mirror", "python -m mcdreforged", 25565,
                False, is_mcdr,
            )
        return proxy, screen

    def test_stop_forwards_mcdr_mode_to_screen(self):
        proxy, screen = self.make_proxy(True)

        self.assertEqual(proxy.stop(), "success")
        screen.stop.assert_called_once_with(True)

    def test_stop_without_mcdr_forwards_minecraft_stop_mode(self):
        proxy, screen = self.make_proxy(False)

        self.assertEqual(proxy.stop(), "success")
        screen.stop.assert_called_once_with(False)

    def test_kill_without_mcdr_uses_forcekill(self):
        proxy, screen = self.make_proxy(False)
        proxy.forcekill = Mock(return_value="success")

        self.assertEqual(proxy.kill(), "success")
        proxy.forcekill.assert_called_once_with()
        screen.kill.assert_not_called()

    def test_forcekill_kills_listener_pids_before_screen(self):
        proxy, screen = self.make_proxy()
        screen.check_existence.return_value = True
        events = []

        with patch("mirror_mcsmcdr.utils.proxy.system_proxy.signal.SIGKILL", 9, create=True), \
                patch("mirror_mcsmcdr.utils.proxy.system_proxy.os.popen") as popen, \
                patch("mirror_mcsmcdr.utils.proxy.system_proxy.os.kill") as kill:
            popen.return_value.read.return_value = "101\n202\n101\n"
            kill.side_effect = lambda pid, sig: events.append(("pid", pid, sig))
            screen.forcekill.side_effect = lambda: events.append(("screen",))

            self.assertEqual(proxy.forcekill(), "success")

        self.assertEqual(
            {event[1] for event in events if event[0] == "pid"}, {101, 202}
        )
        self.assertTrue(all(event[2] == 9 for event in events if event[0] == "pid"))
        self.assertEqual(events[-1], ("screen",))


class ScreenTest(unittest.TestCase):
    def make_screen(self):
        temp_dir = tempfile.TemporaryDirectory()
        path = Path(temp_dir.name)
        (path / "mirror.pid").write_text("123", encoding="utf-8")
        fake_proxy = FakeLinuxProxy(str(path))
        return temp_dir, path, fake_proxy

    def test_stop_and_kill_keep_pid_file_until_screen_exits(self):
        temp_dir, path, fake_proxy = self.make_screen()
        self.addCleanup(temp_dir.cleanup)

        with patch.object(Screen, "_screen_exists", return_value=True), \
                patch("mirror_mcsmcdr.utils.screen_utils.os.popen") as popen:
            screen = Screen(fake_proxy)
            screen.stop(True)
            self.assertIn("!!MCDR server stop_exit", popen.call_args[0][0])
            self.assertTrue((path / "mirror.pid").exists())

            screen.stop(False)
            self.assertIn('stuff "stop\n"', popen.call_args[0][0])
            self.assertTrue((path / "mirror.pid").exists())

            screen.kill()
            self.assertIn("!!MCDR server kill", popen.call_args[0][0])
            self.assertTrue((path / "mirror.pid").exists())

    def test_status_cleanup_removes_pid_after_screen_disappears(self):
        temp_dir, path, fake_proxy = self.make_screen()
        self.addCleanup(temp_dir.cleanup)

        with patch.object(Screen, "_screen_exists", return_value=False):
            screen = Screen(fake_proxy)

        self.assertFalse((path / "mirror.pid").exists())
        self.assertIsNone(screen.pid)


class TerminalSettingTest(unittest.TestCase):
    def test_is_mcdr_false_is_a_valid_terminal_configuration(self):
        proxy = ServerProxy()

        with patch("mirror_mcsmcdr.utils.server_utils.SystemProxy") as system_proxy:
            self.assertTrue(proxy.set_terminal(
                True,
                regex_strict=False,
                is_mcdr=False,
                system="Linux",
                terminal_name="Mirror",
                launch_path="/tmp/mirror",
                launch_command="python -m mcdreforged",
                port=25565,
            ))

        self.assertIs(proxy.terminal, system_proxy.return_value)
        self.assertFalse(system_proxy.call_args.kwargs["is_mcdr"])


class CommandRegistrationTest(unittest.TestCase):
    def test_force_kill_aliases_are_registered(self):
        source = Path("mirror_mcsmcdr/mirror_manager.py").read_text(encoding="utf-8")

        self.assertIn('builder.command(\n            f"{command_prefix} kill -f"', source)
        self.assertIn('builder.command(\n            f"{command_prefix} kill --force"', source)


if __name__ == "__main__":
    unittest.main()
