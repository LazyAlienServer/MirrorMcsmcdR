import time
from threading import Lock
from typing import Optional, Sequence

from mirror_mcsmcdr.server.action import TERMINATIONS, Action, ActionResult, Intent
from mirror_mcsmcdr.server.backend.base import ServerBackend
from mirror_mcsmcdr.server.resolver import StatusResolver
from mirror_mcsmcdr.server.status import Evidence, ServerState, StatusSnapshot


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

    def execute(self, action: Action) -> ActionResult:
        with self._action_lock:
            # judged with the pending start or stop still in view: while starting, that is all some backends have
            result = ActionResult.check(action, self.status())
            backend = next((backend for backend in self.backends if action in backend.supports), None)
            if backend is None:
                return result.reject(ActionResult.Outcome.UNSUPPORTED)
            if not result.accepted:
                return result
            result = backend.perform(result)
            if result.accepted:
                if action in TERMINATIONS:
                    # nobody is waiting for the last start or stop any more
                    self._set_intent(None)
                else:
                    self._set_intent(Intent(action, time.monotonic() + self._timeouts[action]))
            return result

    def wait_for(self, state: ServerState, timeout: float, interval: float) -> StatusSnapshot:
        """
        Poll until the server is exactly in ``state``.

        :return: the last status observed, which is not in ``state`` if the timeout ran out
        """
        deadline = time.monotonic() + timeout
        while True:
            snapshot = self.status()
            remaining = deadline - time.monotonic()
            if snapshot.is_exactly(state) or remaining <= 0:
                return snapshot
            time.sleep(min(interval, remaining))

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
