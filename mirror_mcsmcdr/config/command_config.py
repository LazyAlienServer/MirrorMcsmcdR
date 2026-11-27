from mcdreforged.api.all import Serializable
from typing import Optional, Union, Literal

PermissionRequirement = Union[int, Literal["console"]]

class CommandPermissionConfig(Serializable):
    status: PermissionRequirement = 0
    start: PermissionRequirement = 0
    stop: PermissionRequirement = 2
    kill: PermissionRequirement = 3
    sync: PermissionRequirement = 2
    history: PermissionRequirement = 0
    confirm: PermissionRequirement = 0
    log: PermissionRequirement = "console"
    input: PermissionRequirement = "console"
    recover: PermissionRequirement = 3

    def requirement_of(self, command: str) -> PermissionRequirement:
        return getattr(self, command)

class ActionConfig(Serializable):
    require_confirm: bool = False

class StartActionConfig(ActionConfig):
    timeout: int = 120

class StopActionConfig(ActionConfig):
    timeout: int = 60

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
    # the server is running: stop it before the sync, start it again afterwards
    auto_server_restart: bool = False
    # only MCDR is running: make it exit before the sync, nothing is started afterwards
    auto_mcdr_stop: bool = False
    save_world: SaveWorldConfig = SaveWorldConfig()

class HistoryActionConfig(ActionConfig):
    max_history_count: int = 5

class ConfirmActionConfig(Serializable):
    timeout: int = 30
    cancel_anymsg: bool = True

class CommandActionConfig(Serializable):
    status: ActionConfig = ActionConfig()
    start: StartActionConfig = StartActionConfig()
    stop: StopActionConfig = StopActionConfig(require_confirm=True)
    # the longest gap in seconds between two full checks while waiting for the status to change
    check_status_interval: int = 5
    kill: ActionConfig = ActionConfig(require_confirm=True)
    sync: SyncActionConfig = SyncActionConfig(require_confirm=True)
    history: HistoryActionConfig = HistoryActionConfig()
    confirm: ConfirmActionConfig = ConfirmActionConfig()

    def requires_confirm(self, command: str) -> bool:
        # a command without an action config, such as recover, asks for a confirmation by itself where it needs one
        action: Optional[ActionConfig] = getattr(self, command, None)
        return action is not None and action.require_confirm

class CommandConfig(Serializable):
    permission: CommandPermissionConfig = CommandPermissionConfig()
    action: CommandActionConfig = CommandActionConfig()
