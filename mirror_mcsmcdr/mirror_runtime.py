import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Pattern

from mirror_mcsmcdr.config import MirrorConfig
from mirror_mcsmcdr.utils.history_utils import SyncHistory
from mirror_mcsmcdr.utils.proxy.subprocess_proxy import SubprocessProxy
from mirror_mcsmcdr.utils.server_utils import ProxySettingException, ServerProxy
from mirror_mcsmcdr.utils.sync.classic_synchronizer import ClassicWorldSynchronizer


@dataclass(frozen=True)
class MirrorRuntime:
    """
    Everything a mirror manager derives from one config.

    Built in one step and swapped as a whole on reload, so a config that fails to build
    never leaves the manager with a mix of old and new objects.
    """

    config: MirrorConfig
    proxy: ServerProxy
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

        proxy = ServerProxy()
        setups: tuple[Callable[[], object], ...] = (
            lambda: proxy.set_mcsm(**config.mcsm.serialize()),
            lambda: proxy.set_rcon(**config.rcon.serialize()),
            lambda: proxy.set_terminal(**config.terminal.serialize()),
        )
        proxy_errors = []
        for setup in setups:
            try:
                setup()
            except ProxySettingException as e:
                proxy_errors.append(e)
        return cls(config, proxy, world_sync, history, save_world_regex, tuple(proxy_errors))

    @property
    def subprocess_terminal(self) -> Optional[SubprocessProxy]:
        terminal = self.proxy.terminal
        return terminal if isinstance(terminal, SubprocessProxy) else None
