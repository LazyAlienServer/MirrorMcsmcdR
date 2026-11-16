from mcdreforged.api.all import Serializable
from typing import List, Union

class BackupConfig(Serializable):
    enable: bool = False
    mcdr_path: str = ""
    timeout: int = 600
    confirm_on_warning: bool = True

class SynchronizationConfig(Serializable):
    world: List[str] = ["world"]
    source: str = "./server"
    target: Union[List[str], str] = ["./Mirror/server"]
    ignore_inexistent_target_path: bool = False
    concurrency: int = 4
    ignore_files: List[str] = ["session.lock"]
    backup: BackupConfig = BackupConfig()