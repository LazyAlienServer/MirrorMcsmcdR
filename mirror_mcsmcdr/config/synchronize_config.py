from mcdreforged.api.all import Serializable
from typing import List, Union

class BackupConfig(Serializable):
    enable: bool = False
    timeout: int = 600
    confirm_on_warning: bool = True

class SynchronizationConfig(Serializable):
    world: List[str] = ["world"]
    # empty: the working directory of this MCDR
    source: str = ""
    # empty: derived from root_path, see MirrorRuntime.sync_targets
    target: Union[List[str], str] = []
    ignore_inexistent_target_path: bool = False
    concurrency: int = 4
    ignore_files: List[str] = ["session.lock"]
    backup: BackupConfig = BackupConfig()