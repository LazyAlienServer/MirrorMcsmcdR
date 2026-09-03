from mcdreforged.api.all import Serializable
from typing import Optional, Literal

class MCSMConfig(Serializable):
    enable: bool = False
    url: str = "http://127.0.0.1:23333/"
    uuid: Optional[str] = None
    remote_uuid: Optional[str] = None
    apikey: Optional[str] = None

class TerminalConfig(Serializable):
    enable: bool = False
    launch_path: str = "./Mirror"
    launch_command: str = "python -m mcdreforged"
    port: Optional[int] = None
    terminal_name: str = "Mirror"
    regex_strict: bool = False
    is_mcdr: bool = True
    proxy_type: Optional[Literal["windows", "linux", "subprocess"]] = None
    console_log: bool = False

class RConConfig(Serializable):
    enable: bool = False
    address: Optional[str] = None
    port: Optional[int] = None
    password: Optional[str] = None