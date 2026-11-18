import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Iterable, Optional

import psutil

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.status import Evidence, ProcessInfo, ServerState
from mirror_mcsmcdr.server.system_utils import process_utils
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener
from mirror_mcsmcdr.server.tracker import ProcessRecord, ProcessTracker, Role, TreeView


class ServerBackend(ABC):
    """One way to reach the server: it reports what it can observe and carries out the actions it supports."""

    supports: ClassVar[frozenset[Action]]

    @abstractmethod
    def observe(self) -> Evidence:
        ...

    def watch(self, timeout: float) -> None:
        """
        Block until something this backend observes may have changed, or for ``timeout`` at most.

        Returning early is a hint only: the caller observes again either way. By default nothing is watched.
        """
        time.sleep(timeout)

    def perform(self, result: ActionResult) -> ActionResult:
        """
        Carry out ``result.action``, which is one of :attr:`supports` and has passed :meth:`ActionResult.check`.

        :return: the given result, or a rejection of it if the action could not be carried out
        """
        match result.action:
            case Action.START:
                return self._start(result)
            case Action.STOP:
                return self._stop(result)
            case Action.KILL:
                return self._kill(result)
            case Action.FORCEKILL:
                return self._forcekill(result)

    # A backend overrides the methods of the actions it lists in :attr:`supports`; the others are never called.

    def _start(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _stop(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _kill(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _forcekill(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _unsupported(self, result: ActionResult) -> NotImplementedError:
        return NotImplementedError(f"{type(self).__name__} does not support {result.action}")


@dataclass(frozen=True)
class KillTargets:
    """What a forced kill would end."""

    record: Optional[ProcessRecord]
    # the tracked processes, parents ahead of their children, then the listeners of the port the plugin did not launch
    processes: tuple[tuple[ProcessInfo, psutil.Process], ...]
    # something holds the port whose pid cannot be read, so the port cannot be freed by force
    unreadable: bool


class TerminalProxy(ServerBackend, ABC):
    """A backend that launches the server from a command line on this machine and keeps track of what it launched."""

    # the backend as the record names it
    name: ClassVar[str]

    def __init__(self, config: TerminalConfig, tracker: ProcessTracker) -> None:
        self.terminal_name = config.terminal_name or "Mirror"
        self.path = config.launch_path
        self.command = config.launch_command
        self.is_mcdr = config.is_mcdr
        assert config.port is not None
        self.listener = PortListener(config.port)
        self.tracker = tracker

    # how often the recorded processes are looked at while watching
    _WATCH_SLICE = 0.25

    @property
    def stop_command(self) -> str:
        return "!!MCDR server stop_exit" if self.is_mcdr else "stop"

    def watch(self, timeout: float) -> None:
        # Only an exit is watched, which is what a stop waits for; a new process or the port opening shows at the next status.
        # Not psutil.wait_procs: it reaps a process that is a child of this one, such as the shell of the subprocess proxy.
        processes, unchanged = self.tracker.live_processes()
        if not unchanged:
            # one has exited since the last status was taken
            return
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            time.sleep(min(self._WATCH_SLICE, remaining))
            if not all(process_utils.is_alive(process) for process in processes):
                return

    @property
    def _console_readers(self) -> frozenset[Role]:
        """The roles of the processes that read what is typed into the console."""
        return frozenset({Role.MCDR}) if self.is_mcdr else frozenset({Role.MCDR, Role.SERVER, Role.CHILD, Role.OTHER})

    def _start(self, result: ActionResult) -> ActionResult:
        if result.snapshot.state is ServerState.MCDR_ONLY:
            # the server alone, by the MCDR that is still there
            return self._send_console(result, "!!MCDR server start")
        return self._launch(result)

    def _stop(self, result: ActionResult) -> ActionResult:
        # stop_exit fails once the server has stopped, so an MCDR without a server is told to exit instead
        command = "!!MCDR server exit" if result.snapshot.state is ServerState.MCDR_ONLY else self.stop_command
        return self._send_console(result, command)

    def _send_console(self, result: ActionResult, command: str) -> ActionResult:
        """
        Type a command the plugin composed into the console of the recorded launch.

        Right before, the console and the process that reads it are checked again:
        whatever else is left in the console, such as the shell of a failed launch, would take the command for its own.
        A short window between the check and the input remains.

        :return: ``result``, or its rejection with CONSOLE_INPUT_FAILED.
            Whether the status changed or the input itself failed is for the caller to tell from a new status
        """
        view = self.tracker.observe(self.listener, self._console_exists)
        record = view.record
        if (
            record is None or record.backend != self.name or not self._endpoint_alive(view)
            or not view.alive(*self._console_readers) or not self._type(view, command)
        ):
            return result.reject(ActionResult.Outcome.CONSOLE_INPUT_FAILED)
        return result

    def observe(self) -> Evidence:
        view = self.tracker.observe(self.listener, self._console_exists)
        port_owned = any(live.member.pid in view.listeners for live in view.members)
        if self.is_mcdr:
            mcdr_alive: Optional[bool] = view.alive(Role.MCDR)
            server_alive = view.alive(Role.SERVER, Role.CHILD) or port_owned
            others_alive = view.alive(Role.OTHER)
            server_roles = {Role.SERVER}
            # with MCDR gone, a server outside of it may still hold the port
            listener_roles = {Role.SERVER, Role.OTHER}
        else:
            mcdr_alive, others_alive = None, False
            server_alive = view.alive(Role.MCDR, Role.SERVER, Role.CHILD, Role.OTHER)
            server_roles = listener_roles = {Role.MCDR, Role.SERVER, Role.CHILD, Role.OTHER}
        # the listener is the server for certain; otherwise the deepest process of it, past any shell it was started through
        server = next((live for live in view.members if live.member.pid in view.listeners and live.member.role in listener_roles), None)
        if server is None:
            server = next((live for live in reversed(view.members) if live.member.role in server_roles), None)
        mcdr = next((live for live in view.members if live.member.role is Role.MCDR), None) if self.is_mcdr else None
        return Evidence(
            port_listening=bool(view.listeners),
            foreign_listeners=tuple(self._describe_listener(pid) for pid in view.foreign_listeners()),
            mcdr_alive=mcdr_alive,
            server_alive=server_alive,
            others_alive=others_alive,
            wrapper_alive=view.alive(Role.WRAPPER),
            # a launch by another backend cannot be controlled from this one
            endpoint_alive=view.record is not None and view.record.backend == self.name and self._endpoint_alive(view),
            port=self.listener.port,
            mcdr_process=process_utils.describe(mcdr.process, True) if mcdr is not None else None,
            server_process=process_utils.describe(server.process, True) if server is not None else None,
            child_processes=tuple(process_utils.describe(live.process, True) for live in view.members if live.member.role is Role.CHILD),
            others_count=sum(live.member.role is Role.OTHER and live is not server for live in view.members) if self.is_mcdr else 0,
        )

    def _console_exists(self, record: ProcessRecord) -> Optional[bool]:
        """
        Whether the console of an active record is still there, for a backend whose processes do not tell it.

        :return: None if the processes tell it
        """
        return None

    @abstractmethod
    def _endpoint_alive(self, view: TreeView) -> bool:
        """Whether the console of the launch in ``view.record``, which this backend made, is still there."""

    @abstractmethod
    def _launch(self, result: ActionResult) -> ActionResult:
        """Launch a new process tree with the launch command."""

    @abstractmethod
    def _type(self, view: TreeView, command: str) -> bool:
        """
        Deliver one line to the console of the launch in ``view.record``, which this backend made and is read by a live process.

        :return: whether the console took it
        """

    def forcekill_targets(self) -> KillTargets:
        view = self.tracker.observe(self.listener)
        targets = [(process_utils.describe(live.process, True), live.process) for live in view.members]
        unreadable = False
        for pid in view.foreign_listeners():
            try:
                process = psutil.Process(pid) if pid is not None else None
            except psutil.NoSuchProcess:
                continue
            except psutil.Error:
                process = None
            if process is None:
                unreadable = True
                continue
            targets.append((process_utils.describe(process, False), process))
        return KillTargets(view.record, tuple(targets), unreadable)

    def _forcekill(self, result: ActionResult) -> ActionResult:
        targets = self.forcekill_targets()
        if targets.unreadable:
            return result.reject(ActionResult.Outcome.UNREADABLE_LISTENER)
        if not targets.processes:
            return result.reject(ActionResult.Outcome.NO_TARGET)
        # each one is attempted whatever became of the others, and the first failure is reported at the end
        errors = self._end(targets)
        if errors:
            raise errors[0] from (errors[1] if len(errors) > 1 else None)
        return result

    def _end(self, targets: KillTargets) -> list[Exception]:
        """Kill the targets of a forced kill; a backend adds what its console needs."""
        return self._kill_all(process for _, process in targets.processes)

    @staticmethod
    def _kill_all(processes: Iterable[psutil.Process]) -> list[Exception]:
        """Kill each process, parents first so that nothing is left to restart what has just been killed."""
        errors: list[Exception] = []
        for process in processes:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
            except psutil.Error as error:
                errors.append(error)
        return errors

    @staticmethod
    def _describe_listener(pid: Optional[int]) -> ProcessInfo:
        if pid is None:
            return ProcessInfo(None, "", "", False)
        try:
            return process_utils.describe(psutil.Process(pid), False)
        except psutil.Error:
            return ProcessInfo(pid, "", "", False)
