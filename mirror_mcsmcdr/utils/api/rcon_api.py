from mcdreforged.api.all import RconConnection

class RConAPI:

    def __init__(self, address: str, port: int, password: str) -> None:
        self.rcon = RconConnection(address, port, password)
    
    def status(self):
        try:
            self.rcon.connect()
            return "running"
        except:
            return "stopped"
    
    def stop(self):
        if self.status() == "stopped":
            return "stopped"
        self.rcon.send_command("stop")
        return "success"
        