import os
import subprocess

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import TerminalProxy
from mirror_mcsmcdr.server.status import Evidence
from mirror_mcsmcdr.server.system_utils.console_utils import send_console_command
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener


class WindowsProxy(TerminalProxy):
    # killing is already forceful here
    supports = frozenset({Action.START, Action.STOP, Action.KILL})

    def __init__(self, config: TerminalConfig) -> None:
        super().__init__(config)
        assert config.port is not None
        self.listener = PortListener(config.port, config.regex_strict)

    def observe(self) -> Evidence:
        return Evidence(port_listening=self.listener.is_listening())

    def _start(self, result: ActionResult) -> ActionResult:
        if not os.path.exists(self.path):
            return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
        subprocess.Popen(f'''start cmd.exe cmd /C "title {self.terminal_name}&&{self.command}"''', shell=True, cwd=self.path)
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        # the listening processes normally share one console, so the first one that takes the command is enough
        if not any(send_console_command(pid, self.stop_command) for pid in self.listener.pids()):
            return result.reject(ActionResult.Outcome.WRONG_STATE)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        for pid in self.listener.pids():
            subprocess.Popen(["taskkill", "/PID", str(pid), "/F"], shell=True)
        return result
