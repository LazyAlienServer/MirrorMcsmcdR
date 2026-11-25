from mcdreforged.api.all import Serializable
from typing import List, Literal, Union

class BackupConfig(Serializable):
    enable: bool = False
    timeout: int = 600
    confirm_on_warning: bool = True

class MissingConfig(Serializable):
    """What a sync does about what the config names but is not there; all is judged before the mirror is stopped."""
    # a world pattern that selects no directory in the source
    source_world: Literal["refuse", "skip"] = "refuse"
    # a target directory that does not exist; "create" makes its last component only
    target: Literal["refuse", "skip", "create"] = "refuse"
    # an existing target without a world the source has
    target_world: Literal["create", "refuse"] = "create"
    # an extra pattern that matches nothing in the source
    extra_pattern: Literal["skip", "refuse"] = "skip"

class SynchronizationConfig(Serializable):
    # gitignore patterns over the names of the source's top-level directories
    world: List[str] = ["world"]
    # gitignore patterns over paths relative to the server directory, outside the worlds
    extra_patterns: List[str] = []
    # empty: the working directory of this MCDR
    source: str = ""
    # empty: derived from root_path, see MirrorRuntime.sync_targets
    target: Union[List[str], str] = []
    missing: MissingConfig = MissingConfig()
    concurrency: int = 4
    # gitignore patterns over paths relative to the server directory, as PrimeBackup's of the same names
    ignore_patterns: List[str] = ["session.lock"]
    retain_patterns: List[str] = []
    backup: BackupConfig = BackupConfig()