from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Collection, Iterator, Optional

from mcdreforged.api.all import CommandContext, CommandSource, Info, Literal, PlayerCommandSource, PluginServerInterface, RAction, RColor, RText, RTextBase, RTextList, SimpleCommandBuilder, new_thread, Integer, GreedyText

from mirror_mcsmcdr.constants import TITLE
from mirror_mcsmcdr.config import MultiConfigLoader, MirrorConfig
from mirror_mcsmcdr.mirror_runtime import MirrorRuntime
from mirror_mcsmcdr.sync_workflow import SyncWorkflow
from mirror_mcsmcdr.utils.display_utils import help_msg, rtr
from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxyError
from mirror_mcsmcdr.utils.server_utils import ProxyResult
from mirror_mcsmcdr.utils.status import ServerStatus
from mirror_mcsmcdr.utils.history_utils import SyncRecord, SyncStatus
from mirror_mcsmcdr.utils.page_utils import Page
from mirror_mcsmcdr.utils.confirmation_utils import ConfirmationTask, ConfirmationManager

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
                self.managers[command_prefix] = MirrorManager(
                    server,
                    self.loader.get_mirror_config(command_prefix),
                    command_prefix,
                    reload_method=self.reload_config,
                )
            except Exception as e:
                server.logger.error(rtr("multi_manager.init.error", prefix=command_prefix, e=e))
                server.logger.error(e, exc_info=e)
                failed.append(command_prefix)
        server.register_event_listener("mcdr.general_info", self.on_info)
        server.register_event_listener("mcdr.user_info", self.on_user_info)

        success_info = rtr("multi_manager.init.success", prefix=", ".join(self.managers))
        fail_info = (rtr("multi_manager.init.fail",title=False,prefix=" §7/§c " + " ".join(failed)) if failed else "")
        server.broadcast(RTextList(success_info, " ", fail_info))

    def reload_config(self, prefix: str) -> bool:
        manager = self.managers[prefix]
        try:
            self.loader.load()
        except Exception as e:
            self.server.logger.error(e, exc_info=e)
            self.server.broadcast(manager.rtr("manager.reload.fail"))
            return False
        if prefix not in self.loader.get_all_prefix():
            self.server.broadcast(rtr("multi_manager.init.prefix_notfound", prefix=prefix))
            manager.disable()
            return False
        manager.reload_config(self.loader.get_mirror_config(prefix))
        return True

    def on_info(self, _: PluginServerInterface, info: Info) -> None:
        for manager in self.managers.values():
            manager.on_info(info)

    def on_user_info(self, _: PluginServerInterface, info: Info) -> None:
        for manager in self.managers.values():
            manager.on_user_info(info)

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
        self.confirmations = ConfirmationManager(self._on_confirmation_timeout)
        self._sync_workflow = SyncWorkflow(server, self.rtr)
        # the runtime is kept while disabled, so that its subprocess can still be cleaned up on unload
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
            runtime = MirrorRuntime.build(config, Path(self.server.get_data_folder()) / self.command_prefix)
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
        return True

    def reload_config(self, config: MirrorConfig) -> None:
        previous = self._runtime
        if not self._apply_config(config):
            return
        # the new runtime owns a fresh proxy that cannot reach the process started by the previous one
        if previous is not None and previous.subprocess_terminal is not None:
            previous.subprocess_terminal.forcekill()
        self.server.broadcast(self.rtr("manager.reload.success"))

    def disable(self) -> None:
        self._available = False

    def help(self, source: CommandSource, _: CommandContext) -> None:
        source.reply(help_msg(self.server_name, self.command_prefix))
        if self._runtime is not None:
            source.reply(self._proxy_info(self._runtime))

    @staticmethod
    def _proxy_info(runtime: MirrorRuntime) -> RTextList:
        proxy = runtime.proxy
        info = RTextList(rtr("command.proxy.title", False))
        # a proxy attribute is the proxy itself when enabled, None when disabled, False when misconfigured
        for name, state in (("mcsm", proxy.mcsm), ("rcon", proxy.rcon), ("terminal", proxy.terminal)):
            if state:
                text = RText(name, RColor.green).h(rtr("command.proxy.enabled", False))
            elif state is None:
                text = RText(name, RColor.gray).h(rtr("command.proxy.disabled", False))
            else:
                text = RText(name, RColor.red).h(rtr("command.proxy.error", False))
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
    ) -> None:
        """
        Run ``action`` if the manager is available and the source is permitted.

        A confirmable command whose config requires confirmation is parked instead,
        and goes through the availability and permission checks again once confirmed.
        """
        runtime = self._runtime
        if not self._available or runtime is None:
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
        if confirmable and action_config.requires_confirm(command):
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
        """Reply the error to the source; a MCSM request error is swallowed, anything else propagates."""
        try:
            yield
        except MCSManagerProxyError as e:
            source.reply(rtr("mcsm.error.request", e=e))
        except Exception:
            source.reply(rtr("error.unknown"))
            raise

    def _execute(
        self,
        runtime: MirrorRuntime,
        source: CommandSource,
        command: str,
        available_status: Collection[ServerStatus],
        action: Callable[[], ProxyResult],
    ) -> bool:
        with self._report_api_error(source):
            status_code = runtime.proxy.status()
            if not ServerStatus.is_available(status_code):
                source.reply(self.rtr(f"command.status.fail.{status_code}"))
                return False
            result: ProxyResult = status_code
            if status_code in available_status:
                result = action()
                if result == "success":
                    self.server.broadcast(self.rtr("command._execute.success", prompt=self.rtr(f"command.{command}.success.{status_code}", title=False).to_legacy_text()))
                    return True
            source.reply(self.rtr("command._execute.fail", prompt=self.rtr(f"command.{command}.fail.{result}", title=False).to_legacy_text()))
        return False

    def status(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("status", source, lambda runtime: self._status(runtime, source))

    def _status(self, runtime: MirrorRuntime, source: CommandSource) -> None:
        with self._report_api_error(source):
            status_code = runtime.proxy.status()
            flag = "success" if ServerStatus.is_available(status_code) else "fail"
            prompt = self.rtr(f"command.status.{flag}.{status_code}", title=False).to_legacy_text()
            self.server.broadcast(self.rtr(f"command._execute.{flag}", prompt=prompt))

    def start(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("start", source, lambda runtime: self._start(runtime, source))

    def _start(self, runtime: MirrorRuntime, source: CommandSource) -> bool:
        return self._execute(runtime, source, "start", [ServerStatus.STOPPED], runtime.proxy.start)

    def stop(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("stop", source, lambda runtime: self._execute(
            runtime, source, "stop", [ServerStatus.RUNNING], runtime.proxy.stop,
        ))

    def kill(self, source: CommandSource, context: CommandContext, force: bool = False) -> None:
        self._run_command("kill", source, lambda runtime: self._execute(
            runtime,
            source,
            "kill",
            [ServerStatus.STOPPING, ServerStatus.STARTING, ServerStatus.RUNNING, ServerStatus.DETACHED_JAVA, ServerStatus.DETACHED_SCREEN],
            runtime.proxy.forcekill if force else runtime.proxy.kill,
        ))

    def sync(self, source: CommandSource, context: CommandContext) -> None:
        self._run_command("sync", source, lambda runtime: self._sync(runtime, source))

    @new_thread(f"{TITLE}-sync")
    def _sync(self, runtime: MirrorRuntime, source: CommandSource) -> None:
        with self._report_api_error(source):
            if self._sync_workflow.run(runtime, source, operator_name(source)):
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
        if terminal.status() != ServerStatus.RUNNING:
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

    def on_info(self, info: Info) -> None:
        if info.is_from_server and info.content:
            self._sync_workflow.on_server_output(info.content)

    def on_user_info(self, info: Info) -> None:
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
