import datetime
import time
from contextlib import contextmanager
from threading import Event, Lock
from typing import Callable, Iterator, Optional, Pattern

from mcdreforged.api.all import CommandSource, PluginServerInterface, RTextBase

from mirror_mcsmcdr.config.command_config import SaveWorldConfig
from mirror_mcsmcdr.runtime import MirrorRuntime
from mirror_mcsmcdr.sync.history import SyncRecord, SyncStatus
from mirror_mcsmcdr.sync.backup import BackupError, BackupFailed, BackupUnavailable, MirrorBackup
from mirror_mcsmcdr.text_utils import Translator, detail_lines, refusal_lines, status_key
from mirror_mcsmcdr.server import Action, ServerState, StatusSnapshot, WaitEnd


class _SyncRefused(Exception):
    """The sync stopped for a reason that has been reported already; it is recorded as failed."""


def describe_backup_error(tr: Translator, error: BackupError) -> RTextBase:
    """Why there is no backup, in words that may be shown in game."""
    return tr(f"command.sync.backup.reason.{error.reason}", title=False, **error.kwargs)


def backup_error_console_lines(tr: Translator, error: BackupError) -> list[RTextBase]:
    """What only the console may see of ``error``: the paths it is about, and what the command line tool printed."""
    lines = []
    if error.detail:
        lines.append(tr("command.sync.backup.detail", title=False, detail=error.detail))
    if error.output:
        lines.append(tr("command.sync.backup.output", title=False, output=error.output_tail))
    return lines


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

    def run(self, runtime: MirrorRuntime, source: CommandSource, operator: str, on_server_stopped: Callable[[], None]) -> None:
        """
        Run a sync and record its result in the history; the caller must :meth:`hold` the workflow.

        :param on_server_stopped: called once a running mirror server has been stopped for this sync.
            The caller then has to start it again, whatever happens to the sync afterwards.
            An MCDR that ran without a server is made to exit without this call: nothing is to be started again
        """
        started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record: Optional[SyncRecord] = None
        # set as soon as the backup exists, so that every record of this sync carries it
        backup_id: Optional[int] = None
        try:
            if not self._ensure_server_closed(runtime, source, on_server_stopped):
                return
            if runtime.backup is not None:
                backup_id = self._back_up(runtime.backup, operator)
                if backup_id is not None:
                    self._server.broadcast(self._tr("command.sync.backup.done", backup_id=backup_id))
            record = self._sync_world(runtime, started_at, operator, backup_id)
        except _SyncRefused as e:
            record = SyncRecord(started_at, operator, SyncStatus.FAILED, exception=str(e), backup_id=backup_id)
        except Exception as e:
            self._server.broadcast(self._tr("command.sync.error"))
            self._server.logger.error(e, exc_info=e)
            record = SyncRecord(started_at, operator, SyncStatus.FAILED, exception=str(e), backup_id=backup_id)
        finally:
            if record is not None:
                runtime.history.append(record)

    def _ensure_server_closed(self, runtime: MirrorRuntime, source: CommandSource, on_server_stopped: Callable[[], None]) -> bool:
        """
        :return: whether the sync may proceed
        """
        config = runtime.config.command.action.sync
        if not config.ensure_server_closed:
            return True
        controller = runtime.controller
        snapshot = controller.status()
        if snapshot.safe_to_modify():
            return True
        # a running server is restarted after the sync; an MCDR without a server is only told to exit, nothing was running
        restart = snapshot.is_exactly(ServerState.RUNNING)
        if not (restart or snapshot.is_exactly(ServerState.MCDR_ONLY)) or not config.auto_server_restart:
            if snapshot.evidence.empty:
                source.reply(self._tr("command.sync.fail.unsupported"))
            else:
                for line in refusal_lines(self._tr, "sync", snapshot):
                    source.reply(line)
            return False

        self._server.broadcast(self._tr("command.sync.auto_restart.restarting"))
        result = controller.execute(Action.STOP)
        snapshot = result.snapshot
        if result.accepted:
            action = runtime.config.command.action
            waited = controller.wait_until(
                StatusSnapshot.safe_to_modify,
                timeout=action.stop.timeout,
                interval=action.check_status_interval,
                # a listener the plugin did not start does not go away by waiting
                give_up=lambda status: status.state is ServerState.UNKNOWN,
            )
            snapshot = waited.snapshot
            if waited.end is WaitEnd.REACHED:
                if restart:
                    on_server_stopped()
                return True
        self._server.broadcast(self._tr("command.sync.auto_restart.fail", status=self._tr(status_key(snapshot), title=False)))
        # what it is still waiting for
        for line in detail_lines(self._tr, snapshot):
            source.reply(line)
        return False

    def _back_up(self, backup: MirrorBackup, operator: str) -> Optional[int]:
        """
        Back the mirror up with its PrimeBackup, located from scratch: nothing found earlier is trusted.

        :return: the id of the backup, None if no target holds any of the worlds yet
        :raise _SyncRefused: there is no backup, so there must be no sync
        """
        try:
            resolved = backup.resolve()
            if not backup.has_existing_world():
                self._server.broadcast(self._tr("command.sync.backup.skipped"))
                return None
            self._server.broadcast(self._tr("command.sync.backup.start"))
            return backup.make(resolved, operator)
        except BackupError as e:
            raise self._refuse("failed" if isinstance(e, BackupFailed) else "unavailable", e) from e

    def _ensure_stopped(self, runtime: MirrorRuntime) -> None:
        snapshot = runtime.controller.status()
        if not snapshot.safe_to_modify():
            raise BackupUnavailable("mirror_not_stopped", status=self._tr(status_key(snapshot), title=False).to_legacy_text())

    def _refuse(self, kind: str, error: BackupError) -> "_SyncRefused":
        """Report why the sync stops at the backup and return what to raise for it."""
        reason = describe_backup_error(self._tr, error)
        self._server.broadcast(self._tr(f"command.sync.backup.{kind}", reason=reason.to_legacy_text()))
        for line in backup_error_console_lines(self._tr, error):
            self._server.logger.warning(line)
        return _SyncRefused(reason.to_plain_text())

    def _sync_world(self, runtime: MirrorRuntime, started_at: str, operator: str, backup_id: Optional[int]) -> SyncRecord:
        self._server.broadcast(self._tr("command.sync.success"))
        started = time.time()
        sync_config = runtime.config.command.action.sync
        self._save_world(sync_config.save_world, runtime.save_world_regex)
        # the backup and the save took a while; a mirror started meanwhile holds newer data than the backup
        if runtime.backup is not None and sync_config.ensure_server_closed:
            try:
                self._ensure_stopped(runtime)
            except BackupUnavailable as e:
                raise self._refuse("stale", e) from e
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
            backup_id=backup_id,
        )

    def _save_world(self, config: SaveWorldConfig, saved_pattern: Pattern[str]) -> None:
        if config.turn_off_auto_save:
            self._server.execute(config.commands.auto_save_off)
        self._save_waiter.begin(saved_pattern)
        self._server.execute(config.commands.save_all_worlds)
        self._save_waiter.wait(config.save_world_max_wait_sec)
        if config.turn_off_auto_save:
            self._server.execute(config.commands.auto_save_on)
