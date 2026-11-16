import os
from typing import Optional

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import KillTargets, TerminalProxy
from mirror_mcsmcdr.server.status import Capability
from mirror_mcsmcdr.server.system_utils.screen_utils import Screen, ScreenError
from mirror_mcsmcdr.server.tracker import ProcessRecord, ProcessTracker, TreeView


class LinuxProxy(TerminalProxy):
    name = "linux"
    supports = frozenset(Action)

    def __init__(self, config: TerminalConfig, tracker: ProcessTracker) -> None:
        super().__init__(config, tracker)
        # refuses a name screen cannot address before anything is launched
        Screen(self.terminal_name, self.path)

    def _screen(self, record: Optional[ProcessRecord]) -> Screen:
        """
        The session of the recorded launch, by the name it was launched with.

        :raise ScreenError: if the record is not of a launch by this backend
        """
        if record is None or record.backend != self.name:
            raise ScreenError("No screen was launched by this plugin")
        return Screen(record.terminal_name, record.launch_path, record.root.pid)

    def _endpoint_alive(self, view: TreeView) -> bool:
        return view.root_alive and self._screen(view.record).exists()

    def _start(self, result: ActionResult) -> ActionResult:
        if not os.path.exists(self.path):
            return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)
        screen = Screen(self.terminal_name, self.path)
        try:
            screen.create(self.command)
        finally:
            # a session that could not be closed may run the command after all
            if screen.pid is not None:
                self.tracker.register(self.name, self.path, self.command, self.terminal_name, screen.pid)
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        self._screen(self.tracker.observe(self.listener).record).send(self.stop_command)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        if not self.is_mcdr:
            # a plain server has no kill command to be asked with
            return self._forcekill(result)
        if not result.snapshot.evidence.endpoint_alive:
            # without the screen there is no console to send the kill command to
            return result.reject(ActionResult.Outcome.FORCE_REQUIRED)
        screen = self._screen(self.tracker.observe(self.listener).record)
        if result.snapshot.evidence.port_listening and Capability.CONSOLE_INPUT in result.snapshot.capabilities():
            screen.send("!!MCDR server kill")
        else:
            screen.quit()
        return result

    def _end(self, targets: KillTargets) -> list[Exception]:
        record = targets.record
        # the session itself is closed through screen, which also clears its socket
        session = record.root.pid if record is not None and record.backend == self.name else None
        errors = self._kill_all(process for _, process in targets.processes if process.pid != session)
        if session is None:
            return errors
        try:
            self._screen(record).quit()
        except ScreenError as error:
            errors.append(error)
            errors += self._kill_all(process for _, process in targets.processes if process.pid == session)
        return errors
