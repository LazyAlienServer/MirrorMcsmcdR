from dataclasses import astuple, dataclass
from enum import Enum
from typing import Optional


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
class StatusSnapshot:
    state: ServerState
    anomalies: frozenset[Anomaly]
    evidence: Evidence

    def is_exactly(self, state: ServerState) -> bool:
        """Whether the server is in ``state`` with nothing odd about it."""
        return self.state is state and not self.anomalies

    @property
    def label(self) -> str:
        """The name of what matters most about this status: an anomaly if there is one, otherwise the state."""
        for anomaly in Anomaly:
            if anomaly in self.anomalies:
                return anomaly.value
        return self.state.value
