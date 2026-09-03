from mcdreforged.api.all import Serializable
from typing import Union, Literal

class CommandPermissionConfig(Serializable):
    status: Union[int, Literal["console"]] = 0
    start: Union[int, Literal["console"]] = 0
    stop: Union[int, Literal["console"]] = 2
    kill: Union[int, Literal["console"]] = 3
    sync: Union[int, Literal["console"]] = 2
    history: Union[int, Literal["console"]] = 0
    confirm: Union[int, Literal["console"]] = 0
    abort: Union[int, Literal["console"]] = 0
    log: Union[int, Literal["console"]] = "console"
    execute: Union[int, Literal["console"]] = "console"

class ActionConfig(Serializable):
    require_confirm: bool = False

class SaveWorldCommandsConfig(Serializable):
    save_all_worlds: str = "save-all flush"
    auto_save_off: str = "save-off"
    auto_save_on: str = "save-on"

class SaveWorldConfig(Serializable):
    turn_off_auto_save: bool = True
    commands: SaveWorldCommandsConfig = SaveWorldCommandsConfig()
    saved_world_regex: str = "^Saved the game$"
    save_world_max_wait_sec: int = 60

class SyncActionConfig(ActionConfig):
    ensure_server_closed: bool = True
    auto_server_restart: bool = False
    check_status_interval: int = 5
    max_attempt_times: int = 3
    save_world: SaveWorldConfig = SaveWorldConfig()

class HistoryActionConfig(ActionConfig):
    max_history_count: int = 5

class ConfirmActionConfig(Serializable):
    timeout: int = 30
    cancel_anymsg: bool = True

class AbortActionConfig(Serializable):
    operator: str = "everyone"

class CommandActionConfig(Serializable):
    status: ActionConfig = ActionConfig()
    start: ActionConfig = ActionConfig()
    stop: ActionConfig = ActionConfig(require_confirm=True)
    kill: ActionConfig = ActionConfig(require_confirm=True)
    sync: SyncActionConfig = SyncActionConfig(require_confirm=True)
    history: HistoryActionConfig = HistoryActionConfig()
    confirm: ConfirmActionConfig = ConfirmActionConfig()
    abort: AbortActionConfig = AbortActionConfig()

class CommandConfig(Serializable):
    permission: CommandPermissionConfig = CommandPermissionConfig()
    action: CommandActionConfig = CommandActionConfig()