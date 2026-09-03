from mcdreforged.api.all import Serializable
from typing import List, Union

class SynchronizationConfig(Serializable):
    world: List[str] = ["world"]
    source: str = "./server"
    target: Union[List[str], str] = ["./Mirror/server"]
    ignore_inexistent_target_path: bool = False
    concurrency: int = 4
    ignore_files: List[str] = ["session.lock"]