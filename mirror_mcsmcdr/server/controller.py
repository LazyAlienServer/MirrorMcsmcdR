import time
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import Callable, Optional, Sequence

from mirror_mcsmcdr.server.action import TERMINATIONS, Action, ActionResult, Intent
from mirror_mcsmcdr.server.backend.base import KillTargets, ServerBackend, TerminalProxy
from mirror_mcsmcdr.server.resolver import StatusResolver
from mirror_mcsmcdr.server.status import Evidence, ServerState, StatusSnapshot


class WaitEnd(Enum):
    REACHED = "reached"
    # the status is one that waiting longer would not change
    GAVE_UP = "gave_up"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class WaitResult:
    end: WaitEnd
    # the last status observed
    snapshot: StatusSnapshot


class ServerController:
    """Observes and controls one server through its backends."""

    # the state a start or stop goes through until it has settled
    _PENDING_STATES = {Action.START: ServerState.STARTING, Action.STOP: ServerState.STOPPING}

    def __init__(self, backends: Sequence[ServerBackend], start_timeout: float, stop_timeout: float) -> None:
        """
        :param backends: in order of preference; an action goes to the first backend that supports it
        :param start_timeout: how long a start may take before the server is judged by evidence alone again
        :param stop_timeout: the same for a stop
        """
        self.backends = tuple(backends)
        self._timeouts = {Action.START: start_timeout, Action.STOP: stop_timeout}
        self._intent: Optional[Intent] = None
        self._lock = Lock()
        # one action at a time, so that an older action cannot record its intent over a newer one
        self._action_lock = Lock()

    def _set_intent(self, intent: Optional[Intent]) -> None:
        with self._lock:
            self._intent = intent

    def _settle(self, intent: Intent) -> None:
        with self._lock:
            # a newer intent may have been issued since this one was read
            if self._intent is intent:
                self._intent = None

    def status(self) -> StatusSnapshot:
        # read before observing, so that evidence never gets combined with an intent issued after it
        intent = self._intent
        if intent is not None and time.monotonic() >= intent.expires_at:
            self._settle(intent)
            intent = None

        evidence = Evidence()
        for backend in self.backends:
            evidence = evidence.merge(backend.observe())
            # the panel settles the status on its own; the remaining backends need not be reachable
            if evidence.panel_state is not None:
                break
        snapshot = StatusResolver.resolve(evidence, intent.action if intent is not None else None)
        if intent is not None and snapshot.state is not self._PENDING_STATES[intent.action]:
            self._settle(intent)
        return snapshot

    def check(self, action: Action) -> ActionResult:
        """What :meth:`execute` would decide now, without carrying the action out; the status may change before it runs."""
        result, _ = self._judge(action)
        return result

    def _judge(self, action: Action) -> tuple[ActionResult, Optional[ServerBackend]]:
        """The verdict on ``action`` for the status now, and the backend that would carry it out."""
        # judged with the pending start or stop still in view: while starting, that is all some backends have
        result = ActionResult.check(action, self.status())
        backend = next((backend for backend in self.backends if action in backend.supports), None)
        if backend is None:
            return result.reject(ActionResult.Outcome.UNSUPPORTED), None
        return result, backend

    def execute(self, action: Action) -> ActionResult:
        with self._action_lock:
            result, backend = self._judge(action)
            if backend is None or not result.accepted:
                return result
            result = backend.perform(result)
            if result.outcome is ActionResult.Outcome.CONSOLE_INPUT_FAILED:
                again = ActionResult.check(action, self.status())
                if (again.snapshot.state, again.snapshot.anomalies) == (result.snapshot.state, result.snapshot.anomalies):
                    # nothing has changed since the check: the input itself failed
                    result = again.reject(ActionResult.Outcome.CONSOLE_INPUT_FAILED)
                else:
                    # The status now explains it, also where it allows the action:
                    # that would be carried out differently, by a launch or another command.
                    result = again if not again.accepted else again.reject(ActionResult.Outcome.WRONG_STATE)
            if result.accepted:
                if action in TERMINATIONS:
                    # nobody is waiting for the last start or stop any more
                    self._set_intent(None)
                else:
                    self._set_intent(Intent(action, time.monotonic() + self._timeouts[action]))
            return result

    def forcekill_targets(self) -> Optional[KillTargets]:
        """What a forced kill would end; None if no backend can tell."""
        backend = next((backend for backend in self.backends if Action.FORCEKILL in backend.supports), None)
        return backend.forcekill_targets() if isinstance(backend, TerminalProxy) else None

    def wait_until(
        self,
        until: Callable[[StatusSnapshot], bool],
        timeout: float,
        interval: float,
        give_up: Callable[[StatusSnapshot], bool] = lambda _: False,
    ) -> WaitResult:
        """
        Wait until the status satisfies ``until``.

        Every decision is made on a full status. In between, a backend watches for a change that is cheap to see,
        for ``interval`` at most, so that the next status is taken as soon as something has happened.

        :param give_up: tells a status that waiting longer would not change
        """
        # the terminal sees processes exit; the panel has nothing to watch but time
        watcher = next((backend for backend in self.backends if isinstance(backend, TerminalProxy)), self.backends[0])
        deadline = time.monotonic() + timeout
        while True:
            snapshot = self.status()
            if until(snapshot):
                return WaitResult(WaitEnd.REACHED, snapshot)
            if give_up(snapshot):
                return WaitResult(WaitEnd.GAVE_UP, snapshot)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return WaitResult(WaitEnd.TIMEOUT, snapshot)
            watcher.watch(min(interval, remaining))

    def is_starting(self) -> bool:
        """Whether a start issued through this controller is still settling."""
        intent = self._intent
        if intent is None or intent.action is not Action.START:
            return False
        try:
            return self.status().state is ServerState.STARTING
        except Exception:
            # an unreachable backend must not block the reload of the config that would fix it
            return False
