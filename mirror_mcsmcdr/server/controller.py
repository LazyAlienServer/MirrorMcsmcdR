import time
from dataclasses import dataclass, replace
from enum import Enum
from threading import Lock
from typing import Callable, Optional, Sequence

import psutil

from mirror_mcsmcdr.server.action import TERMINATIONS, Action, ActionResult, Intent
from mirror_mcsmcdr.server.backend.base import KillTargets, ProcessIdentity, ServerBackend, TerminalProxy
from mirror_mcsmcdr.server.resolver import StatusResolver
from mirror_mcsmcdr.server.status import Evidence, Origin, ProcessInfo, ServerState, StatusSnapshot
from mirror_mcsmcdr.server.system_utils import process_utils


class WaitEnd(Enum):
    REACHED = "reached"
    # the status is one that waiting longer would not change
    GAVE_UP = "gave_up"
    TIMEOUT = "timeout"
    # nobody waits for the result any more; the snapshot is the last one taken before
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class WaitResult:
    end: WaitEnd
    # the last status observed
    snapshot: StatusSnapshot


class RecoverOutcome(Enum):
    ADOPTED = "adopted"
    # no backend tracks processes
    UNSUPPORTED = "unsupported"
    # the record still holds live processes
    TRACKED = "tracked"
    NONE_FOUND = "none_found"
    # several were found, and none was picked by pid
    AMBIGUOUS = "ambiguous"
    # the pid picked is not among those found
    NOT_FOUND = "not_found"
    # the port is held by something outside the one found, which adopting it would leave out
    FOREIGN_LISTENER = "foreign_listener"
    # it exited while it was being adopted
    GONE = "gone"


@dataclass(frozen=True)
class RecoverResult:
    outcome: RecoverOutcome
    # the MCDR instances (Java processes for a plain server) found outside the record
    found: tuple[ProcessInfo, ...] = ()
    # the one picked, adopted or to be adopted
    picked: Optional[ProcessInfo] = None
    # whether the console of the one adopted was found; False also before it is adopted
    console: bool = False
    # of a dry run that would adopt: the one picked, to be passed back once that is confirmed
    identity: Optional[ProcessIdentity] = None

    @property
    def ok(self) -> bool:
        return self.outcome is RecoverOutcome.ADOPTED


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

    def status(self, scan: bool = False) -> StatusSnapshot:
        """
        :param scan: also look among all processes for the mirror running outside the record, while nothing tracked is alive.
            It costs a look at every process of the machine: for decisions only, never while waiting
        """
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
        if scan and evidence.panel_state is None and evidence.port_listening is not None and not evidence.members_alive:
            terminal = self._terminal()
            if terminal is not None:
                untracked = tuple(process_utils.describe(process, Origin.UNTRACKED) for process in terminal.find_untracked())
                evidence = replace(evidence, untracked=untracked)
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
        # judged with the pending start or stop still in view: while starting, that is all some backends have.
        # A start looks for a mirror running outside the record, which a launch would run beside.
        result = ActionResult.check(action, self.status(scan=action is Action.START))
        backend = next((backend for backend in self.backends if action in backend.supports), None)
        if backend is None:
            return result.reject(ActionResult.Outcome.UNSUPPORTED), None
        return result, backend

    def execute(self, action: Action, listed: Optional[frozenset[ProcessIdentity]] = None) -> ActionResult:
        """:param listed: for a forced kill, the processes shown to the operator beforehand; it ends none but these"""
        with self._action_lock:
            result, backend = self._judge(action)
            if backend is None or not result.accepted:
                return result
            result = backend.perform(result, listed)
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
        terminal = self._terminal()
        return terminal.forcekill_targets() if terminal is not None else None

    def recover(self, pid: Optional[int], dry_run: bool = False, shown: Optional[ProcessIdentity] = None) -> RecoverResult:
        """
        Adopt the mirror's MCDR (a plain server's Java process) that runs outside the record, such as one started by hand:
        from then on it is tracked as if launched.

        :param pid: the one to adopt among those found; None if there is to be exactly one
        :param dry_run: only tell whether it would be adopted, as ADOPTED if so
        :param shown: the identity a dry run gave, after it was shown to the operator: this one is adopted or none,
            GONE if it is not found as it was. It overrides ``pid``
        """
        with self._action_lock:
            terminal = self._terminal()
            if terminal is None:
                return RecoverResult(RecoverOutcome.UNSUPPORTED)
            if self.status().evidence.members_alive:
                return RecoverResult(RecoverOutcome.TRACKED)
            processes = terminal.find_untracked()
            found = tuple(process_utils.describe(process, Origin.UNTRACKED) for process in processes)
            if not processes:
                return RecoverResult(RecoverOutcome.NONE_FOUND)
            if shown is not None:
                process = next((process for process in processes if process.pid == shown[0]), None)
                try:
                    if process is None or process_utils.start_token(process) != shown[1]:
                        return RecoverResult(RecoverOutcome.GONE, found)
                except psutil.Error:
                    return RecoverResult(RecoverOutcome.GONE, found)
            else:
                if pid is None and len(processes) > 1:
                    return RecoverResult(RecoverOutcome.AMBIGUOUS, found)
                process = next((process for process in processes if pid is None or process.pid == pid), None)
                if process is None:
                    return RecoverResult(RecoverOutcome.NOT_FOUND, found)
            picked = process_utils.describe(process, Origin.PICKED)
            try:
                if not terminal.holds_port(process):
                    return RecoverResult(RecoverOutcome.FOREIGN_LISTENER, found, picked)
                if dry_run:
                    identity = (process.pid, process_utils.start_token(process))
                    return RecoverResult(RecoverOutcome.ADOPTED, found, picked, identity=identity)
                adoption = terminal.adopt(process)
            except psutil.Error:
                return RecoverResult(RecoverOutcome.GONE, found, picked)
            # a start or stop issued before is not what the adopted mirror is doing
            self._set_intent(None)
            return RecoverResult(RecoverOutcome.ADOPTED, found, replace(picked, origin=Origin.ADOPTED), adoption.console is not None)

    def _terminal(self) -> Optional[TerminalProxy]:
        """The backend that runs the forced kill, which is the one that tracks the processes."""
        backend = next((backend for backend in self.backends if Action.FORCEKILL in backend.supports), None)
        return backend if isinstance(backend, TerminalProxy) else None

    def wait_until(
        self,
        until: Callable[[StatusSnapshot], bool],
        timeout: float,
        interval: float,
        give_up: Callable[[StatusSnapshot], bool] = lambda _: False,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> WaitResult:
        """
        Wait until the status satisfies ``until``.

        Every decision is made on a full status. In between, a backend watches for a change that is cheap to see,
        for ``interval`` at most, so that the next status is taken as soon as something has happened.

        :param give_up: tells a status that waiting longer would not change
        :param cancelled: tells, before each status after the first, that nobody waits for the result any more
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
            if cancelled():
                return WaitResult(WaitEnd.CANCELLED, snapshot)

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
