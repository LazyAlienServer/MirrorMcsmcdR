from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from mcdreforged.api.all import CommandContext, CommandSource, Info, Literal, PlayerCommandSource, PluginServerInterface, RAction, RColor, RText, RTextBase, RTextList, SimpleCommandBuilder, new_thread, Integer, GreedyText

from mirror_mcsmcdr.constants import TITLE
from mirror_mcsmcdr.config import MultiConfigLoader, MirrorConfig
from mirror_mcsmcdr.runtime import MirrorRuntime
from mirror_mcsmcdr.sync.workflow import SyncWorkflow, backup_error_console_lines, describe_backup_error
from mirror_mcsmcdr.sync.backup import BackupError, BackupWarning, MirrorBackup
from mirror_mcsmcdr.text_utils import detail_lines, help_msg, rejection_lines, rtr, status_key
from mirror_mcsmcdr.server import Action, MCSManagerProxyError, ProcessInfo, ProcessTracker, ScreenError, ServerState, StatusSnapshot
from mirror_mcsmcdr.sync.history import SyncRecord, SyncStatus
from mirror_mcsmcdr.command_utils.page_utils import Page
from mirror_mcsmcdr.command_utils.confirmation_utils import ConfirmationTask, ConfirmationManager

PAGE_SIZE = 5
CONSOLE_OPERATOR = "[console]"

# A command body; it receives the runtime that is current when it actually runs.
CommandAction = Callable[[MirrorRuntime], object]


def operator_name(source: CommandSource) -> str:
    return source.player if isinstance(source, PlayerCommandSource) else CONSOLE_OPERATOR


class MultiMirrorManager:
    """Owns the plugin config and one :class:`MirrorManager` per command prefix."""

    def __init__(self, server: PluginServerInterface) -> None:
        self.server = server
        self.loader = MultiConfigLoader(server)
        self.loader.load()
        self.managers: dict[str, MirrorManager] = {}

        failed: list[str] = []
        for command_prefix in self.loader.get_all_prefix():
            try:
                manager = MirrorManager(
                    server,
                    self.loader.get_mirror_config(command_prefix),
                    command_prefix,
                    reload_method=self.reload_config,
                )
                # one listener per manager: MCDR isolates listeners, so a failing manager does not affect the others
                server.register_event_listener("mcdr.general_info", manager.on_info)
                server.register_event_listener("mcdr.user_info", manager.on_user_info)
                self.managers[command_prefix] = manager
            except Exception as e:
                server.logger.error(rtr("multi_manager.init.error", prefix=command_prefix, e=e))
                server.logger.error(e, exc_info=e)
                failed.append(command_prefix)

        success_info = rtr("multi_manager.init.success", prefix=", ".join(self.managers))
        fail_info = (rtr("multi_manager.init.fail",title=False,prefix=" §7/§c " + " ".join(failed)) if failed else "")
        server.broadcast(RTextList(success_info, " ", fail_info))

    def reload_config(self, prefix: str) -> bool:
        manager = self.managers[prefix]
        try:
            self.loader.load()
            config = self.loader.get_mirror_config(prefix) if prefix in self.loader.get_all_prefix() else None
        except Exception as e:
            self.server.logger.error(e, exc_info=e)
            self.server.broadcast(manager.rtr("manager.reload.fail"))
            return False
        if config is None:
            self.server.broadcast(rtr("multi_manager.init.prefix_notfound", prefix=prefix))
            manager.disable()
            return False
        return manager.reload_config(config)

    def on_unload(self) -> None:
        for manager in self.managers.values():
            manager.on_unload()


class MirrorManager:
    """Controls one mirror server through the commands registered under its prefix."""

    def __init__(
        self,
        server: PluginServerInterface,
        config: MirrorConfig,
        command_prefix: str,
        reload_method: Callable[[str], bool],
    ) -> None:
        self.server = server
        self.command_prefix = command_prefix
        self.server_name = config.display.server_name
        # outlives the runtimes: what was launched stays tracked across config reloads
        self._tracker = ProcessTracker(
            Path(server.get_data_folder()) / command_prefix / "process.json",
            lambda key, **kwargs: server.logger.warning(self.rtr(f"process_record.{key}", title=False, **kwargs)),
        )
        self.confirmations = ConfirmationManager(self._on_confirmation_timeout)
        self._sync_workflow = SyncWorkflow(server, self.rtr)
        # Kept while disabled, so that its subprocess can still be cleaned up on unload.
        # Only replaced while holding the sync workflow.
        self._runtime: Optional[MirrorRuntime] = None
        self._available = False

        server.logger.info(rtr("manager.load", prefix=command_prefix))
        self._register_commands(reload_method)
        self._apply_config(config)

    def _register_commands(self, reload_method: Callable[[str], bool]) -> None:
        command_prefix = self.command_prefix
        builder = SimpleCommandBuilder()
        builder.command(f"{command_prefix}", self.help)
        builder.command(f"{command_prefix} reload", lambda source, context: reload_method(command_prefix))
        builder.command(f"{command_prefix} help", self.help)
        builder.command(f"{command_prefix} status", self.status)
        builder.command(f"{command_prefix} start", self.start)
        builder.command(f"{command_prefix} stop", self.stop)
        builder.command(f"{command_prefix} kill", self.kill)
        builder.literal("-f", lambda _: Literal(("-f", "--force")))
        builder.command(f"{command_prefix} kill -f", lambda source, context: self.kill(source, context, force=True))
        builder.command(f"{command_prefix} sync", self.sync)
        builder.arg("page", Integer)
        builder.command(f"{command_prefix} history", self.history)
        builder.command(f"{command_prefix} history <page>", self.history)
        builder.command(f"{command_prefix} confirm", self.confirm)
        builder.arg("count", Integer)
        builder.arg("cmd", GreedyText)
        builder.command(f"{command_prefix} log", self.log_help)
        builder.command(f"{command_prefix} log <count>", self.set_console_log_limit)
        builder.command(f"{command_prefix} log enable", lambda source, context: self.set_console_log(source, context, True))
        builder.command(f"{command_prefix} log disable", lambda source, context: self.set_console_log(source, context, False))
        builder.command(f"{command_prefix} execute <cmd>", self.mirror_execute)
        builder.register(self.server)

    def rtr(self, key: str, title: bool = True, **kwargs: Any) -> RTextBase:
        return rtr(key, title, prefix=self.command_prefix, server_name=self.server_name, **kwargs)

    def _apply_config(self, config: MirrorConfig) -> bool:
        """Build a runtime from the config and make it current; on failure the previous state is left untouched."""
        try:
            runtime = MirrorRuntime.build(config, Path(self.server.get_data_folder()) / self.command_prefix, self._tracker)
        except Exception as e:
            if self.server.is_server_startup():
                self.server.say(self.rtr("manager.reload.fail"))
            self.server.logger.error(e, exc_info=e)
            return False
        self.server_name = config.display.server_name
        self._runtime = runtime
        self._available = True
        for error in runtime.proxy_errors:
            self.server.broadcast(self.rtr("manager.reload.fail.proxy", proxy=error.proxy, keys="', '".join(error.missing_keys)))
        if runtime.backup is not None:
            self._diagnose_backup(runtime.backup)
        return True

    def _diagnose_backup(self, backup: MirrorBackup) -> None:
        """Tell the console early what a sync would run into; this decides nothing, each sync checks again."""
        try:
            resolved = backup.resolve()
            backup.probe(resolved)
            warnings = backup.warnings(resolved)
        except BackupError as e:
            self.server.logger.warning(self.rtr("manager.backup.unavailable", title=False, reason=describe_backup_error(self.rtr, e).to_plain_text()))
            for line in backup_error_console_lines(self.rtr, e):
                self.server.logger.warning(line)
            return
        except Exception as e:
            self.server.logger.warning(self.rtr("manager.backup.unavailable", title=False, reason=str(e)), exc_info=e)
            return
        self.server.logger.info(self.rtr("manager.backup.ready", title=False, version=resolved.plugin_version, path=resolved.plugin_path))
        self._log_backup_warnings(warnings)

    def _log_backup_warnings(self, warnings: list[BackupWarning]) -> None:
        # they name paths, so they are for the console only
        for warning in warnings:
            self.server.logger.warning(self.rtr(f"command.sync.backup.warning.{warning.key}", title=False, **warning.kwargs))

    def reload_config(self, config: MirrorConfig) -> bool:
        with self._sync_workflow.hold() as held:
            if not held:
                self.server.broadcast(self.rtr("manager.reload.fail.syncing"))
                return False
            previous = self._runtime
            # a new runtime would no longer know that it has to wait for this start
            if previous is not None and previous.controller.is_starting():
                self.server.broadcast(self.rtr("manager.reload.fail.starting"))
                return False
            if not self._apply_config(config):
                return False
            # the new runtime owns a fresh proxy that cannot reach the process started by the previous one
            if previous is not None and previous.subprocess_terminal is not None:
                previous.subprocess_terminal.forcekill()
            self.server.broadcast(self.rtr("manager.reload.success"))
            return True

    def disable(self) -> None:
        self._available = False

    def _active_runtime(self) -> Optional[MirrorRuntime]:
        return self._runtime if self._available else None

    def help(self, source: CommandSource, _: CommandContext) -> None:
        source.reply(help_msg(self.server_name, self.command_prefix))
        if self._runtime is not None:
            source.reply(self._proxy_info(self._runtime))

    @staticmethod
    def _proxy_info(runtime: MirrorRuntime) -> RTextList:
        config = runtime.config
        misconfigured = {error.proxy for error in runtime.proxy_errors}
        info = RTextList(rtr("command.proxy.title", False))
        for name, proxy_config in (("mcsm", config.mcsm), ("terminal", config.terminal)):
            if name in misconfigured:
                text = RText(name, RColor.red).h(rtr("command.proxy.error", False))
            elif proxy_config.enable:
                text = RText(name, RColor.green).h(rtr("command.proxy.enabled", False))
            else:
                text = RText(name, RColor.gray).h(rtr("command.proxy.disabled", False))
            info.append(" | ", text)
        return info

    def _check_permission(self, runtime: MirrorRuntime, source: CommandSource, command: str) -> bool:
        required_permission = runtime.config.command.permission.requirement_of(command)
        if required_permission == "console":
            if source.is_console:
                return True
            source.reply(self.rtr("manager.console_only"))
            return False
        if source.has_permission(required_permission):
            return True
        source.reply(self.rtr("manager.permission_denied"))
        return False

    def _run_command(
        self,
        command: str,
        source: CommandSource,
        action: CommandAction,
        confirmable: bool = True,
        confirm_if: Optional[Callable[[MirrorRuntime], Optional[bool]]] = None,
    ) -> None:
        """
        Run ``action`` if the manager is available and the source is permitted.

        A confirmable command whose config requires confirmation is parked instead,
        and goes through the availability and permission checks again once confirmed.

        :param confirm_if: asked once, before a confirmable command is run or parked: whether it has to be
            confirmed whatever the config says. None drops the command; reporting why is up to ``confirm_if``
        """
        runtime = self._active_runtime()
        if runtime is None:
            source.reply(self.rtr("manager.unavailable"))
            return

        operator = operator_name(source)
        if confirmable:
            previous = self.confirmations.cancel(operator)
            if previous is not None:
                source.reply(self.rtr("command.confirm.previous", action=previous.action))

        if not self._check_permission(runtime, source, command):
            return
        action_config = runtime.config.command.action
        # execute and log have no action config: they are never confirmed
        must_confirm = confirmable and action_config.requires_confirm(command)
        if confirmable and confirm_if is not None:
            forced = confirm_if(runtime)
            if forced is None:
                return
            must_confirm = must_confirm or forced
        if confirmable and must_confirm:
            self.confirmations.request(
                operator,
                command,
                source,
                lambda: self._run_command(command, source, action, confirmable=False),
                action_config.confirm.timeout,
            )
            source.reply(self.rtr("command.confirm.prompt").set_click_event(RAction.run_command, f"{self.command_prefix} confirm"))
            return
        action(runtime)

    @contextmanager
    def _report_api_error(self, source: CommandSource) -> Iterator[None]:
        """Reply the error to the source; a MCSM request or screen error is swallowed, anything else propagates."""
        try:
            yield
        except MCSManagerProxyError as e:
            source.reply(rtr("mcsm.error.request", e=e))
        except ScreenError as e:
            source.reply(rtr("screen.error", e=e))
        except Exception:
            source.reply(rtr("error.unknown"))
            raise

    def _execute(self, runtime: MirrorRuntime, source: CommandSource, action: Action) -> bool:
        # forcing is a flag of the kill command, not a command of its own
        command = "kill" if action is Action.FORCEKILL else action.value
        with self._report_api_error(source):
            result = runtime.controller.execute(action)
            if result.accepted:
                self.server.broadcast(self.rtr("command._execute.success", prompt=self.rtr(f"command.{command}.success", title=False).to_legacy_text()))
                return True
            for line in rejection_lines(self.rtr, command, result):
                source.reply(line)
        return False

    def status(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("status", source, lambda runtime: self._status(runtime, source))

    def _status(self, runtime: MirrorRuntime, source: CommandSource) -> None:
        with self._report_api_error(source):
            snapshot = runtime.controller.status()
            if snapshot.evidence.empty:
                prompt = self.rtr("command.status.unsupported", title=False).to_legacy_text()
                self.server.broadcast(self.rtr("command._execute.fail", prompt=prompt))
                return
            prompt = self.rtr(f"command.state.{snapshot.state.value}", title=False).to_legacy_text()
            if snapshot.anomalies:
                prompt += " §7/ " + self.rtr(status_key(snapshot), title=False).to_legacy_text()
            self.server.broadcast(self.rtr("command._execute.success", prompt=prompt))
            self._report_status_details(runtime, source, snapshot)

    def _report_status_details(self, runtime: MirrorRuntime, source: CommandSource, snapshot: StatusSnapshot) -> None:
        """Tell ``source`` alone what the status is made of."""
        evidence = snapshot.evidence
        protected: set[str] = set(runtime.config.display.protected_process_info)
        if evidence.port is not None:
            if evidence.mcdr_alive is not None:
                source.reply(self.rtr("command.status.mcdr", title=False, process=self._single_process_text(evidence.mcdr_process, protected)))
            if evidence.child_processes:
                # until the server is told apart, all of them are taken for it
                source.reply(self.rtr("command.status.children", title=False, processes=self._processes_text(evidence.child_processes, protected)))
            else:
                source.reply(self.rtr("command.status.server", title=False, process=self._single_process_text(evidence.server_process, protected)))
            if evidence.others_count:
                source.reply(self.rtr("command.status.others", title=False, count=evidence.others_count))
            if evidence.foreign_listeners:
                self._report_processes(runtime, source, evidence.foreign_listeners, "command.status.foreign", title=False, port=evidence.port)
            else:
                port_state = "listening" if evidence.port_listening else "closed"
                source.reply(self.rtr(f"command.status.port.{port_state}", title=False, port=evidence.port))
        for line in detail_lines(self.rtr, snapshot):
            source.reply(line)

    def _report_processes(
        self, runtime: MirrorRuntime, source: CommandSource, processes: tuple[ProcessInfo, ...], key: str, title: bool = True, **kwargs: Any,
    ) -> None:
        """
        Tell ``source`` about processes under the translation key ``key``, leaving out what the config protects.

        The console always gets their names, pids and command lines.

        :param title: whether the first line starts a message of its own, rather than going on with one
        :param kwargs: for the first line
        """
        for info in processes:
            self.server.logger.info(self.rtr(
                "command.process.console",
                title=False,
                name=info.name or "?",
                pid=info.pid if info.pid is not None else "?",
                cmdline=info.cmdline,
                origin=self.rtr(f"command.process.{'in_record' if info.in_record else 'not_in_record'}", title=False),
            ))
        protected: set[str] = set(runtime.config.display.protected_process_info)
        foreign = sum(not info.in_record for info in processes)
        if {"name", "pid"} <= protected:
            source.reply(self.rtr(f"{key}.count", title, count=len(processes), foreign=foreign, **kwargs))
            return
        source.reply(self.rtr(f"{key}.title", title, count=len(processes), **kwargs))
        for info in processes:
            item = "item" if info.in_record else "item_foreign"
            source.reply(self.rtr(f"command.process.{item}", title=False, process=self._process_text(info, protected)))

    def _single_process_text(self, info: Optional[ProcessInfo], protected: set[str]) -> str:
        if info is None:
            return self.rtr("command.status.not_running", title=False).to_legacy_text()
        if {"name", "pid"} <= protected:
            return self.rtr("command.status.running", title=False).to_legacy_text()
        return self._process_text(info, protected)

    def _processes_text(self, infos: tuple[ProcessInfo, ...], protected: set[str]) -> str:
        if {"name", "pid"} <= protected:
            return self.rtr("command.status.count", title=False, count=len(infos)).to_legacy_text()
        return ", ".join(self._process_text(info, protected) for info in infos)

    def _process_text(self, info: ProcessInfo, protected: set[str]) -> str:
        if info.pid is None:
            return self.rtr("command.process.unreadable", title=False).to_legacy_text()
        name = "" if "name" in protected else info.name or "?"
        pid = "" if "pid" in protected else f"PID {info.pid}"
        return f"{name} ({pid})" if name and pid else name or pid

    def start(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("start", source, lambda runtime: self._start(runtime, source))

    def _start(self, runtime: MirrorRuntime, source: CommandSource) -> bool:
        return self._execute(runtime, source, Action.START)

    def stop(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("stop", source, lambda runtime: self._execute(runtime, source, Action.STOP))

    def kill(self, source: CommandSource, context: CommandContext, force: bool = False) -> None:
        action = Action.FORCEKILL if force else Action.KILL
        self._run_command(
            "kill",
            source,
            lambda runtime: self._execute(runtime, source, action),
            confirm_if=(lambda runtime: self._review_forcekill(runtime, source)) if force else None,
        )

    def _review_forcekill(self, runtime: MirrorRuntime, source: CommandSource) -> Optional[bool]:
        """
        Tell ``source``, before a forced kill is run or confirmed, which processes it would end.

        :return: False; None if there is nothing it could end, so there is nothing to confirm
        """
        with self._report_api_error(source):
            targets = runtime.controller.forcekill_targets()
            if targets is None:
                # the kill itself reports that it is not supported
                return False
            outcome = "unreadable_listener" if targets.unreadable else None if targets.processes else "no_target"
            if outcome is not None:
                prompt = self.rtr(f"command.outcome.{outcome}", title=False).to_legacy_text()
                source.reply(self.rtr("command._execute.fail", prompt=prompt))
                return None
            self._report_processes(runtime, source, tuple(info for info, _ in targets.processes), "command.kill.targets")
            return False
        return None

    def sync(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command(
            "sync",
            source,
            lambda runtime: self._sync(runtime, source),
            confirm_if=lambda runtime: self._review_backup(runtime, source),
        )

    def _review_backup(self, runtime: MirrorRuntime, source: CommandSource) -> Optional[bool]:
        """
        Tell ``source``, before the sync is run or confirmed, what the pre-sync backup would not hold.

        :return: whether the sync has to be confirmed for that; None if no backup can be made, so there is no sync to confirm
        """
        backup = runtime.backup
        if backup is None:
            return False
        try:
            warnings = backup.warnings(backup.resolve())
        except BackupError as e:
            source.reply(self.rtr("command.sync.backup.unavailable", reason=describe_backup_error(self.rtr, e).to_legacy_text()))
            for line in backup_error_console_lines(self.rtr, e):
                self.server.logger.warning(line)
            return None
        if not warnings:
            return False
        source.reply(self.rtr("command.sync.backup.warnings", count=len(warnings)))
        self._log_backup_warnings(warnings)
        return runtime.config.sync.backup.confirm_on_warning

    @new_thread(f"{TITLE}-sync")
    def _sync(self, checked: MirrorRuntime, source: CommandSource) -> None:
        server_stopped = False

        def on_server_stopped() -> None:
            nonlocal server_stopped
            server_stopped = True

        with self._report_api_error(source), self._sync_workflow.hold() as held:
            if not held:
                source.reply(self.rtr("command.sync.fail.task_exist"))
                return
            try:
                # resolved under the hold, so it cannot be replaced before the sync is done
                runtime = self._active_runtime()
                if runtime is None:
                    source.reply(self.rtr("manager.unavailable"))
                    return
                # a reload slipped in after the command was checked; the new config decides
                if runtime is not checked and not self._check_permission(runtime, source, "sync"):
                    return
                self._sync_workflow.run(runtime, source, operator_name(source), on_server_stopped)
            finally:
                # still under the hold: a reload in between would leave the start to a runtime that is being replaced
                if server_stopped:
                    self._run_command("start", source, lambda current: self._start(current, source), confirmable=False)

    def history(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("history", source, lambda runtime: self._history(runtime, source, context))

    def _history(self, runtime: MirrorRuntime, source: CommandSource, context: CommandContext) -> None:
        page = Page(runtime.history.read(), PAGE_SIZE, f"{self.command_prefix} history")
        page.set_page_index(context)
        for record in page.get_items_on_page():
            source.reply(self._get_history_rtext(record))
        source.reply(page.get_rtext())

    def _get_history_rtext(self, record: SyncRecord) -> RTextBase:
        text = self._get_outcome_rtext(record)
        if record.backup_id is None:
            return text
        return RTextList(text, self.rtr("command.history.record.backup", title=False, backup_id=record.backup_id))

    def _get_outcome_rtext(self, record: SyncRecord) -> RTextBase:
        if record.status == SyncStatus.SUCCESS:
            return self.rtr(
                "command.history.record.success",
                title=False,
                time=record.time,
                operator=record.operator,
                duration=record.duration,
                change_file_count=record.changed_files_count,
            )
        if record.status == SyncStatus.IDENTICAL:
            return self.rtr(
                "command.history.record.identical",
                title=False,
                time=record.time,
                operator=record.operator,
                duration=record.duration,
            )
        return self.rtr(
            "command.history.record.failed",
            title=False,
            time=record.time,
            operator=record.operator,
            exception=record.exception,
        )

    def log_help(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("log", source, lambda runtime: self._log_help(runtime, source), confirmable=False)

    def _log_help(self, runtime: MirrorRuntime, source: CommandSource) -> None:
        terminal = runtime.subprocess_terminal
        if terminal is None:
            source.reply(self.rtr("command.log.not_available"))
            return
        status = "enabled" if terminal.console_log_enabled else "disabled"
        source.reply(self.rtr("command.log.status", status=self.rtr(f"command.log.{status}", title=False).to_legacy_text()))
        source.reply(self.rtr("command.log.help"))

    def set_console_log(self, source: CommandSource, context: CommandContext, enabled: bool) -> None:
        self._run_command("log", source, lambda runtime: self._set_console_log(runtime, source, enabled), confirmable=False)

    def _set_console_log(self, runtime: MirrorRuntime, source: CommandSource, enabled: bool) -> None:
        terminal = runtime.subprocess_terminal
        if terminal is None:
            source.reply(self.rtr("command.log.not_available"))
            return
        terminal.set_console_log(enabled)
        terminal.reset_log_limit()
        source.reply(self.rtr("command.log.set_enable" if enabled else "command.log.set_disable"))

    def set_console_log_limit(self, source: CommandSource, context: CommandContext) -> None:
        count: int = context["count"]
        self._run_command("log", source, lambda runtime: self._set_console_log_limit(runtime, source, count), confirmable=False)

    def _set_console_log_limit(self, runtime: MirrorRuntime, source: CommandSource, count: int) -> None:
        terminal = runtime.subprocess_terminal
        if terminal is None:
            source.reply(self.rtr("command.log.not_available"))
            return
        if count < 1:
            source.reply(self.rtr("command.log.invalid_count"))
            return
        terminal.set_console_log_limit(count)
        source.reply(self.rtr("command.log.enabled_count", count=count))

    def mirror_execute(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("execute", source, lambda runtime: self._mirror_execute(runtime, source, context["cmd"]), confirmable=False)

    def _mirror_execute(self, runtime: MirrorRuntime, source: CommandSource, command: str) -> None:
        terminal = runtime.subprocess_terminal
        if terminal is None:
            source.reply(self.rtr("command.execute.not_available"))
            return
        with self._report_api_error(source):
            if runtime.controller.status().state is ServerState.UNKNOWN:
                source.reply(self.rtr("command.execute.unknown"))
                return
            if not terminal.alive:
                source.reply(self.rtr("command.execute.not_running"))
                return
            if not terminal.send_command(command):
                source.reply(self.rtr("command.execute.failed"))
                return
            source.reply(self.rtr("command.execute.sent", cmd=command))

    def _on_confirmation_timeout(self, task: ConfirmationTask) -> None:
        task.source.reply(self.rtr("command.confirm.timeout", action=task.action))

    def confirm(self, source: CommandSource, context: CommandContext) -> None:
        operator = operator_name(source)
        if not self.confirmations.has(operator):
            if self.confirmations.has_any():
                source.reply(self.rtr("command.confirm.others"))
            else:
                source.reply(self.rtr("command.confirm.none"))
            return
        self.confirmations.confirm(operator)

    def on_info(self, _: PluginServerInterface, info: Info) -> None:
        if info.is_from_server and info.content:
            self._sync_workflow.on_server_output(info.content)

    def on_user_info(self, _: PluginServerInterface, info: Info) -> None:
        operator = info.player
        if operator is None or (info.content and info.content.startswith(self.command_prefix)):
            return
        task = self.confirmations.cancel(operator)
        if task is not None:
            self.server.reply(info, self.rtr("command.confirm.cancel", action=task.action))

    def on_unload(self) -> None:
        self.confirmations.clear()
        runtime = self._runtime
        if runtime is not None and runtime.subprocess_terminal is not None:
            runtime.subprocess_terminal.forcekill()
