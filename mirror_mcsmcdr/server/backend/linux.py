import os
from typing import Optional

import psutil

from mirror_mcsmcdr.config.mirror_config import MirrorConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import KillTargets, TerminalProxy
from mirror_mcsmcdr.server.status import Capability
from mirror_mcsmcdr.server.system_utils.screen_utils import Screen, ScreenError
from mirror_mcsmcdr.server.tracker import Adoption, ProcessRecord, ProcessTracker, TreeView


class LinuxProxy(TerminalProxy):
    name = "linux"
    supports = frozenset(Action)

    def __init__(self, config: MirrorConfig, tracker: ProcessTracker) -> None:
        super().__init__(config, tracker)
        # refuses a name screen cannot address before anything is launched
        Screen(self.terminal_name, self.path)

    def _screen(self, record: Optional[ProcessRecord]) -> Screen:
        """
        The session of the recorded launch, by the name it was launched with, or the window an adopted mirror runs in.

        :raise ScreenError: if the record is not of a launch by this backend, or of an adopted mirror in a screen
        """
        if record is None or record.backend != self.name:
            raise ScreenError("No screen was launched by this plugin")
        adoption = record.adoption
        if adoption is None:
            return Screen(record.terminal_name, record.launch_path, record.root.pid)
        if adoption.console != "screen" or adoption.session_name is None:
            raise ScreenError("The adopted mirror runs in no screen")
        return Screen(adoption.session_name, record.launch_path, adoption.session_pid, adoption.window or "0")

    def _console_exists(self, record: ProcessRecord) -> Optional[bool]:
        # a launch by another backend, or an adopted mirror outside of screen, has no screen to look for
        if record.backend != self.name or (record.adoption is not None and record.adoption.console != "screen"):
            return False
        return self._screen(record).exists()

    def _console_of(self, process: psutil.Process) -> Adoption:
        # Screen tells what it starts its session and window through STY and WINDOW. A launcher that clears them,
        # such as sudo, is skipped: the shell above it still has them. The search ends at screen itself.
        try:
            lineage = [process, *process.parents()]
        except psutil.Error:
            return Adoption(None)
        for current in lineage:
            try:
                if current.name().lower() == "screen":
                    break
                environ = current.environ()
            except psutil.Error:
                continue
            session, window = environ.get("STY"), environ.get("WINDOW")
            if not session or window is None:
                continue
            pid, _, name = session.partition(".")
            try:
                if pid.isdigit() and Screen(name, self.path, int(pid), window).exists():
                    return Adoption("screen", int(pid), name, window)
            except ScreenError:
                pass
            break
        return Adoption(None)

    def _endpoint_alive(self, view: TreeView) -> bool:
        return view.root_alive and bool(view.console)

    def _launch(self, result: ActionResult) -> ActionResult:
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

    def _type(self, view: TreeView, command: str) -> bool:
        self._screen(view.record).send(command)
        return True

    def _kill(self, result: ActionResult) -> ActionResult:
        if not self.is_mcdr:
            # a plain server has no kill command to be asked with
            return self._forcekill(result)
        if not result.snapshot.evidence.endpoint_alive:
            # without the screen there is no console to send the kill command to
            return result.reject(ActionResult.Outcome.FORCE_REQUIRED)
        if result.snapshot.evidence.port_listening and Capability.CONSOLE_INPUT in result.snapshot.capabilities():
            return self._send_console(result, "!!MCDR server kill")
        view = self.tracker.observe(self.listener)
        if view.record is not None and view.record.adoption is not None:
            # the session is not the plugin's to close: what runs in it goes instead
            errors = self._kill_all(live.process for live in view.members)
            if errors:
                raise errors[0]
            return result
        self._screen(view.record).quit()
        return result

    def _end(self, targets: KillTargets) -> list[Exception]:
        record = targets.record
        # the session itself is closed through screen, which also clears its socket; that of an adopted mirror is left alone
        session = record.root.pid if record is not None and record.backend == self.name and record.adoption is None else None
        errors = self._kill_all(process for _, process in targets.processes if process.pid != session)
        if session is None:
            return errors
        try:
            self._screen(record).quit()
        except ScreenError as error:
            errors.append(error)
            errors += self._kill_all(process for _, process in targets.processes if process.pid == session)
        return errors
