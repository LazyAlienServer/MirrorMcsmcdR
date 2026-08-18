from mcdreforged.api.all import RconConnection
from mirror_mcsmcdr.utils.status import ServerStatus

class RConProxy:

    def __init__(self, address: str, port: int, password: str) -> None:
        self.rcon = RconConnection(address, port, password)
    
    def status(self) -> ServerStatus:
        try:
            self.rcon.connect()
            return ServerStatus.RUNNING
        except:
            return ServerStatus.STOPPED
    
    def stop(self):
        if self.status() == ServerStatus.STOPPED:
            return ServerStatus.STOPPED
        self.rcon.send_command("stop")
        return "success"
        