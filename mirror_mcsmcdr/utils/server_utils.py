from mirror_mcsmcdr.utils.api.mcsm_api import MCSManagerApi, MCSManagerApiError
from mirror_mcsmcdr.utils.api.rcon_api import RConAPI
from mirror_mcsmcdr.utils.api.system_api import SystemAPI

class ServerProxy:

    def __init__(self) -> None:
        self.mcsm : MCSManagerApi = None
        self.rcon : RConAPI = None
        self.system : SystemAPI = None
    
    def set_mcsm(self, enable, url, uuid, remote_uuid, apikey):
        self.mcsm = MCSManagerApi(enable, url, uuid, remote_uuid, apikey)
    
    def set_rcon(self, address, port, password):
        self.rcon = RConAPI(address, port, password)
    
    def set_system(self, new_terminal):
        if self.rcon:
            self.system = SystemAPI(new_terminal, self.rcon)
    
    def status(self):
        if self.mcsm:
            return self.mcsm.status()
        if self.rcon:
            status = self.rcon.status()
            if not status and self.system:
                status_sys = self.system.status()
                if status == status_sys:
                    return "stopped"
                raise