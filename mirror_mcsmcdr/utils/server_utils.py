from typing import List, Union, Optional, Literal
import platform

from mcdreforged.api.all import PluginServerInterface

from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxy
from mirror_mcsmcdr.utils.proxy.rcon_proxy import RConProxy
from mirror_mcsmcdr.utils.proxy.subprocess_proxy import SubprocessProxy
from mirror_mcsmcdr.utils.proxy.system_proxy import AbstractSystemProxy, LinuxProxy, WindowsProxy
from mirror_mcsmcdr.utils.status import ServerStatus


class ProxySettingException(Exception):

    def __init__(self, proxy: str, missing_keys: List[str]):
        super().__init__("Proxy '{}' has the incorrect key(s) '{}'".format(proxy, "', '".join(missing_keys)))
        self.proxy = proxy
        self.missing_keys = missing_keys


class TerminalSettingException(Exception):

    def __init__(self, system: Optional[str]) -> None:
        super().__init__("Unavailable system '%s'" % system)
        self.system = system


class ServerProxy:

    def __init__(self) -> None:
        self.proxies = ["mcsm", "rcon", "terminal"]
        self.mcsm: Union[MCSManagerProxy, Literal[False, None]] = None
        self.rcon: Union[RConProxy, Literal[False, None]] = None
        self.terminal: Union[AbstractSystemProxy, Literal[False, None]] = None

    def set_mcsm(self, enable, **kwargs):
        if not enable:
            return
        if not sum(map(lambda x: not bool(x), kwargs.values())):
            self.mcsm = MCSManagerProxy(enable, **kwargs)
            return
        self.mcsm = False
        raise ProxySettingException("mcsm", [key for key, value in kwargs.items() if not bool(value)])

    def set_rcon(self, enable, **kwargs):
        if not enable:
            return
        if not sum(map(lambda x: not bool(x), kwargs.values())):
            self.rcon = RConProxy(**kwargs)
            return
        self.rcon = False
        raise ProxySettingException("rcon", [key for key, value in kwargs.items() if not bool(value)])

    def set_terminal(
        self,
        enable,
        regex_strict: bool,
        is_mcdr: bool = True,
        proxy_type: Optional[str] = None,
        console_log: bool = False,
        server: Optional[PluginServerInterface] = None,
        **kwargs,
    ):
        if not enable:
            return

        terminal_name = kwargs.get("terminal_name") or "Mirror"
        path = kwargs.get("path", kwargs.get("launch_path"))
        command = kwargs.get("command", kwargs.get("launch_command"))

        normalized_proxy_type = proxy_type.lower() if isinstance(proxy_type, str) else proxy_type
        if normalized_proxy_type is None:
            normalized_proxy_type = platform.system().lower()

        required_values = {"path": path, "command": command}
        if normalized_proxy_type != "subprocess":
            required_values["port"] = kwargs.get("port")
        missing_keys = [key for key, value in required_values.items() if not bool(value)]
        invalid_keys = missing_keys
        if type(regex_strict) != bool:
            invalid_keys.append("regex_strict")
        if type(is_mcdr) != bool:
            invalid_keys.append("is_mcdr")
        if invalid_keys:
            self.terminal = False
            raise ProxySettingException("terminal", invalid_keys)

        match normalized_proxy_type:
            case "linux":
                self.terminal = LinuxProxy(
                    terminal_name,
                    path,
                    command,
                    kwargs.get("port"),
                    regex_strict,
                    is_mcdr,
                )
                return
            case "windows":
                self.terminal = WindowsProxy(
                    terminal_name,
                    path,
                    command,
                    kwargs.get("port"),
                    regex_strict,
                    is_mcdr,
                )
                return
            case "subprocess":
                self.terminal = SubprocessProxy(
                    terminal_name=terminal_name,
                    path=path,
                    command=command,
                    port=kwargs.get("port"),
                    regex_strict=regex_strict,
                    is_mcdr=is_mcdr,
                    console_log=console_log,
                    server=server,
                )
                return
            case _:
                raise ProxySettingException("terminal", ["proxy_type"])

    def status(self) -> ServerStatus:
        if self.mcsm:
            return self.mcsm.status()
        if self.rcon:
            status = self.rcon.status()
            if status == ServerStatus.STOPPED and self.terminal:
                status_sys = self.terminal.status()
                if status_sys in (ServerStatus.DETACHED_JAVA, ServerStatus.DETACHED_SCREEN):
                    return status_sys
                return ServerStatus.STOPPED if status_sys == ServerStatus.STOPPED else ServerStatus.RCON_STATUS_MISMATCH
            return status
        return self.terminal.status() if self.terminal else ServerStatus.UNAVAILABLE

    def start(self):
        if self.mcsm:
            return self.mcsm.start()
        if self.terminal:
            return self.terminal.start()
        return ServerStatus.UNAVAILABLE

    def stop(self):
        if self.mcsm:
            return self.mcsm.stop()
        if self.rcon:
            return self.rcon.stop()
        if self.terminal:
            return self.terminal.stop()
        return ServerStatus.UNAVAILABLE

    def kill(self):
        if self.mcsm:
            return self.mcsm.kill()
        if self.terminal:
            return self.terminal.kill()
        return ServerStatus.UNAVAILABLE

    def forcekill(self):
        if self.terminal and isinstance(self.terminal, AbstractSystemProxy):
            return self.terminal.forcekill()
        return ServerStatus.UNAVAILABLE
