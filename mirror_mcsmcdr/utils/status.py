from dataclasses import astuple, dataclass, replace
from enum import Enum
from typing import ClassVar, Optional


class ServerStatus(str, Enum):
    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STARTING = "starting"
    RUNNING = "running"
    DETACHED_JAVA = "detached_java"
    DETACHED_SCREEN = "detached_screen"
    RCON_STATUS_MISMATCH = "rcon_status_mismatch"
    UNAVAILABLE = "unavailable"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def is_available(cls, status: "ServerStatus") -> bool:
        return type(status) is cls and status in {
            cls.UNKNOWN,
            cls.STOPPED,
            cls.STOPPING,
            cls.STARTING,
            cls.RUNNING,
            cls.DETACHED_JAVA,
            cls.DETACHED_SCREEN,
        }


class ServerState(Enum):
    """Where the server is in its lifecycle; anything odd about it is an :class:`Anomaly` instead."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


class Anomaly(Enum):
    # the screen session is there, the server inside it is not
    ORPHAN_SCREEN = "orphan_screen"
    # the server is there, the screen session to control it is not
    ORPHAN_PROCESS = "orphan_process"
    # the terminal sees a server that RCON cannot reach
    PROBE_CONFLICT = "probe_conflict"


class Action(Enum):
    START = "start"
    STOP = "stop"
    KILL = "kill"
    FORCEKILL = "forcekill"


TERMINATIONS = frozenset({Action.KILL, Action.FORCEKILL})


@dataclass(frozen=True)
class Evidence:
    """What the backends observed; a field is None when no backend is able to observe it."""

    # the child process owned by the plugin
    process_alive: Optional[bool] = None
    port_listening: Optional[bool] = None
    screen_exists: Optional[bool] = None
    rcon_reachable: Optional[bool] = None
    panel_state: Optional[ServerState] = None

    def merge(self, other: "Evidence") -> "Evidence":
        """Fill the fields this evidence lacks with those of ``other``."""
        return Evidence(*(
            mine if mine is not None else theirs
            for mine, theirs in zip(astuple(self), astuple(other))
        ))

    @property
    def empty(self) -> bool:
        return self == Evidence()


@dataclass(frozen=True)
class Intent:
    """A start or stop the plugin has issued and that has not settled yet."""

    action: Action
    expires_at: float


@dataclass(frozen=True)
class StatusSnapshot:
    state: ServerState
    anomalies: frozenset[Anomaly]
    evidence: Evidence

    def is_exactly(self, state: ServerState) -> bool:
        """Whether the server is in ``state`` with nothing odd about it."""
        return self.state is state and not self.anomalies


@dataclass(frozen=True)
class ActionResult:
    """
    Whether an action goes ahead, first as the verdict of :meth:`check` and then as what the backend made of it.

    The snapshot is the one the verdict was based on, so a rejection can be explained without observing again.
    """

    class Outcome(Enum):
        ACCEPTED = "accepted"
        WRONG_STATE = "wrong_state"
        ANOMALY = "anomaly"
        UNSUPPORTED = "unsupported"
        PATH_NOT_FOUND = "path_not_found"
        TIMEOUT = "timeout"
        FORCE_REQUIRED = "force_required"

    action: Action
    snapshot: StatusSnapshot
    outcome: Outcome = Outcome.ACCEPTED

    ALLOWED_STATES: ClassVar[dict[Action, frozenset[ServerState]]] = {
        Action.START: frozenset({ServerState.STOPPED}),
        Action.STOP: frozenset({ServerState.RUNNING}),
        Action.KILL: frozenset({ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING}),
        Action.FORCEKILL: frozenset({ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING}),
    }

    @classmethod
    def check(cls, action: Action, snapshot: StatusSnapshot) -> "ActionResult":
        result = cls(action, snapshot)
        if snapshot.anomalies:
            # an anomaly can only be cleaned up, whatever the state says
            return result if action in TERMINATIONS else result.reject(cls.Outcome.ANOMALY)
        if snapshot.state in cls.ALLOWED_STATES[action]:
            return result
        return result.reject(cls.Outcome.WRONG_STATE)

    def reject(self, outcome: Outcome) -> "ActionResult":
        return replace(self, outcome=outcome)

    @property
    def accepted(self) -> bool:
        return self.outcome is self.Outcome.ACCEPTED
