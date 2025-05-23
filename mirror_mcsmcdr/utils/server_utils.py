from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxy
from mirror_mcsmcdr.utils.proxy.rcon_proxy import RConProxy
from mirror_mcsmcdr.utils.proxy.system_proxy import SystemProxy
import platform
from typing import List, Union, Optional, Literal

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
        
    
    def set_terminal(self, enable, regex_strict: bool, system: Optional[str] = None, **kwargs):
        if enable and not sum(map(lambda x : not bool(x), kwargs.values())) and type(regex_strict) == bool:
            if not system:
                system = platform.system()
                if system not in ["Linux", "Windows"]:
                    self.terminal = False
                    raise TerminalSettingException(system)
            self.terminal = SystemProxy(**kwargs, regex_strict = regex_strict, system = system)
            return True
        if enable:
            self.terminal = False
            raise ProxySettingException("terminal", [key for key, value in kwargs.items() if not bool(value)] + ["regex_strict"] if type(regex_strict) != bool else [])
    
    def status(self):
        if self.mcsm:
            return self.mcsm.status()
        if self.rcon:
            status = self.rcon.status()
            if status == "stopped" and self.terminal:
                status_sys = self.terminal.status()
                return "stopped" if status == status_sys else "rcon_status_mismatch"
            return status
        return self.terminal.status() if self.terminal else "unavailable"
    
    def start(self):
        if self.mcsm:
            return self.mcsm.start()
        if self.terminal:
            return self.terminal.start()
        return "unavailable"
    
    def stop(self):
        if self.mcsm:
            return self.mcsm.stop()
        if self.rcon:
            return self.rcon.stop()
        if self.terminal:
            return self.terminal.stop()
        return "unavailable"
    
    def kill(self):
        if self.mcsm:
            return self.mcsm.kill()
        return "unavailable"