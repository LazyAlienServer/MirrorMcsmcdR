from mcdreforged.api.all import RconConnection

from mirror_mcsmcdr.config.proxy_config import RConConfig
from mirror_mcsmcdr.server.backend.base import ServerBackend
from mirror_mcsmcdr.server.status import Action, ActionResult, Evidence


class RConProxy(ServerBackend):
    supports = frozenset({Action.STOP})

    def __init__(self, config: RConConfig) -> None:
        assert config.address is not None and config.port is not None and config.password is not None
        self.rcon = RconConnection(config.address, config.port, config.password)

    def observe(self) -> Evidence:
        try:
            self.rcon.connect()
        except Exception:
            return Evidence(rcon_reachable=False)
        finally:
            self.rcon.disconnect()
        return Evidence(rcon_reachable=True)

    def _stop(self, result: ActionResult) -> ActionResult:
        self.rcon.connect()
        try:
            self.rcon.send_command("stop")
        finally:
            self.rcon.disconnect()
        return result
