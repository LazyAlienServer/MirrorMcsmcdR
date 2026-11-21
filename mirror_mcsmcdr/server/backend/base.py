import os
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Iterable, Optional

import psutil

from mirror_mcsmcdr.config.mirror_config import MirrorConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.status import Evidence, Origin, ProcessInfo, ServerState
from mirror_mcsmcdr.server.system_utils import process_utils
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener
from mirror_mcsmcdr.server.tracker import Adoption, ProcessRecord, ProcessTracker, Role, TreeView

# a process by its pid and its start token, which tells it from a later one with the same pid
ProcessIdentity = tuple[int, str]


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

    def perform(self, result: ActionResult, listed: Optional[frozenset[ProcessIdentity]] = None) -> ActionResult:
        """
        Carry out ``result.action``, which is one of :attr:`supports` and has passed :meth:`ActionResult.check`.

        :param listed: for a forced kill, the processes shown to the operator beforehand; it ends none but these
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
                return self._forcekill(result, listed)

    # A backend overrides the methods of the actions it lists in :attr:`supports`; the others are never called.

    def _start(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _stop(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _kill(self, result: ActionResult) -> ActionResult:
        raise self._unsupported(result)

    def _forcekill(self, result: ActionResult, listed: Optional[frozenset[ProcessIdentity]] = None) -> ActionResult:
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

    def identities(self) -> frozenset[ProcessIdentity]:
        """The targets by identity; one that is gone by now is left out."""
        found = set()
        for _, process in self.processes:
            try:
                found.add((process.pid, process_utils.start_token(process)))
            except psutil.Error:
                pass
        return frozenset(found)


class TerminalProxy(ServerBackend, ABC):
    """A backend that launches the server from a command line on this machine and keeps track of what it launched."""

    # the backend as the record names it
    name: ClassVar[str]

    def __init__(self, config: MirrorConfig, tracker: ProcessTracker) -> None:
        """:raise re.error: if ``java_name`` is no regular expression"""
        terminal = config.terminal
        self.terminal_name = terminal.terminal_name or "Mirror"
        self.path = config.root_path
        self.command = terminal.launch_command
        self.is_mcdr = config.is_mcdr
        self.java_name = re.compile(terminal.java_name, re.IGNORECASE)
        assert terminal.port is not None
        self.listener = PortListener(terminal.port)
        self.tracker = tracker

    # how often the recorded processes are looked at while watching, for an exit and for the port
    _WATCH_SLICE = 0.25
    _PORT_WATCH_SLICE = 1.0

    @property
    def stop_command(self) -> str:
        return "!!MCDR server stop_exit" if self.is_mcdr else "stop"

    def watch(self, timeout: float) -> None:
        # An exit is watched, and whether the recorded processes listen on the port, from their own sockets.
        # A new process is not: children() snapshots every process of the machine on Windows. It joins the record at the next status.
        # Not psutil.wait_procs: it reaps a process that is a child of this one, such as the shell of the subprocess proxy.
        processes, unchanged = self.tracker.live_processes()
        if not unchanged:
            # one has exited since the last status was taken
            return
        listening = self.listener.listened_by(processes)
        now = time.monotonic()
        deadline = now + timeout
        next_port_check = now + self._PORT_WATCH_SLICE
        while (remaining := deadline - time.monotonic()) > 0:
            time.sleep(min(self._WATCH_SLICE, remaining))
            if not all(process_utils.is_alive(process) for process in processes):
                return
            if time.monotonic() >= next_port_check:
                if self.listener.listened_by(processes) != listening:
                    return
                next_port_check += self._PORT_WATCH_SLICE

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
        origin = self._member_origin(view)
        return Evidence(
            port_listening=bool(view.listeners),
            foreign_listeners=tuple(self._describe_listener(pid) for pid in view.foreign_listeners()),
            mcdr_alive=mcdr_alive,
            server_alive=server_alive,
            server_listened=any(live.member.listened for live in view.members),
            others_alive=others_alive,
            wrapper_alive=view.alive(Role.WRAPPER),
            # a launch by another backend cannot be controlled from this one
            endpoint_alive=view.record is not None and view.record.backend == self.name and self._endpoint_alive(view),
            port=self.listener.port,
            mcdr_process=process_utils.describe(mcdr.process, origin) if mcdr is not None else None,
            server_process=process_utils.describe(server.process, origin) if server is not None else None,
            child_processes=tuple(process_utils.describe(live.process, origin) for live in view.members if live.member.role is Role.CHILD),
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

    def find_untracked(self) -> list[psutil.Process]:
        """
        The mirror's MCDR instances, or its Java processes when it is not run by MCDR,
        that run on this machine but are not in the record, such as one started by hand.

        Every process of the machine is looked at, so this is for a decision, not for a watch.
        """
        tracked, _ = self.tracker.live_processes()
        # the MCDR this plugin runs in, too: a launch path pointing at its own folder must not make it a mirror
        exclude = {process.pid for process in tracked} | {os.getpid()}
        if self.is_mcdr:
            return process_utils.find_mcdr_in(self.path, exclude)
        return process_utils.find_java_in(self.path, exclude, self.java_name)

    def holds_port(self, process: psutil.Process) -> bool:
        """
        Whether the port is free or listened on by ``process`` and its descendants only, so that adopting it takes in the whole mirror.

        :raise psutil.Error: if the descendants of ``process`` cannot be read
        """
        listeners = self.listener.owners()
        if None in listeners:
            return False
        mirror = {process.pid} | {child.pid for child in process.children(recursive=True)}
        return listeners <= mirror

    def adopt(self, process: psutil.Process) -> Adoption:
        """
        Record ``process``, an MCDR of the mirror that runs outside the record, as the root of the mirror, together with its console.

        :raise psutil.Error: if the process is gone or cannot be read
        """
        adoption = self._console_of(process)
        self.tracker.adopt(self.name, self.path, process, adoption)
        return adoption

    def _console_of(self, process: psutil.Process) -> Adoption:
        """The console of a process this backend did not launch, if the backend can type into it."""
        return Adoption(None)

    def forcekill_targets(self) -> KillTargets:
        view = self.tracker.observe(self.listener)
        origin = self._member_origin(view)
        targets = [(process_utils.describe(live.process, origin), live.process) for live in view.members]
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
            targets.append((process_utils.describe(process, Origin.UNTRACKED), process))
        return KillTargets(view.record, tuple(targets), unreadable)

    def _forcekill(self, result: ActionResult, listed: Optional[frozenset[ProcessIdentity]] = None) -> ActionResult:
        targets = self.forcekill_targets()
        if targets.unreadable:
            return result.reject(ActionResult.Outcome.UNREADABLE_LISTENER)
        if not targets.processes:
            return result.reject(ActionResult.Outcome.NO_TARGET)
        # those listed that have exited meanwhile are simply not there; anything else would be ended unseen
        if listed is not None and not targets.identities() <= listed:
            return result.reject(ActionResult.Outcome.TARGETS_CHANGED)
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
    def _member_origin(view: TreeView) -> Origin:
        return Origin.ADOPTED if view.record is not None and view.record.adoption is not None else Origin.LAUNCHED

    @staticmethod
    def _describe_listener(pid: Optional[int]) -> ProcessInfo:
        if pid is None:
            return ProcessInfo(None, "", "", Origin.UNTRACKED)
        try:
            return process_utils.describe(psutil.Process(pid), Origin.UNTRACKED)
        except psutil.Error:
            return ProcessInfo(pid, "", "", Origin.UNTRACKED)
