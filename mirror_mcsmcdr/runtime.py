import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Pattern

from mirror_mcsmcdr.config import MirrorConfig
from mirror_mcsmcdr.sync.history import SyncHistory
from mirror_mcsmcdr.server import ProxySettingException, ServerController, SubprocessProxy, build_backends
from mirror_mcsmcdr.sync.synchronizer import ClassicWorldSynchronizer


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

    @classmethod
    def build(cls, config: MirrorConfig, data_path: Path) -> "MirrorRuntime":
        sync = config.sync
        action = config.command.action
        world_sync = ClassicWorldSynchronizer(
            sync.world,
            sync.source,
            sync.target,
            sync.ignore_inexistent_target_path,
            sync.concurrency,
            sync.ignore_files,
        )
        save_world_regex = re.compile(action.sync.save_world.saved_world_regex)
        history = SyncHistory(data_path / "history.json", action.history.max_history_count)

        backends, proxy_errors = build_backends(config)
        controller = ServerController(backends, action.start.timeout, action.stop.timeout)
        return cls(config, controller, world_sync, history, save_world_regex, tuple(proxy_errors))

    @property
    def subprocess_terminal(self) -> Optional[SubprocessProxy]:
        return next((backend for backend in self.controller.backends if isinstance(backend, SubprocessProxy)), None)
