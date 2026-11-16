from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar, Iterable, Optional

import psutil

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.status import Evidence, ProcessInfo
from mirror_mcsmcdr.server.system_utils import process_utils
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener
from mirror_mcsmcdr.server.tracker import ProcessRecord, ProcessTracker, Role, TreeView


class ServerBackend(ABC):
    """One way to reach the server: it reports what it can observe and carries out the actions it supports."""

    supports: ClassVar[frozenset[Action]]

    @abstractmethod
    def observe(self) -> Evidence:
        ...

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

    @property
    def stop_command(self) -> str:
        return "!!MCDR server stop_exit" if self.is_mcdr else "stop"

    def observe(self) -> Evidence:
        view = self.tracker.observe(self.listener)
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

    @abstractmethod
    def _endpoint_alive(self, view: TreeView) -> bool:
        """Whether the console of the launch in ``view.record``, which this backend made, is still there."""

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
