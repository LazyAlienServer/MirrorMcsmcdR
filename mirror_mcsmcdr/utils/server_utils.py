from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxy
from mirror_mcsmcdr.utils.proxy.rcon_proxy import RConProxy
from mirror_mcsmcdr.utils.proxy.system_proxy import SystemProxy
import platform

class ServerProxy:

    def __init__(self) -> None:
        self.mcsm : MCSManagerProxy = None
        self.rcon : RConProxy = None
        self.system : SystemProxy = None
    
    def set_mcsm(self, enable, url, uuid, remote_uuid, apikey):
        if enable and url and uuid and remote_uuid and apikey:
            self.mcsm = MCSManagerProxy(enable, url, uuid, remote_uuid, apikey)
            return True

    
    def set_rcon(self, enable, address, port, password):
        if enable and address and port and password:
            self.rcon = RConProxy(address, port, password)
            return True
        
    
    def set_system(self, enable, terminal_name: str, launch_path: str, launch_command: str, port: int, regex_strict: bool, system: str):
        if enable and terminal_name and launch_path and launch_command and port and type(regex_strict) == bool:
            if not system:
                system = platform.system()
                if system not in ["Linux", "Windows"]:
                    return system
            self.system = SystemProxy(terminal_name, launch_path, launch_command, port, regex_strict, system)
            return True
    
    def status(self):
        if self.mcsm:
            return self.mcsm.status()
        if self.rcon:
            status = self.rcon.status()
            if status == "stopped" and self.system:
                status_sys = self.system.status()
                return "stopped" if status == status_sys else "rcon_status_mismatch"
            return status
        return self.system.status() if self.system else "unavailable"
    
    def start(self):
        if self.mcsm:
            return self.mcsm.start()
        if self.system:
            return self.system.start()
        return "unavailable"
    
    def stop(self):
        if self.mcsm:
            return self.mcsm.stop()
        if self.rcon:
            return self.rcon.stop()
        if self.system:
            return self.system.stop()
        return "unavailable"
    
    def kill(self):
        if self.mcsm:
            return self.mcsm.kill()
        return "unavailable"