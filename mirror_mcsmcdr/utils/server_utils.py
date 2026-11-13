import platform
import time
from threading import Lock
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from mcdreforged.api.all import Serializable

from mirror_mcsmcdr.config import MirrorConfig, TerminalConfig
from mirror_mcsmcdr.utils.proxy.backend import ServerBackend
from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxy
from mirror_mcsmcdr.utils.proxy.rcon_proxy import RConProxy
from mirror_mcsmcdr.utils.proxy.subprocess_proxy import SubprocessProxy
from mirror_mcsmcdr.utils.proxy.system_proxy import LinuxProxy, TerminalProxy, WindowsProxy
from mirror_mcsmcdr.utils.status import TERMINATIONS, Action, ActionResult, Evidence, Intent, ServerState, StatusSnapshot
from mirror_mcsmcdr.utils.status_resolver import StatusResolver


class ProxySettingException(Exception):

    def __init__(self, proxy: str, missing_keys: List[str]):
        super().__init__("Proxy '{}' has the incorrect key(s) '{}'".format(proxy, "', '".join(missing_keys)))
        self.proxy = proxy
        self.missing_keys = missing_keys


def _require(proxy: str, config: Serializable, keys: Sequence[str]) -> None:
    missing_keys = [key for key in keys if not getattr(config, key)]
    if missing_keys:
        raise ProxySettingException(proxy, missing_keys)


def _build_terminal(config: TerminalConfig) -> TerminalProxy:
    terminal_types: Dict[str, Callable[[TerminalConfig], TerminalProxy]] = {"linux": LinuxProxy, "windows": WindowsProxy, "subprocess": SubprocessProxy}
    terminal_type = terminal_types.get(config.proxy_type or platform.system().lower())
    if terminal_type is None:
        raise ProxySettingException("terminal", ["proxy_type"])
    _require("terminal", config, ["launch_path", "launch_command"] + ([] if terminal_type is SubprocessProxy else ["port"]))
    return terminal_type(config)


def build_backends(config: MirrorConfig) -> Tuple[List[ServerBackend], List[ProxySettingException]]:
    """
    Build the backends the config enables, in the order they are preferred for an action.

    :return: the backends, and an error for each enabled one that could not be set up
    """
    def build_mcsm() -> ServerBackend:
        _require("mcsm", config.mcsm, ["url", "uuid", "remote_uuid", "apikey"])
        return MCSManagerProxy(config.mcsm)

    def build_rcon() -> ServerBackend:
        _require("rcon", config.rcon, ["address", "port", "password"])
        return RConProxy(config.rcon)

    builders: Tuple[Tuple[bool, Callable[[], ServerBackend]], ...] = (
        (config.mcsm.enable, build_mcsm),
        (config.rcon.enable, build_rcon),
        (config.terminal.enable, lambda: _build_terminal(config.terminal)),
    )
    backends: List[ServerBackend] = []
    errors: List[ProxySettingException] = []
    for enabled, build in builders:
        if not enabled:
            continue
        try:
            backends.append(build())
        except ProxySettingException as e:
            errors.append(e)
    return backends, errors


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
        snapshot = StatusResolver.resolve(evidence, intent.action if intent is not None else None)
        if intent is not None and snapshot.state is not self._PENDING_STATES[intent.action]:
            self._settle(intent)
        return snapshot

    def execute(self, action: Action) -> ActionResult:
        if action in TERMINATIONS:
            # whatever becomes of it, nobody is waiting for the last start or stop any more
            self._set_intent(None)
        result = ActionResult.check(action, self.status())
        backend = next((backend for backend in self.backends if action in backend.supports), None)
        if backend is None:
            return result.reject(ActionResult.Outcome.UNSUPPORTED)
        if not result.accepted:
            return result
        result = backend.perform(result)
        if result.accepted and action in self._timeouts:
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
