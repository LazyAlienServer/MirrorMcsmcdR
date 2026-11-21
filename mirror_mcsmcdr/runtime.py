import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Pattern

from mirror_mcsmcdr.config import MirrorConfig
from mirror_mcsmcdr.mcdr_config import CONFIG_FILE, MCDRConfigError, read_mcdr_config
from mirror_mcsmcdr.sync.history import SyncHistory
from mirror_mcsmcdr.server import ProcessTracker, ProxySettingException, ServerController, SubprocessProxy, build_backends
from mirror_mcsmcdr.sync.synchronizer import ClassicWorldSynchronizer
from mirror_mcsmcdr.sync.backup import MirrorBackup


def sync_targets(config: MirrorConfig) -> list[str]:
    """
    The directories a sync copies into: as configured, or else the server directory under ``root_path``,
    which for an MCDR is its ``working_directory``. Read anew on every call, as the mirror's own config may change.

    :raise MCDRConfigError: if the mirror's MCDR config has to be read and cannot be
    """
    target = config.sync.target
    targets = [path for path in ([target] if isinstance(target, str) else target) if path]
    if targets:
        return targets
    if not config.is_mcdr:
        return [config.root_path]
    config_path = Path(config.root_path) / CONFIG_FILE
    working_directory = read_mcdr_config(config_path).get("working_directory", "server")
    if not isinstance(working_directory, str):
        raise MCDRConfigError(config_path, None)
    return [os.path.join(config.root_path, working_directory)]


def sync_source(config: MirrorConfig, working_directory: str) -> str:
    """
    The directory a sync copies from: as configured, or else ``working_directory``, that of the MCDR running this plugin.
    Taken anew for every sync, as that MCDR may reload its config and start its server elsewhere.
    """
    return config.sync.source or working_directory


@dataclass(frozen=True)
class MirrorRuntime:
    """
    Everything a mirror manager derives from one config.

    Built in one step and swapped as a whole on reload, so a config that fails to build
    never leaves the manager with a mix of old and new objects.
    """

    config: MirrorConfig
    controller: ServerController
    world_sync: ClassicWorldSynchronizer
    history: SyncHistory
    save_world_regex: Pattern[str]
    # proxies that are enabled but could not be set up; they stay unusable, the rest still work
    proxy_errors: tuple[ProxySettingException, ...]
    # None while the pre-sync backup is disabled
    backup: Optional[MirrorBackup]

    @classmethod
    def build(cls, config: MirrorConfig, data_path: Path, tracker: ProcessTracker) -> "MirrorRuntime":
        if not config.root_path:
            raise ValueError("root_path must not be empty")
        sync = config.sync
        action = config.command.action
        world_sync = ClassicWorldSynchronizer(
            sync.world,
            sync.ignore_inexistent_target_path,
            sync.concurrency,
            sync.ignore_files,
        )
        save_world_regex = re.compile(action.sync.save_world.saved_world_regex)
        history = SyncHistory(data_path / "history.json", action.history.max_history_count)

        backends, proxy_errors = build_backends(config, tracker)
        controller = ServerController(backends, action.start.timeout, action.stop.timeout)
        return cls(config, controller, world_sync, history, save_world_regex, tuple(proxy_errors), cls._build_backup(config))

    @staticmethod
    def _build_backup(config: MirrorConfig) -> Optional[MirrorBackup]:
        backup = config.sync.backup
        if not backup.enable:
            return None
        # a plain server has no MCDR, so no PrimeBackup of its own
        mcdr_path = config.root_path if config.is_mcdr else None
        return MirrorBackup(mcdr_path, list(config.sync.world), lambda: sync_targets(config), list(config.sync.ignore_files), backup.timeout)

    @property
    def subprocess_terminal(self) -> Optional[SubprocessProxy]:
        return next((backend for backend in self.controller.backends if isinstance(backend, SubprocessProxy)), None)
