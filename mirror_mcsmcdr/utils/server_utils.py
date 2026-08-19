from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxy
from mirror_mcsmcdr.utils.proxy.rcon_proxy import RConProxy
from mirror_mcsmcdr.utils.proxy.system_proxy import SystemProxy, LinuxProxy, WindowsProxy
import platform
from typing import List, Union, Optional, Literal
from mirror_mcsmcdr.utils.status import ServerStatus

class ProxySettingException(Exception):

    def __init__(self, proxy: str, missing_keys: List[str]):
        super().__init__("Proxy '{}' has the incorrect key(s) '{}'".format(proxy, "', '".join(missing_keys)))
        self.proxy = proxy
        self.missing_keys = missing_keys

class TerminalSettingException(Exception):

    def __init__(self, system: str) -> None:
        super().__init__("Unavailable system '%s'"%system)
        self.system = system

class ServerProxy:

    def __init__(self) -> None:
        self.proxies = ["mcsm", "rcon", "terminal"]
        self.mcsm : Union[MCSManagerProxy, Literal[False, None]] = None
        self.rcon : Union[RConProxy, Literal[False, None]] = None
        self.terminal : Union[SystemProxy, Literal[False, None]] = None
    
    def set_mcsm(self, enable, **kwargs):
        if enable and not sum(map(lambda x : not bool(x), kwargs.values())):
            self.mcsm = MCSManagerProxy(enable, **kwargs)
            return True
        if enable:
            self.mcsm = False
            raise ProxySettingException("mcsm", [key for key, value in kwargs.items() if not bool(value)])

    
    def set_rcon(self, enable, **kwargs):
        if enable and not sum(map(lambda x : not bool(x), kwargs.values())):
            self.rcon = RConProxy(**kwargs)
            return True
        if enable:
            self.rcon = False
            raise ProxySettingException("rcon", [key for key, value in kwargs.items() if not bool(value)])
        
    
    def set_terminal(self, enable, regex_strict: bool, is_mcdr: bool = True, system: Optional[str] = None, **kwargs):
        missing_keys = [key for key, value in kwargs.items() if not bool(value)]
        if enable and not missing_keys and type(regex_strict) == bool and type(is_mcdr) == bool:
            if not system:
                system = platform.system()
                if system not in ["Linux", "Windows"]:
                    self.terminal = False
                    raise TerminalSettingException(system)
            self.terminal = SystemProxy(**kwargs, regex_strict = regex_strict, is_mcdr = is_mcdr, system = system)
            return True
        if enable:
            self.terminal = False
            invalid_keys = missing_keys
            if type(regex_strict) != bool:
                invalid_keys.append("regex_strict")
            if type(is_mcdr) != bool:
                invalid_keys.append("is_mcdr")
            raise ProxySettingException("terminal", invalid_keys)
    
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
        if self.terminal and isinstance(self.terminal.system_api, LinuxProxy):
            return self.terminal.forcekill()
        if self.mcsm and isinstance(self.terminal, WindowsProxy):
            return self.terminal.kill()
        return ServerStatus.UNAVAILABLE
