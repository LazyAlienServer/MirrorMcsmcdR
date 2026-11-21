import platform
import re
from typing import Callable, Dict, List, Sequence, Tuple

from mcdreforged.api.all import Serializable

from mirror_mcsmcdr.config import MirrorConfig
from mirror_mcsmcdr.server.backend.base import ServerBackend, TerminalProxy
from mirror_mcsmcdr.server.backend.child_process import SubprocessProxy
from mirror_mcsmcdr.server.backend.linux import LinuxProxy
from mirror_mcsmcdr.server.backend.mcsm import MCSManagerProxy
from mirror_mcsmcdr.server.backend.windows import WindowsProxy
from mirror_mcsmcdr.server.system_utils.screen_utils import ScreenError
from mirror_mcsmcdr.server.tracker import ProcessTracker


class ProxySettingException(Exception):

    def __init__(self, proxy: str, missing_keys: List[str]):
        super().__init__("Proxy '{}' has the incorrect key(s) '{}'".format(proxy, "', '".join(missing_keys)))
        self.proxy = proxy
        self.missing_keys = missing_keys


def _require(proxy: str, config: Serializable, keys: Sequence[str]) -> None:
    missing_keys = [key for key in keys if not getattr(config, key)]
    if missing_keys:
        raise ProxySettingException(proxy, missing_keys)


def _build_terminal(config: MirrorConfig, tracker: ProcessTracker) -> TerminalProxy:
    terminal_types: Dict[str, Callable[[MirrorConfig, ProcessTracker], TerminalProxy]] = {"linux": LinuxProxy, "windows": WindowsProxy, "subprocess": SubprocessProxy}
    terminal_type = terminal_types.get(config.terminal.proxy_type or platform.system().lower())
    if terminal_type is None:
        raise ProxySettingException("terminal", ["proxy_type"])
    _require("terminal", config.terminal, ["launch_command", "port"])
    try:
        return terminal_type(config, tracker)
    except ScreenError as e:
        # the only thing a screen can refuse before it is used is its name
        raise ProxySettingException("terminal", ["terminal_name"]) from e
    except re.error as e:
        raise ProxySettingException("terminal", ["java_name"]) from e


def build_backends(config: MirrorConfig, tracker: ProcessTracker) -> Tuple[List[ServerBackend], List[ProxySettingException]]:
    """
    Build the backends the config enables, in the order they are preferred for an action.

    :param tracker: what the terminal records its launches in; it outlives the backends
    :return: the backends, and an error for each enabled one that could not be set up
    """
    def build_mcsm() -> ServerBackend:
        _require("mcsm", config.mcsm, ["url", "uuid", "remote_uuid", "apikey"])
        return MCSManagerProxy(config.mcsm)

    builders: Tuple[Tuple[bool, Callable[[], ServerBackend]], ...] = (
        (config.mcsm.enable, build_mcsm),
        (config.terminal.enable, lambda: _build_terminal(config, tracker)),
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
