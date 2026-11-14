import os
from abc import ABC

import psutil

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.backend.base import ServerBackend
from mirror_mcsmcdr.server.backend.console import send_console_command
from mirror_mcsmcdr.server.backend.port import PortListener
from mirror_mcsmcdr.server.backend.screen import Screen, ScreenError
from mirror_mcsmcdr.server.backend.shell import run_shell_command
from mirror_mcsmcdr.server.status import Action, ActionResult, Evidence


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
        return Evidence(port_listening=self.listener.is_listening(), screen_exists=self.screen.check_existence())

    def _start(self, result: ActionResult) -> ActionResult:
        if not os.path.exists(self.path):
            return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
        self.screen.create(self.command)
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        self.screen.send(self.stop_command)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        if not self.is_mcdr:
            # a plain server has no kill command to be asked with
            return self._forcekill(result)
        evidence = result.snapshot.evidence
        if evidence.screen_exists is None:
            # a backend ahead of this one settled the status, so the terminal was not looked at
            evidence = self.observe()
        if not evidence.screen_exists:
            # without the screen there is no console to send the kill command to
            return result.reject(ActionResult.Outcome.FORCE_REQUIRED)
        if evidence.port_listening:
            self.screen.send("!!MCDR server kill")
        else:
            self.screen.quit()
        return result

    def _forcekill(self, result: ActionResult) -> ActionResult:
        errors: list[Exception] = []
        targets: list[psutil.Process] = []
        # Everything in the session goes, so that a server that has not opened its port yet goes as well.
        # Each step is attempted whatever became of the others, and the first failure is reported at the end.
        for find in (self.screen.processes, self.listener.processes):
            try:
                targets += find()
            except (ScreenError, psutil.Error, OSError) as error:
                errors.append(error)
        # parents first: nothing is left to restart what has just been killed
        for process in dict.fromkeys(targets):
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error as error:
                errors.append(error)
        try:
            self.screen.quit()
        except ScreenError as error:
            errors.append(error)
        if errors:
            raise errors[0] from (errors[1] if len(errors) > 1 else None)
        return result


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
        run_shell_command(f'''start cmd.exe cmd /C "title {self.terminal_name}&&{self.command}"''', cwd=self.path)
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        # the listening processes normally share one console, so the first one that takes the command is enough
        if not any(send_console_command(pid, self.stop_command) for pid in self.listener.pids()):
            return result.reject(ActionResult.Outcome.WRONG_STATE)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        for pid in self.listener.pids():
            run_shell_command(["taskkill", "/PID", str(pid), "/F"])
        return result
