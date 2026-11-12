from mcdreforged.api.all import Serializable
from typing import Union, Literal

PermissionRequirement = Union[int, Literal["console"]]

class CommandPermissionConfig(Serializable):
    status: PermissionRequirement = 0
    start: PermissionRequirement = 0
    stop: PermissionRequirement = 2
    kill: PermissionRequirement = 3
    sync: PermissionRequirement = 2
    history: PermissionRequirement = 0
    confirm: PermissionRequirement = 0
    abort: PermissionRequirement = 0
    log: PermissionRequirement = "console"
    execute: PermissionRequirement = "console"

    def requirement_of(self, command: str) -> PermissionRequirement:
        return getattr(self, command)

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

    def requires_confirm(self, command: str) -> bool:
        action: ActionConfig = getattr(self, command)
        return action.require_confirm

class CommandConfig(Serializable):
    permission: CommandPermissionConfig = CommandPermissionConfig()
    action: CommandActionConfig = CommandActionConfig()
