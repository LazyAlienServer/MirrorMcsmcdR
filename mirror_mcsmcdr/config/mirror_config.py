from mcdreforged.api.all import Serializable
from mirror_mcsmcdr.config.command_config import CommandConfig
from mirror_mcsmcdr.config.proxy_config import MCSMConfig, TerminalConfig, RConConfig
from mirror_mcsmcdr.config.synchronize_config import SynchronizationConfig
from typing import Dict

class DisplayConfig(Serializable):
    server_name: str = "Mirror"

class MirrorConfig(Serializable):
    mcsm: MCSMConfig = MCSMConfig()
    terminal: TerminalConfig = TerminalConfig()
    rcon: RConConfig = RConConfig()
    sync: SynchronizationConfig = SynchronizationConfig()
    command: CommandConfig = CommandConfig()
    display: DisplayConfig = DisplayConfig()

class MultiMirrorConfig(Dict[str, MirrorConfig]):
    ...