import os
import subprocess

import psutil

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
        pids = self.listener.pids()
        if pids:
            # with the server gone, whatever launched it ends by itself
            for pid in pids:
                subprocess.Popen(["taskkill", "/PID", str(pid), "/F"], shell=True)
            return result
        # no port is open while the server is still starting: all there is to go by is the terminal it was started in
        for process in self._terminal_processes():
            try:
                process.kill()
            except psutil.Error:
                pass
        return result

    def _terminal_processes(self) -> list[psutil.Process]:
        """The shells this backend launched the server from that are still open, each ahead of everything it runs."""
        launch = f"title {self.terminal_name}&&{self.command}"
        path = os.path.normcase(os.path.abspath(self.path))
        processes: list[psutil.Process] = []
        for process in psutil.process_iter(["name", "cmdline", "cwd"]):
            try:
                if (process.info["name"] or "").lower() != "cmd.exe" or not " ".join(process.info["cmdline"] or []).endswith(launch):
                    continue
                if os.path.normcase(process.info["cwd"] or "") == path:
                    processes += [process, *process.children(recursive=True)]
            except psutil.Error:
                continue
        return processes
