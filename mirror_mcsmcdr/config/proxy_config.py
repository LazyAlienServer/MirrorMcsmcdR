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
    is_mcdr: bool = True
    proxy_type: Optional[Literal["windows", "linux", "subprocess"]] = None
    console_log: bool = False
    # adopt the mirror's MCDR found running outside the record when the plugin loads
    auto_recover: bool = True
    # with is_mcdr false: the names of the Java processes looked for outside the record, as a regular expression
    java_name: str = r"^javaw?\d*(\.exe)?$"