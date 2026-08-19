import re
import time
from copy import deepcopy
from functools import wraps
from threading import Event, Timer
from typing import Any, Callable, Dict, Optional, Union, cast

from mcdreforged.api.all import CommandContext, CommandSource, Info, Literal, PluginServerInterface, RAction, RColor, RText, \
    RTextList, SimpleCommandBuilder, new_thread

from mirror_mcsmcdr.constants import DEFAULT_CONFIG, TITLE
from mirror_mcsmcdr.utils.display_utils import help_msg, rtr
from mirror_mcsmcdr.utils.sync.classic_synchronizer import ClassicWorldSynchronizer
from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxyError
from mirror_mcsmcdr.utils.server_utils import ProxySettingException, ServerProxy, TerminalSettingException
from mirror_mcsmcdr.utils.status import ServerStatus


def catch_api_error(func):
    @wraps(func)
    def wrapper(self, source: CommandSource, *args, **kwargs):
        try:
            return func(self, source, *args, **kwargs)
        except MCSManagerProxyError as e:
            source.reply(rtr("mcsm.error.request", e=e))
        except Exception as e:
            source.reply(rtr("error.unknown"))
            raise e

    return wrapper


def command_call(command: str):
    def decorator(function):
        @wraps(function)
        def wrapper(self, source: CommandSource, context: CommandContext, *args, **kwargs):
            confirmed = kwargs.pop("_confirmed", False)
            return self._call_command(
                command,
                function,
                wrapper,
                source,
                context,
                args,
                kwargs,
                confirmed,
            )

        return wrapper

    return decorator


class ConfirmationTask:
    def __init__(
        self,
        action: str,
        source: CommandSource,
        context: CommandContext,
        callback: Callable[..., Any],
        callback_args: tuple,
        callback_kwargs: dict,
    ) -> None:
        self.action = action
        self.source = source
        self.context = context
        self.callback = callback
        self.callback_args = callback_args
        self.callback_kwargs = callback_kwargs
        self.timer: Optional[Timer] = None

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()

    def execute(self):
        return self.callback(*self.callback_args, **self.callback_kwargs)


class ConfirmationManager:
    def __init__(self, timeout: float, on_timeout: Callable[[ConfirmationTask], None]) -> None:
        self.timeout = timeout
        self.on_timeout = on_timeout
        self.tasks: Dict[str, ConfirmationTask] = {}

    def request(
        self,
        operator: str,
        action: str,
        source: CommandSource,
        context: CommandContext,
        callback: Callable[..., Any],
        callback_args: tuple,
        callback_kwargs: dict,
    ):
        task = ConfirmationTask(
            action,
            source,
            context,
            callback,
            callback_args,
            callback_kwargs,
        )
        task.timer = Timer(self.timeout, self._timeout, args=(operator,))
        self.tasks[operator] = task
        task.timer.start()

    def _timeout(self, operator: str):
        task = self.tasks.pop(operator, None)
        if task is not None:
            self.on_timeout(task)

    def cancel(self, operator: str) -> Optional[ConfirmationTask]:
        task = self.tasks.pop(operator, None)
        if task is not None:
            task.cancel()
        return task

    def confirm(self, operator: str) -> Optional[ConfirmationTask]:
        task = self.cancel(operator)
        if task is not None:
            task.execute()
        return task

    def has(self, operator: str) -> bool:
        return operator in self.tasks

    def has_any(self) -> bool:
        return bool(self.tasks)

    def clear(self):
        for operator in tuple(self.tasks):
            self.cancel(operator)


class MultiMirrorManager:  # The manager at large which manage multi single mirror server manager

    def __init__(self, server: PluginServerInterface) -> None:
        self.server = server
        config, default_conf = self.load_config_all()

        self.managers = {}

        succeed, failed = [], []
        for command_prefix, single_conf in config.items():
            try:
                single_conf = self._conf_update(default_conf, single_conf)
                single_manager = MirrorManager(
                    server,
                    single_conf,
                    command_prefix,
                    reload_method=self.reload_config,
                )
                server.register_event_listener(
                    "mcdr.general_info", single_manager.on_info
                )
                server.register_event_listener(
                    "mcdr.user_info", single_manager.on_user_info
                )
                self.managers[command_prefix] = single_manager
                succeed.append(command_prefix)
            except Exception as e:
                server.logger.error(
                    rtr("multi_manager.init.error", prefix=command_prefix, e=e)
                )
                failed.append(command_prefix)
        success_info = rtr("multi_manager.init.success",
                           prefix=", ".join(succeed))
        fail_info = (
            rtr(
                "multi_manager.init.fail",
                title=False,
                prefix=" §7/§c " + " ".join(failed),
            )
            if failed
            else ""
        )
        server.logger.info(success_info)
        server.say(RTextList(success_info, " ", fail_info))

    def _conf_update(self, default_conf: dict, new_conf: dict):
        default_conf = deepcopy(default_conf)
        for key, value in new_conf.items():
            if key not in default_conf.keys():
                continue
            if type(value) == dict:
                default_conf[key] = self._conf_update(
                    default_conf[key], new_conf[key])
            elif default_conf[key] != value:
                default_conf[key] = value
        return default_conf

    def load_config_all(self):
        try:
            config = self.server.load_config_simple()
        except:
            config = self.server.load_config_simple(
                default_config=DEFAULT_CONFIG)
        default_prefix = list(config.keys())[0]
        default_conf = self._conf_update(
            DEFAULT_CONFIG["!!mirror"], config[default_prefix]
        )
        if config[default_prefix] != default_conf:
            config[default_prefix] = default_conf
            self.server.save_config_simple(config)
        return config, default_conf

    def reload_config(self, prefix):
        manager: MirrorManager = self.managers[prefix]
        config, default_conf = self.load_config_all()
        if prefix not in config.keys():
            rtr("multi_manager.init.prefix_notfound", prefix=prefix)
            manager.manager_available = False
            return False
        single_config = self._conf_update(default_conf, config[prefix])
        manager.reload_config(single_config)


class MirrorManager:  # The single mirror server manager which manages a specific mirror server

    def __init__(
        self,
        server: PluginServerInterface,
        config: dict,
        command_prefix: str,
        reload_method: Callable,
    ) -> None:
        self.manager_available: bool = False
        self.server = server

        server.logger.info(rtr("manager.load", prefix=command_prefix))
        self.command_prefix = command_prefix

        # init flag
        self.sync_flag: bool = False
        self.save_world_wait: Event = Event()
        self.save_world_wait.set()
        self.confirmations: ConfirmationManager

        # register mcdr command
        builder = SimpleCommandBuilder()
        builder.command(f"{command_prefix}", self.help)
        builder.command(
            f"{command_prefix} reload",
            lambda source, context: reload_method(command_prefix),
        )
        builder.command(f"{command_prefix} help", self.help)
        builder.command(f"{command_prefix} status", self.status)
        builder.command(f"{command_prefix} start", self.start)
        builder.command(f"{command_prefix} stop", self.stop)
        builder.command(f"{command_prefix} kill", self.kill)
        builder.literal("-f", lambda _: Literal(("-f", "--force")))
        builder.command(f"{command_prefix} kill -f", lambda source, context: self.kill(source, context, force=True))
        builder.command(f"{command_prefix} sync", self.sync)
        builder.command(f"{command_prefix} confirm", self.confirm)
        builder.register(server)
        if not self.set_config(config):
            return
        self.manager_available = True

    def rtr(self, key, title=True, *args, **kwargs):
        return rtr(
            key,
            title,
            prefix=self.command_prefix,
            server_name=self.server_name,
            *args,
            **kwargs,
        )

    def set_config(self, config):
        try:
            (
                self.config,
                self.world_sync,
                self.permission,
                self.command_action,
                self.server_name,
            ) = (
                config,
                ClassicWorldSynchronizer(**config["sync"]),
                config["command"]["permission"],
                config["command"]["action"],
                config["display"]["server_name"],
            )
            self.server_api = ServerProxy()
            for proxy in self.server_api.proxies:
                try:
                    _obj = getattr(self.server_api, f"set_{proxy}", None)
                    if not callable(_obj):
                        raise ProxySettingException(
                            proxy,
                            missing_keys=[f"set_{proxy}"]
                        )
                    _ = cast(Callable[..., Any], _obj)
                    _(**self.config[proxy])
                except ProxySettingException as e:
                    self.server.broadcast(
                        self.rtr(
                            "manager.reload.fail.proxy",
                            proxy=e.proxy,
                            keys="', '".join(e.missing_keys),
                        )
                    )
                except TerminalSettingException as _:
                    self.server.broadcast(
                        self.rtr("manager.reload.fail.unavailable_system")
                    )
            self.confirmations = ConfirmationManager(
                self.command_action["confirm"]["timeout"],
                self._on_confirmation_timeout,
            )
            return True
        except Exception as e:
            if self.server.is_server_startup():
                self.server.say(self.rtr("manager.reload.fail"))
            self.server.logger.error(e, exc_info=e)

    def reload_config(self, config):
        self.manager_available = False
        if not self.set_config(config):
            return
        self.server.broadcast(self.rtr("manager.reload.success"))
        self.manager_available = True

    def help(self, source: CommandSource, _: CommandContext):
        source.reply(help_msg(self.server_name, self.command_prefix))
        source.reply(self.proxy_info())

    def proxy_info(self):
        info = RTextList(rtr("command.proxy.title", False))
        for proxy in self.server_api.proxies:
            if _proxy := getattr(self.server_api, proxy):
                text = RText(proxy, RColor.green).h(
                    rtr("command.proxy.enabled", False))
            elif _proxy is None:
                text = RText(proxy, RColor.gray).h(
                    rtr("command.proxy.disabled", False))
            else:
                text = RText(proxy, RColor.red).h(
                    rtr("command.proxy.error", False))
            info.append(" | ", text)
        return info

    def check_permission(self, source: CommandSource, command: str):
        if not source.has_permission(self.permission[command]):
            source.reply(self.rtr("manager.permission_denied"))
            return False
        return True

    def _call_command(
        self,
        command: str,
        function: Callable[..., Any],
        wrapper: Callable[..., Any],
        source: CommandSource,
        context: CommandContext,
        args: tuple,
        kwargs: dict,
        confirmed: bool,
    ):
        if not self.manager_available:
            source.reply(self.rtr("manager.unavailable"))
            return

        operator = source.player if source.is_player else "[console]"
        if self.confirmations.has(operator) and not confirmed:
            task = self.confirmations.cancel(operator)
            source.reply(self.rtr("command.confirm.previous", action=task.action))

        if not self.check_permission(source, command):
            return False
        if not confirmed and self.command_action[command]["require_confirm"]:
            self.confirmations.request(
                operator,
                command,
                source,
                context,
                wrapper,
                (self, source, context, *args),
                {**kwargs, "_confirmed": True},
            )
            source.reply(
                self.rtr("command.confirm.prompt").set_click_event(
                    RAction.run_command, f"{self.command_prefix} confirm"
                )
            )
            return False
        return function(self, source, context, *args, **kwargs)

    @catch_api_error
    def _execute(
        self, source: CommandSource, command: str, available_status: list[ServerStatus],
        backend_command: Optional[str] = None,
    ):  # <failed_prompt> & <succeeded_prompt> : {status_code: "prompt"}
        status_code = self.server_api.status()
        if not ServerStatus.is_available(status_code):
            source.reply(self.rtr(f"command.status.fail.{status_code}"))
            return False
        if status_code in available_status:
            action_name = backend_command or command
            action_obj = getattr(self.server_api, action_name, None)
            if not callable(action_obj):
                raise ProxySettingException(
                    action_name,
                    missing_keys=[action_name],
                )
            action = cast(Callable[[], Optional[Union[str, ServerStatus]]], action_obj)
            rep: Optional[Union[str, ServerStatus]] = action()
            if rep == "success":
                self.server.broadcast(
                    self.rtr(
                        "command._execute.success",
                        prompt=self.rtr(
                            f"command.{command}.success.{status_code}", title=False
                        ).to_legacy_text(),
                    )
                )
                return True
            status_code = rep
        source.reply(
            self.rtr(
                "command._execute.fail",
                prompt=self.rtr(
                    f"command.{command}.fail.{status_code}", title=False
                ).to_legacy_text(),
            )
        )
        return False

    @command_call("status")
    @catch_api_error
    def status(self, source: CommandSource, context: CommandContext):
        status_code = self.server_api.status()
        flag = "success" if ServerStatus.is_available(status_code) else "fail"
        prompt = self.rtr(f"command.status.{flag}.{status_code}", title=False).to_legacy_text()
        self.server.broadcast(
            self.rtr(
                f"command._execute.{flag}",
                prompt=prompt,
            )
        )

    @command_call("start")
    def start(self, source: CommandSource, context: CommandContext):
        return self._execute(source, "start", [ServerStatus.STOPPED])

    @command_call("stop")
    def stop(self, source: CommandSource, context: CommandContext):
        return self._execute(source, "stop", [ServerStatus.RUNNING])

    @command_call("kill")
    def kill(
        self, source: CommandSource, context: CommandContext, force=False,
    ):
        return self._execute(
            source,
            "kill",
            [ServerStatus.STOPPING, ServerStatus.STARTING, ServerStatus.RUNNING, ServerStatus.DETACHED_JAVA, ServerStatus.DETACHED_SCREEN],
            "forcekill" if force else None,
        )
    @command_call("sync")
    @new_thread(f"{TITLE}-sync")
    @catch_api_error
    def sync(self, source: CommandSource, context: CommandContext):

        if self.sync_flag:
            source.reply(self.rtr("command.sync.fail.task_exist"))
            return

        auto_restart_flag = False
        sync_action_config = self.command_action["sync"]
        if sync_action_config["ensure_server_closed"]:
            status_code = self.server_api.status()

            if status_code == ServerStatus.STOPPED:
                pass
            elif (
                status_code != ServerStatus.RUNNING
                or not sync_action_config["auto_server_restart"]
            ):
                source.reply(self.rtr(f"command.sync.fail.{status_code}"))
                return
            else:  # restart server
                self.server.broadcast(
                    self.rtr("command.sync.auto_restart.restarting"))
                self.server_api.stop()
                interval, times = (
                    sync_action_config["check_status_interval"],
                    sync_action_config["max_attempt_times"],
                )
                for _ in range(times):  # wait for server to stop
                    time.sleep(interval)
                    status_code = self.server_api.status()
                    if status_code == ServerStatus.STOPPED:
                        break
                    if not ServerStatus.is_available(
                        status_code
                    ):  # if status command is not available, skip and end
                        self.server.broadcast(
                            self.rtr(
                                "command.sync.auto_restart.fail",
                                status=self.rtr(
                                    f"command.status.failed.{status_code}", title=False
                                ),
                            )
                        )
                        return
                else:
                    self.server.broadcast(
                        self.rtr(
                            "command.sync.auto_restart.fail",
                            status=self.rtr(
                                f"command.status.success.{status_code}", title=False
                            ),
                        )
                    )
                    return
                auto_restart_flag = True

        self.sync_flag = True
        try:
            self.server.broadcast(self.rtr("command.sync.success"))
            t = time.time()

            # save the world
            save_world_config = sync_action_config["save_world"]
            turn_off_auto_save = save_world_config["turn_off_auto_save"]
            if turn_off_auto_save:
                self.server.execute(
                    save_world_config["commands"]["auto_save_off"])
            self.save_world_wait.clear()
            self.server.execute(
                save_world_config["commands"]["save_all_worlds"])
            self.save_world_wait.wait(
                timeout=save_world_config["save_world_max_wait_sec"]
            )  # wait for finishing saving world
            if turn_off_auto_save:
                self.server.execute(
                    save_world_config["commands"]["auto_save_on"])

            # sync
            changed_files_count, paths_notfound = self.world_sync.sync()

            # calc time
            m, s = divmod(time.time() - t, 60)
            h, m = divmod(m, 60)
            t = (
                ("%02d:" % h if h else "")
                + ("%02d:" % m if m else "")
                + ("%02d" % s if m or h else ("%.02f" % s).zfill(5))
            )
            if paths_notfound:
                self.server.broadcast(
                    self.rtr(
                        "command.sync.skip_dictionary",
                        paths="§f`§7".join(paths_notfound),
                    )
                )
            self.server.broadcast(
                self.rtr(
                    "command.sync.completed",
                    time=t,
                    changed_files_count=changed_files_count,
                )
                if changed_files_count != 0
                else self.rtr("command.sync.identical")
            )
        except Exception as e:
            self.server.broadcast(self.rtr("command.sync.error"))
            self.server.logger.error(e, exc_info=e)
        finally:
            self.sync_flag = False

            if auto_restart_flag:
                self.start(source, context, _confirmed=True)


    def _on_confirmation_timeout(self, task: ConfirmationTask):
        task.source.reply(
            self.rtr("command.confirm.timeout", action=task.action)
        )

    def confirm(self, source: CommandSource, context: CommandContext):
        operator = source.player if source.is_player else "[console]"
        if not self.confirmations.has(operator):
            if self.confirmations.has_any():
                source.reply(self.rtr("command.confirm.others"))
            else:
                source.reply(self.rtr("command.confirm.none"))
            return
        self.confirmations.confirm(operator)

    def on_info(self, _: PluginServerInterface, info: Info):
        if (
            self.config
            and not self.save_world_wait.is_set()
            and info.is_from_server
            and re.match(
                self.command_action["sync"]["save_world"]["saved_world_regex"],
                info.content,
            )
        ):
            self.save_world_wait.set()  # stop waiting in sync function

    def on_user_info(self, server: PluginServerInterface, info: Info):
        operator = info.player
        if info.content[: len(self.command_prefix)] == self.command_prefix:
            return
        task = self.confirmations.cancel(operator)
        if task is not None:
            server.reply(
                info,
                self.rtr("command.confirm.cancel", action=task.action),
            )
