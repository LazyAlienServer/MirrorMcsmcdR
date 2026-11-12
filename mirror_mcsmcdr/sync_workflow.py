import datetime
import time
from contextlib import contextmanager
from threading import Event, Lock
from typing import Any, Iterator, Optional, Pattern, Protocol

from mcdreforged.api.all import CommandSource, PluginServerInterface, RTextBase

from mirror_mcsmcdr.config.command_config import SaveWorldConfig
from mirror_mcsmcdr.mirror_runtime import MirrorRuntime
from mirror_mcsmcdr.utils.history_utils import SyncRecord, SyncStatus
from mirror_mcsmcdr.utils.status import ServerStatus


class Translator(Protocol):
    def __call__(self, key: str, title: bool = True, **kwargs: Any) -> RTextBase:
        ...


def format_duration(seconds: float) -> str:
    """Format as ``SS.ss`` below one minute, otherwise as ``[HH:]MM:SS``."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return ("%02d:" % h if h else "") + ("%02d:" % m if m else "") + ("%02d" % s if m or h else ("%.02f" % s).zfill(5))


class SaveWorldWaiter:
    """Lets a sync wait until the server console reports that the world has been saved."""

    def __init__(self) -> None:
        self._pattern: Optional[Pattern[str]] = None
        self._saved = Event()

    def begin(self, pattern: Pattern[str]) -> None:
        """Start watching the server output; call before sending the save command."""
        self._saved.clear()
        self._pattern = pattern

    def wait(self, timeout: float) -> bool:
        try:
            return self._saved.wait(timeout)
        finally:
            self._pattern = None

    def on_server_output(self, content: str) -> None:
        pattern = self._pattern
        if pattern is not None and pattern.match(content):
            self._saved.set()


class SyncWorkflow:
    """
    Synchronizes the world of the source server to the mirror server.

    Whoever uses or replaces a runtime for syncing has to :meth:`hold` the workflow meanwhile.
    This keeps syncs from overlapping, and keeps a reload from swapping the runtime under a running sync.
    """

    def __init__(self, server: PluginServerInterface, tr: Translator) -> None:
        self._server = server
        self._tr = tr
        self._lock = Lock()
        self._save_waiter = SaveWorldWaiter()

    def on_server_output(self, content: str) -> None:
        self._save_waiter.on_server_output(content)

    @contextmanager
    def hold(self) -> Iterator[bool]:
        """Claim the workflow without blocking; yields False if it is already held."""
        acquired = self._lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                self._lock.release()

    def run(self, runtime: MirrorRuntime, source: CommandSource, operator: str) -> bool:
        """
        Run a sync and record its result in the history; the caller must :meth:`hold` the workflow.

        :return: True if the mirror server was stopped for this sync and has to be started again
        """
        started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record: Optional[SyncRecord] = None
        needs_restart = False
        try:
            stopped_here = self._ensure_server_closed(runtime, source)
            if stopped_here is None:
                return False
            needs_restart = stopped_here
            record = self._sync_world(runtime, started_at, operator)
        except Exception as e:
            self._server.broadcast(self._tr("command.sync.error"))
            self._server.logger.error(e, exc_info=e)
            record = SyncRecord(started_at, operator, SyncStatus.FAILED, exception=str(e))
        finally:
            if record is not None:
                runtime.history.append(record)
        return needs_restart

    def _ensure_server_closed(self, runtime: MirrorRuntime, source: CommandSource) -> Optional[bool]:
        """
        :return: whether the mirror server was stopped here, or None if the sync must not proceed
        """
        config = runtime.config.command.action.sync
        if not config.ensure_server_closed:
            return False
        status = runtime.proxy.status()
        if status == ServerStatus.STOPPED:
            return False
        if status != ServerStatus.RUNNING or not config.auto_server_restart:
            source.reply(self._tr(f"command.sync.fail.{status}"))
            return None

        self._server.broadcast(self._tr("command.sync.auto_restart.restarting"))
        runtime.proxy.stop()
        for _ in range(config.max_attempt_times):
            time.sleep(config.check_status_interval)
            status = runtime.proxy.status()
            if status == ServerStatus.STOPPED:
                return True
            if not ServerStatus.is_available(status):
                self._server.broadcast(self._tr("command.sync.auto_restart.fail", status=self._tr(f"command.status.fail.{status}", title=False)))
                return None
        self._server.broadcast(self._tr("command.sync.auto_restart.fail", status=self._tr(f"command.status.success.{status}", title=False)))
        return None

    def _sync_world(self, runtime: MirrorRuntime, started_at: str, operator: str) -> SyncRecord:
        self._server.broadcast(self._tr("command.sync.success"))
        started = time.time()
        self._save_world(runtime.config.command.action.sync.save_world, runtime.save_world_regex)
        changed_files_count, paths_notfound = runtime.world_sync.sync()
        duration = format_duration(time.time() - started)

        if paths_notfound:
            self._server.broadcast(self._tr("command.sync.skip_dictionary", paths="§f`§7".join(paths_notfound)))
        if changed_files_count != 0:
            self._server.broadcast(self._tr("command.sync.completed", time=duration, changed_files_count=changed_files_count))
        else:
            self._server.broadcast(self._tr("command.sync.identical"))
        return SyncRecord(
            started_at,
            operator,
            SyncStatus.SUCCESS if changed_files_count != 0 else SyncStatus.IDENTICAL,
            duration=duration,
            changed_files_count=changed_files_count,
            paths_notfound=paths_notfound,
        )

    def _save_world(self, config: SaveWorldConfig, saved_pattern: Pattern[str]) -> None:
        if config.turn_off_auto_save:
            self._server.execute(config.commands.auto_save_off)
        self._save_waiter.begin(saved_pattern)
        self._server.execute(config.commands.save_all_worlds)
        self._save_waiter.wait(config.save_world_max_wait_sec)
        if config.turn_off_auto_save:
            self._server.execute(config.commands.auto_save_on)
