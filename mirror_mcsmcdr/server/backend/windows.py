import os
import subprocess

from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import TerminalProxy
from mirror_mcsmcdr.server.system_utils.console_utils import send_console_command
from mirror_mcsmcdr.server.tracker import TreeView


class WindowsProxy(TerminalProxy):
    name = "windows"
    supports = frozenset(Action)

    def _endpoint_alive(self, view: TreeView) -> bool:
        # the console lives as long as the cmd.exe that opened it
        return view.root_alive

    def _start(self, result: ActionResult) -> ActionResult:
        if not os.path.exists(self.path):
            return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
        # One string: an argument list would escape the quotes of the launch command, and cmd.exe would pass on the escapes.
        # /S makes cmd.exe strip only the outer pair of quotes, whatever the launch command contains.
        process = subprocess.Popen(f'cmd.exe /S /C "title {self.terminal_name}&&{self.command}"', cwd=self.path, creationflags=subprocess.CREATE_NEW_CONSOLE)
        self.tracker.register(self.name, self.path, self.command, self.terminal_name, process.pid)
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        view = self.tracker.observe(self.listener)
        members = view.member_pids()
        # the listening processes normally share one console, so the first one that takes the command is enough
        if not any(send_console_command(pid, self.stop_command) for pid in view.listeners if pid in members):
            return result.reject(ActionResult.Outcome.WRONG_STATE)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        view = self.tracker.observe(self.listener)
        owners = [live.process for live in view.members if live.member.pid in view.listeners]
        # With the server gone, whatever launched it ends by itself.
        # No port is open while the server is still starting: then everything the plugin launched goes.
        errors = self._kill_all(owners or [live.process for live in view.members])
        if errors:
            raise errors[0]
        return result
