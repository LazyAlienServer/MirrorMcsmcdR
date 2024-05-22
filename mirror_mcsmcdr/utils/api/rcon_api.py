from mcdreforged.api.all import RconConnection

class RConAPI:

    def __init__(self, address: str, port: int, password: str) -> None:
        self.rcon = RconConnection(address, port, password)
        self.status = self.rcon.connect()
    
    def status(self):
        try:
            return self.rcon.connect()
        except:
            return False
    
    def stop(self):
        if self.status():
            return self.rcon.send_command("stop")