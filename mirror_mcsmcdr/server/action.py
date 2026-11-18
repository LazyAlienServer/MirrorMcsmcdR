from dataclasses import dataclass, replace
from enum import Enum
from typing import ClassVar

from mirror_mcsmcdr.server.status import Anomaly, ServerState, StatusSnapshot


class Action(Enum):
    START = "start"
    STOP = "stop"
    KILL = "kill"
    FORCEKILL = "forcekill"


TERMINATIONS = frozenset({Action.KILL, Action.FORCEKILL})


@dataclass(frozen=True)
class Intent:
    """A start or stop the plugin has issued and that has not settled yet."""

    action: Action
    expires_at: float


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
        # a forced kill found nothing to kill
        NO_TARGET = "no_target"
        # a forced kill was refused: something holds the port whose pid cannot be read
        UNREADABLE_LISTENER = "unreadable_listener"
        # the console did not take the input, although the status still allows the action
        CONSOLE_INPUT_FAILED = "console_input_failed"

    action: Action
    snapshot: StatusSnapshot
    outcome: Outcome = Outcome.ACCEPTED

    ALLOWED_STATES: ClassVar[dict[Action, frozenset[ServerState]]] = {
        # in MCDR_ONLY, through the console of the MCDR that is still there
        Action.START: frozenset({ServerState.STOPPED, ServerState.MCDR_ONLY}),
        Action.STOP: frozenset({ServerState.RUNNING, ServerState.MCDR_ONLY}),
        Action.KILL: frozenset({ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING, ServerState.MCDR_ONLY}),
        # the way out of a status that cannot be told
        Action.FORCEKILL: frozenset({
            ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING, ServerState.MCDR_ONLY, ServerState.UNKNOWN,
        }),
    }

    @classmethod
    def check(cls, action: Action, snapshot: StatusSnapshot) -> "ActionResult":
        result = cls(action, snapshot)
        if snapshot.anomalies:
            # an anomaly can only be cleaned up, whatever the state says; without a console, only by force
            allowed = {Action.FORCEKILL} if Anomaly.ORPHAN_PROCESS in snapshot.anomalies else TERMINATIONS
            return result if action in allowed else result.reject(cls.Outcome.ANOMALY)
        if snapshot.state in cls.ALLOWED_STATES[action]:
            return result
        return result.reject(cls.Outcome.WRONG_STATE)

    def reject(self, outcome: Outcome) -> "ActionResult":
        return replace(self, outcome=outcome)

    @property
    def accepted(self) -> bool:
        return self.outcome is self.Outcome.ACCEPTED
