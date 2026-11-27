from dataclasses import dataclass, fields
from enum import Enum
from typing import Optional


class ServerState(Enum):
    """Where the server is in its lifecycle; anything odd about it is an :class:`Anomaly` instead."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    # the server is gone, the MCDR that ran it is not: MCDR is idle, or still exiting
    MCDR_ONLY = "mcdr_only"
    UNKNOWN = "unknown"


class Anomaly(Enum):
    # the terminal or shell the mirror was launched from is left, nothing it launched is
    ORPHAN_SCREEN = "orphan_screen"
    # processes the plugin launched are alive, the console to control them is not
    ORPHAN_PROCESS = "orphan_process"
    # the mirror is run by MCDR, yet none of its processes is an MCDR instance
    MCDR_MISSING = "mcdr_missing"


class Capability(Enum):
    # a new process tree may be launched
    TERMINAL_LAUNCH = "terminal_launch"
    # the console of the tracked processes takes input
    CONSOLE_INPUT = "console_input"
    # tracked processes are alive to be killed
    TREE_KILL = "tree_kill"


class Detail(Enum):
    """Why the status is what it is; every status but a plain running or stopped one has one."""

    # whatever the panel reports
    PANEL = "panel"
    FOREIGN_LISTENER = "foreign_listener"
    # nothing tracked is alive, but an MCDR (a Java process for a plain server) the record does not hold runs in the launch path
    UNTRACKED = "untracked"
    START_PENDING = "start_pending"
    # the server is there without a start of the plugin pending, yet the port stays closed: it is starting, or going unseen
    PORT_CLOSED = "port_closed"
    # the server had the port open, and has closed it while it runs on: it is on its way out
    PORT_RELEASED = "port_released"
    STOP_PENDING = "stop_pending"
    # only the terminal is left, and it is going
    CONSOLE_CLOSING = "console_closing"
    MCDR_ONLY = "mcdr_only"
    ORPHAN_SCREEN = "orphan_screen"
    ORPHAN_PROCESS = "orphan_process"
    MCDR_MISSING = "mcdr_missing"


class Origin(Enum):
    """How a process came to be reported, as far as the record goes."""

    # in the record, after the plugin launched it
    LAUNCHED = "launched"
    # in the record, after the plugin adopted it
    ADOPTED = "adopted"
    # not in the record yet, about to be adopted
    PICKED = "picked"
    UNTRACKED = "untracked"


@dataclass(frozen=True)
class ProcessInfo:
    """A process as it is reported; the command line is for the console only."""

    # None for a process whose pid cannot be read, such as a listener of another user
    pid: Optional[int]
    name: str
    cmdline: str
    origin: Origin


@dataclass(frozen=True)
class Evidence:
    """What the backends observed; a field is None when no backend is able to observe it."""

    # whether anything listens on the configured port
    port_listening: Optional[bool] = None
    # listeners of the configured port that are not processes the plugin launched
    foreign_listeners: Optional[tuple[ProcessInfo, ...]] = None
    # the tracked processes alive, by role; None for MCDR when the mirror is not run by MCDR
    mcdr_alive: Optional[bool] = None
    server_alive: Optional[bool] = None
    # whether a tracked process still alive has been seen listening on the port before
    server_listened: Optional[bool] = None
    # tracked processes that are neither MCDR, the server, nor what launched them
    others_alive: Optional[bool] = None
    # the terminal and shell the mirror was launched from
    wrapper_alive: Optional[bool] = None
    # whether the console the plugin controls the tracked processes through is still there
    endpoint_alive: Optional[bool] = None
    panel_state: Optional[ServerState] = None
    # for the details of the status: the configured port and the processes behind the counts above
    port: Optional[int] = None
    mcdr_process: Optional[ProcessInfo] = None
    # the port listener among them if there is one
    server_process: Optional[ProcessInfo] = None
    # what MCDR launched while the server is not told apart from the rest
    child_processes: Optional[tuple[ProcessInfo, ...]] = None
    others_count: Optional[int] = None
    # MCDR instances (Java processes for a plain server) in the launch path that the record does not hold;
    # looked for only on request, while nothing tracked is alive
    untracked: Optional[tuple[ProcessInfo, ...]] = None

    def merge(self, other: "Evidence") -> "Evidence":
        """Fill the fields this evidence lacks with those of ``other``."""
        return Evidence(**{
            field.name: mine if (mine := getattr(self, field.name)) is not None else getattr(other, field.name)
            for field in fields(self)
        })

    @property
    def empty(self) -> bool:
        return self == Evidence()

    @property
    def members_alive(self) -> bool:
        return any((self.mcdr_alive, self.server_alive, self.others_alive, self.wrapper_alive))


@dataclass(frozen=True)
class StatusSnapshot:
    state: ServerState
    anomalies: frozenset[Anomaly]
    evidence: Evidence
    detail: Optional[Detail] = None

    def is_exactly(self, state: ServerState) -> bool:
        """Whether the server is in ``state`` with nothing odd about it."""
        return self.state is state and not self.anomalies

    def safe_to_modify(self) -> bool:
        """Whether the files of the mirror may be changed: nothing of it is running."""
        return self.is_exactly(ServerState.STOPPED)

    def capabilities(self) -> frozenset[Capability]:
        """What the plugin can do with the processes it launched, as far as the terminal observed them."""
        evidence = self.evidence
        if evidence.port_listening is None:
            # nothing launched by the plugin was looked at
            return frozenset()
        capabilities = set()
        if self.is_exactly(ServerState.STOPPED):
            capabilities.add(Capability.TERMINAL_LAUNCH)
        console_reader = evidence.mcdr_alive if evidence.mcdr_alive is not None else evidence.server_alive
        if evidence.endpoint_alive and console_reader:
            capabilities.add(Capability.CONSOLE_INPUT)
        if evidence.members_alive:
            capabilities.add(Capability.TREE_KILL)
        return frozenset(capabilities)

    @property
    def label(self) -> str:
        """The name of what matters most about this status: an anomaly if there is one, otherwise the state."""
        for anomaly in Anomaly:
            if anomaly in self.anomalies:
                return anomaly.value
        return self.state.value
