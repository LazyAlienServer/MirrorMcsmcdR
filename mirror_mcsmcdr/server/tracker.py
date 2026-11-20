import json
import os
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Optional

import psutil

from mirror_mcsmcdr.server.system_utils import process_utils
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener


class Role(Enum):
    MCDR = "mcdr"
    # the process MCDR runs as the server, and everything below it
    SERVER = "server"
    # what MCDR launched while the server is not told apart yet; it is all taken for the server
    CHILD = "child"
    # the terminal and shell a launch command runs in
    WRAPPER = "wrapper"
    # anything else, including what MCDR launched besides the server
    OTHER = "other"


@dataclass(frozen=True)
class Member:
    pid: int
    token: str
    role: Role


@dataclass(frozen=True)
class Adoption:
    """
    How a mirror the plugin found running, rather than launched, is reached.

    Its console belongs to whoever started it: the plugin types into it, but never closes it or ends what runs above the root.
    """

    # "windows" for the console the root runs in, "screen" for a screen window; None if there is no console to use
    console: Optional[str]
    # for screen: the session, by pid and name, and the window the root runs in
    session_pid: Optional[int] = None
    session_name: Optional[str] = None
    window: Optional[str] = None

    def to_json(self) -> dict[str, Any]:
        return {"console": self.console, "session_pid": self.session_pid, "session_name": self.session_name, "window": self.window}

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Adoption":
        """:raise KeyError, TypeError, ValueError: if ``data`` is not an adoption"""
        def optional(value: Any, kind: type) -> Any:
            return None if value is None else kind(value)

        return cls(optional(data["console"], str), optional(data["session_pid"], int), optional(data["session_name"], str), optional(data["window"], str))


@dataclass(frozen=True)
class ProcessRecord:
    """
    What the plugin launched or adopted last, as it is kept across plugin reloads.

    The launch settings are those of that launch, so that a changed config applies from the next launch on.
    The root is the process the plugin spawned; on Linux and Windows it is also the console the mirror is controlled through.
    For an adopted mirror, the root is its MCDR, and :attr:`adoption` tells its console.
    """

    # counts the launches of this mirror
    generation: int
    backend: str
    launch_path: str
    launch_command: str
    terminal_name: str
    root: Member
    # the live processes of the launch, parents ahead of their children
    members: tuple[Member, ...]
    # False once none of them is alive any more
    active: bool
    # None for a launch of the plugin
    adoption: Optional[Adoption] = None

    def to_json(self) -> dict[str, Any]:
        def member(m: Member) -> dict[str, Any]:
            return {"pid": m.pid, "token": m.token, "role": m.role.value}

        return {
            "generation": self.generation,
            "backend": self.backend,
            "launch_path": self.launch_path,
            "launch_command": self.launch_command,
            "terminal_name": self.terminal_name,
            "root": member(self.root),
            "members": [member(m) for m in self.members],
            "state": "active" if self.active else "exited",
            "adoption": self.adoption.to_json() if self.adoption is not None else None,
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ProcessRecord":
        """:raise KeyError, TypeError, ValueError: if ``data`` is not a record"""
        def member(m: dict[str, Any]) -> Member:
            return Member(int(m["pid"]), str(m["token"]), Role(m["role"]))

        return cls(
            int(data["generation"]),
            str(data["backend"]),
            str(data["launch_path"]),
            str(data["launch_command"]),
            str(data["terminal_name"]),
            member(data["root"]),
            tuple(member(m) for m in data["members"]),
            {"active": True, "exited": False}[data["state"]],
            # absent from the records of earlier versions, which only launched
            Adoption.from_json(data["adoption"]) if data.get("adoption") is not None else None,
        )


@dataclass(frozen=True)
class LiveMember:
    member: Member
    # bound to this very process: it refuses to act on a later one that got the same pid
    process: psutil.Process


@dataclass(frozen=True)
class TreeView:
    """The tracked processes and the listeners of the configured port, as observed at one moment."""

    record: Optional[ProcessRecord]
    # parents ahead of their children
    members: tuple[LiveMember, ...]
    # None stands for a listener whose pid cannot be read
    listeners: frozenset[Optional[int]]
    # whether the console of the record was found, before the members were; None if it was not looked for
    console: Optional[bool] = None

    def member_pids(self) -> set[int]:
        return {live.member.pid for live in self.members}

    def alive(self, *roles: Role) -> bool:
        return any(live.member.role in roles for live in self.members)

    @property
    def root_alive(self) -> bool:
        return self.record is not None and any(live.member == self.record.root for live in self.members)

    def foreign_listeners(self) -> list[Optional[int]]:
        members = self.member_pids()
        return [pid for pid in self.listeners if pid not in members]


class ProcessTracker:
    """
    Keeps track of the processes one mirror was launched as, in a record that survives plugin and config reloads.

    The record is the only thing taken as the mirror: nothing else is looked for.
    Every method may be called from any thread.
    """

    def __init__(self, path: Path, warn: Callable[..., None]) -> None:
        """
        :param warn: tells the console about a problem, given the translation key under ``process_record`` and its arguments
        """
        self.path = path
        self._warn = warn
        self._lock = Lock()
        self._record = self._load()

    def register(self, backend: str, launch_path: str, launch_command: str, terminal_name: str, pid: int) -> None:
        """Record a launch whose root process has just been spawned; it replaces the previous record."""
        with self._lock:
            try:
                process = psutil.Process(pid)
                root = Member(pid, process_utils.start_token(process), self._role_of_root(process))
            except psutil.Error:
                # gone already: the launch failed, and there is nothing to track
                return
            generation = (self._record.generation if self._record is not None else 0) + 1
            self._record = ProcessRecord(generation, backend, launch_path, launch_command, terminal_name, root, (root,), True)
            self._save()

    def adopt(self, backend: str, launch_path: str, process: psutil.Process, adoption: Adoption) -> None:
        """
        Record a mirror that runs outside of any record, with ``process`` as its root; it replaces the previous record.

        Its descendants join at the next observation, as those of a launch do.

        :raise psutil.Error: if the process is gone or cannot be read
        """
        with self._lock:
            root = Member(process.pid, process_utils.start_token(process), self._role_of_root(process))
            command = " ".join(process.cmdline())
            generation = (self._record.generation if self._record is not None else 0) + 1
            self._record = ProcessRecord(generation, backend, launch_path, command, adoption.session_name or "", root, (root,), True, adoption)
            self._save()

    def observe(self, listener: PortListener, console: Optional[Callable[[ProcessRecord], Optional[bool]]] = None) -> TreeView:
        """
        Revalidate the members, take in their new descendants and look at the port; the record follows what is found.

        :param console: tells whether the console of an active record is still there. It is asked before the members:
            a console goes away only after the processes in it, so one found gone while a member is found alive after it
            has really been lost, rather than closed in between
        """
        with self._lock:
            # before the members: a listener that shows up in between is then found among them, not taken for a stranger
            listeners = frozenset(listener.owners())
            record = self._record
            members: list[LiveMember] = []
            console_found: Optional[bool] = None
            if record is not None and record.active:
                if console is not None:
                    console_found = console(record)
                known = {member.pid for member in record.members}
                members = self._take_in_descendants(self._revalidate(record.members), record.root.pid)
                members = self._tell_server_apart(members, {live.member.pid for live in members} - known, listeners)
                updated = replace(record, members=tuple(live.member for live in members), active=bool(members))
                if updated != record:
                    self._record = record = updated
                    self._save()
            # a listener that has exited since is no stranger, but a member that is gone now, or nothing at all
            member_pids = {live.member.pid for live in members}
            listeners = frozenset(pid for pid in listeners if pid is None or pid in member_pids or psutil.pid_exists(pid))
            return TreeView(record, tuple(members), listeners, console_found)

    def live_processes(self) -> tuple[list[psutil.Process], bool]:
        """
        The recorded processes that are still alive, checked against their identities; nothing else is looked at, nothing is written.

        :return: them, and whether every process the record held at the last observation is among them
        """
        with self._lock:
            record = self._record
            if record is None or not record.active:
                return [], True
            live = self._revalidate(record.members)
            return [member.process for member in live], len(live) == len(record.members)

    @staticmethod
    def _revalidate(members: tuple[Member, ...]) -> list[LiveMember]:
        live = []
        for member in members:
            try:
                process = psutil.Process(member.pid)
                if process_utils.start_token(process) == member.token and process_utils.is_alive(process):
                    live.append(LiveMember(member, process))
            except psutil.Error:
                pass
        return live

    @classmethod
    def _take_in_descendants(cls, members: list[LiveMember], root_pid: int) -> list[LiveMember]:
        known = {live.member.pid for live in members}
        # breadth first, so that a role is decided from the parent's
        index = 0
        while index < len(members):
            parent = members[index]
            index += 1
            try:
                children = parent.process.children()
            except psutil.Error:
                continue
            for child in children:
                if child.pid in known:
                    continue
                try:
                    member = Member(child.pid, process_utils.start_token(child), cls._role_of_child(child, parent.member, root_pid))
                except psutil.Error:
                    continue
                if process_utils.is_alive(child):
                    known.add(child.pid)
                    members.append(LiveMember(member, child))
        return members

    @staticmethod
    def _tell_server_apart(members: list[LiveMember], new: set[int], listeners: frozenset[Optional[int]]) -> list[LiveMember]:
        """
        Mark which of the processes an MCDR launched is the server, and the others as other processes.

        The one the port listener descends from is the server for certain; failing that, the one already known,
        and failing that, a new one that MCDR's config describes as the server.
        """
        by_pid = {live.member.pid: live for live in members}
        mcdr = {pid for pid, live in by_pid.items() if live.member.role is Role.MCDR}
        # the child of an MCDR that each process descends from; parents come first
        branch: dict[int, int] = {}
        parents: dict[int, int] = {}
        for live in members:
            # the console host of an MCDR is neither the server nor another process of it
            if live.member.role in (Role.MCDR, Role.WRAPPER):
                continue
            try:
                parent = parents[live.member.pid] = live.process.ppid()
            except psutil.Error:
                continue
            if parent in mcdr:
                branch[live.member.pid] = live.member.pid
            elif parent in branch:
                branch[live.member.pid] = branch[parent]
        heads = set(branch.values())
        server = next((branch[pid] for pid in listeners if pid in branch), None)
        if server is None:
            server = next((pid for pid in heads if by_pid[pid].member.role is Role.SERVER), None)
        if server is None:
            server = next((
                pid for pid in heads & new if process_utils.is_server_of(by_pid[pid].process, by_pid[parents[pid]].process)
            ), None)
        if server is None:
            return members
        told_apart = []
        for live in members:
            head = branch.get(live.member.pid)
            role = live.member.role if head is None else Role.SERVER if head == server else Role.OTHER
            told_apart.append(live if role is live.member.role else LiveMember(replace(live.member, role=role), live.process))
        return told_apart

    @staticmethod
    def _role_of_root(process: psutil.Process) -> Role:
        if process_utils.is_mcdr(process):
            return Role.MCDR
        return Role.WRAPPER if process_utils.is_shell(process) else Role.OTHER

    @staticmethod
    def _role_of_child(process: psutil.Process, parent: Member, root_pid: int) -> Role:
        if process_utils.is_mcdr(process):
            return Role.MCDR
        # the console host of an MCDR that has a console of its own, which is the case of one started by hand on Windows
        if parent.role is Role.MCDR and process_utils.is_console_host(process):
            return Role.WRAPPER
        if parent.role is Role.MCDR:
            return Role.CHILD
        if parent.role in (Role.SERVER, Role.CHILD):
            return parent.role
        # only the shell a terminal opens and the console host of the root: a script the command runs is not one
        if parent.pid == root_pid and parent.role is Role.WRAPPER and process_utils.is_shell(process):
            return Role.WRAPPER
        return Role.OTHER

    def _load(self) -> Optional[ProcessRecord]:
        try:
            with open(self.path, encoding="utf8") as file:
                return ProcessRecord.from_json(json.load(file))
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, TypeError) as e:
            self._warn("unreadable", path=self.path, error=e)
            return None

    def _save(self) -> None:
        """Write the record; if that fails, it is kept in memory and lost on the next plugin reload."""
        assert self._record is not None
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf8") as file:
                json.dump(self._record.to_json(), file, indent=2)
            os.replace(temp_path, self.path)
        except OSError as e:
            self._warn("unwritable", path=self.path, error=e)
