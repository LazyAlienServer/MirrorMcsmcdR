import os
import signal
from abc import ABC

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.utils.command_utils import run_shell_command
from mirror_mcsmcdr.utils.port_utils import PortListener
from mirror_mcsmcdr.utils.proxy.backend import ServerBackend
from mirror_mcsmcdr.utils.screen_utils import Screen
from mirror_mcsmcdr.utils.status import Action, ActionResult, Evidence


class TerminalProxy(ServerBackend, ABC):
    """A backend that launches the server from a command line on this machine."""

    def __init__(self, config: TerminalConfig) -> None:
        self.terminal_name = config.terminal_name or "Mirror"
        self.path = config.launch_path
        self.command = config.launch_command
        self.is_mcdr = config.is_mcdr

    @property
    def stop_command(self) -> str:
        return "!!MCDR server stop_exit" if self.is_mcdr else "stop"


class LinuxProxy(TerminalProxy):
    supports = frozenset(Action)

    def __init__(self, config: TerminalConfig) -> None:
        super().__init__(config)
        assert config.port is not None
        self.listener = PortListener(config.port, config.regex_strict)
        self.screen = Screen(self.terminal_name, self.path)

    def observe(self) -> Evidence:
        return Evidence(port_listening=bool(self.listener.pids()), screen_exists=self.screen.check_existence())

    def perform(self, result: ActionResult) -> ActionResult:
        action = result.action
        if action is Action.START:
            if not os.path.exists(self.path):
                return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
            self.screen.create(self.command)
        elif action is Action.STOP:
            self.screen.stop(self.stop_command)
        elif action is Action.KILL and self.is_mcdr:
            evidence = result.snapshot.evidence
            if evidence.screen_exists is None:
                # a backend ahead of this one settled the status, so the terminal was not looked at
                evidence = self.observe()
            if not evidence.screen_exists:
                # without the screen there is no console to send the kill command to
                return result.reject(ActionResult.Outcome.FORCE_REQUIRED)
            if evidence.port_listening:
                self.screen.kill("!!MCDR server kill")
            else:
                self.screen.forcekill()
        else:
            self._forcekill()
        return result

    def _forcekill(self) -> None:
        try:
            for pid in self.listener.pids():
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            if self.screen.check_existence():
                self.screen.forcekill()


class WindowsProxy(TerminalProxy):
    # killing is already forceful here
    supports = frozenset({Action.START, Action.STOP, Action.KILL})

    def __init__(self, config: TerminalConfig) -> None:
        super().__init__(config)
        assert config.port is not None
        self.listener = PortListener(config.port, config.regex_strict)

    def observe(self) -> Evidence:
        return Evidence(port_listening=bool(self.listener.pids()))

    def perform(self, result: ActionResult) -> ActionResult:
        action = result.action
        if action is Action.START:
            if not os.path.exists(self.path):
                return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
            run_shell_command(f'''start cmd.exe cmd /C "title {self.terminal_name}&&{self.command}"''', cwd=self.path)
        elif action is Action.STOP:
            for pid in self.listener.pids():
                try:
                    os.kill(pid, signal.SIGINT)
                except (ProcessLookupError, PermissionError):
                    pass
        else:
            for pid in self.listener.pids():
                run_shell_command(["taskkill", "/PID", str(pid), "/F"])
        return result
