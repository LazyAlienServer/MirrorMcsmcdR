from typing import Dict, List, Literal
from mcdreforged.api.all import Serializable
from mirror_mcsmcdr.config.command_config import CommandConfig
from mirror_mcsmcdr.config.proxy_config import MCSMConfig, TerminalConfig
from mirror_mcsmcdr.config.synchronize_config import SynchronizationConfig

class DisplayConfig(Serializable):
    server_name: str = 'Mirror'
    # what game messages leave out about processes; the console always gets everything
    protected_process_info: List[Literal['name', 'pid']] = []

class MirrorConfig(Serializable):
    mcsm: MCSMConfig = MCSMConfig()
    terminal: TerminalConfig = TerminalConfig()
    sync: SynchronizationConfig = SynchronizationConfig()
    command: CommandConfig = CommandConfig()
    display: DisplayConfig = DisplayConfig()

class MultiMirrorConfig(Dict[str, MirrorConfig]):
    pass