from mcdreforged.api.all import Serializable
from typing import List, Union

class BackupConfig(Serializable):
    enable: bool = False
    timeout: int = 600
    confirm_on_warning: bool = True

class SynchronizationConfig(Serializable):
    # gitignore patterns over the names of the source's top-level directories
    world: List[str] = ["world"]
    # empty: the working directory of this MCDR
    source: str = ""
    # empty: derived from root_path, see MirrorRuntime.sync_targets
    target: Union[List[str], str] = []
    ignore_inexistent_target_path: bool = False
    concurrency: int = 4
    # gitignore patterns over paths relative to the server directory, as PrimeBackup's of the same names
    ignore_patterns: List[str] = ["session.lock"]
    retain_patterns: List[str] = []
    backup: BackupConfig = BackupConfig()