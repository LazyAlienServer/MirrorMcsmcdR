from mcdreforged.api.all import PluginServerInterface, CommandSource, CommandContext, Info, SimpleCommandBuilder, new_thread, RTextList, RAction
from mirror_mcsmcdr.constants import DEFAULT_CONFIG, TITLE
from mirror_mcsmcdr.utils.proxy.mcsm_proxy import MCSManagerProxyError
from mirror_mcsmcdr.utils.server_utils import ServerProxy
from mirror_mcsmcdr.utils.file_operation import WorldSync
from mirror_mcsmcdr.utils.display_utils import rtr, help_msg
from typing import Callable
from threading import Event, Timer
from copy import deepcopy
from functools import wraps
import time, re
 
 
def catch_api_error(func):
    def wrapper(self, source: CommandSource, command: str, *args, **kwargs):
        try:
            return func(self, source, command, *args, **kwargs)
        except MCSManagerProxyError as e:
            source.reply(rtr("mcsm.error.request", e=e))
        except Exception as e:
            source.reply(rtr("mcsm.error.unknown", e=e))
            raise e
    return wrapper


class MultiMirrorManager: # The manager at large which manage multi single mirror server manager

    def __init__(self, server: PluginServerInterface) -> None:
        self.server = server
        config, default_conf = self.load_config_all()

        self.managers = {}

        succeed, failed = [], []
        for command_prefix, single_conf in config.items():
            try:
                single_conf = self._conf_update(default_conf, single_conf)
                single_manager = MirrorManager(server, single_conf, command_prefix, reload_method=self.reload_config)
                server.register_event_listener('mcdr.general_info', single_manager.on_info)
                server.register_event_listener('mcdr.user_info', single_manager.on_user_info)
                self.managers[command_prefix] = single_manager
                succeed.append(command_prefix)
            except Exception as e:
                server.logger.error(rtr("multi_manager.init.error", prefix=command_prefix, e=e))
                failed.append(command_prefix)
        success_info = rtr("multi_manager.init.success", prefix=', '.join(succeed))
        fail_info = rtr("multi_manager.init.fail", title=False, prefix=' §7/§c '+' '.join(failed)) if failed else ''
        server.logger.info(success_info)
        server.say(RTextList(success_info, " ", fail_info))
    

    def _conf_update(self, default_conf: dict, new_conf: dict):
        default_conf = deepcopy(default_conf)
        for key, value in new_conf.items():
            if key not in default_conf.keys():
                continue
            if type(value) == dict:
                default_conf[key] =  self._conf_update(default_conf[key], new_conf[key])
            elif default_conf[key] != value:
                default_conf[key] = value
        return default_conf
    

    def load_config_all(self):
        try:
            config = self.server.load_config_simple()
        except:
            config = self.server.load_config_simple(default_config=DEFAULT_CONFIG)
        default_prefix = list(config.keys())[0]
        default_conf = self._conf_update(DEFAULT_CONFIG["!!mirror"], config[default_prefix])
        if config[default_prefix] != default_conf:
            config[default_prefix] = default_conf
            self.server.save_config_simple(config)
        return config, default_conf


    def reload_config(self, prefix):
        manager: MirrorManager = self.managers[prefix]
        config, default_conf = self.load_config_all()
        if prefix not in config.keys():
            manager.config_error()
            return False
        single_config = self._conf_update(default_conf, config[prefix])
        manager.reload_config(single_config)


class MirrorManager: # The single mirror server manager which manages a specific mirror server


    def __init__(self, server: PluginServerInterface, config: dict, command_prefix: str, reload_method: Callable) -> None:
        self.server = server

        server.logger.info(rtr("manager.load", prefix = command_prefix))
        self.command_prefix = command_prefix

        # init flag
        self.sync_flag = False
        self.save_world_wait = Event()
        self.save_world_wait.set()
        self.confirmation = {}

        # register mcdr command
        builder = SimpleCommandBuilder()
        builder.command(f"{command_prefix}", self.help)
        builder.command(f"{command_prefix} reload", lambda source, context: reload_method(command_prefix))
        
        # check config
        if not self.set_config(config):
            builder.register(server)
            return
        builder.command(f"{command_prefix} help", self.help)
        builder.command(f"{command_prefix} status", self.status)
        builder.command(f"{command_prefix} start", self.start)
        builder.command(f"{command_prefix} stop", self.stop)
        builder.command(f"{command_prefix} kill", self.kill)
        builder.command(f"{command_prefix} sync", self.sync)
        builder.command(f"{command_prefix} confirm", self.confirm)
        builder.register(server)


    def rtr(self, key, title=True, *args, **kwargs):
        return rtr(key, title, prefix = self.command_prefix, server_name = self.server_name, *args, **kwargs)


    def set_config(self, config):
        try:
            self.config, self.world_sync, self.permission, self.command_action, self.server_name = \
                config, WorldSync(**config["sync"]), config["command"]["permission"], config["command"]["action"], config["display"]["server_name"]
            self.server_api = ServerProxy()
            self.server_api.set_mcsm(**self.config["mcsm"])
            self.server_api.set_rcon(**self.config["rcon"])
            terminal = self.server_api.set_system(**self.config["terminal"])
            if type(terminal) == str:
                self.server.broadcast(self.rtr("manager.reload.fail.unavailable_system"))
            return True
        except Exception as e:
            self.config_error()
            return False


    def reload_config(self, config):
        if not self.set_config(config):
            self.config_error()
            return
        self.broadcast(self.rtr("manager.reload.success"))


    def config_error(self):
        info = self.rtr("manager.reload.fail")
        self.server.logger.warn(info)
        self.server.say(info)


    def broadcast(self, text):
        self.server.broadcast(text)


    def help(self, source: CommandSource, context: CommandContext):
        source.reply(help_msg(self.server_name, self.command_prefix))


    def check_permission(self, source: CommandSource, command: str):
        if not source.has_permission(self.permission[command]):
            source.reply(self.rtr("manager.permission_denied"))
            return False
        return True


    def pre_check(command):
        def wrapper(func):
            @wraps(func)
            def sub_wrapper(self, source: CommandSource, context: CommandContext, confirm=False, *args, **kwargs):
                operator = source.player if source.is_player else "[console]"
                
                # automatically cancel old operation
                if operator in self.confirmation.keys():
                    source.reply(self.rtr("command.confirm.previous", action=self.confirmation[operator]['action']))
                    self.confirm_end(operator)

                if not self.check_permission(source, command):
                    return
                if not confirm and self.command_action[command]["require_confirm"]:
                    timer = Timer(self.command_action["confirm"]["timeout"], self.confirm_timer, args=[source, context, operator])
                    self.confirmation[operator] = {"func":func, "timer":timer, "action":command}
                    timer.start()

                    run_command = f"{self.command_prefix} confirm"
                    source.reply(self.rtr("command.confirm.prompt").set_click_event(RAction.run_command, run_command))
                    return
                return func(self, source, context, *args, **kwargs)
            return sub_wrapper
        return wrapper


    @catch_api_error
    def _execute(self, source: CommandSource, command: str, available_status: list): # <failed_prompt> & <succeeded_prompt> : {status_code: "prompt"}
        status_code = self.server_api.status()
        if not self.status_available(status_code):
            source.reply(self.rtr(f"command.status.fail.{status_code}"))
            return False
        if status_code in available_status:
            rep = getattr(self.server_api, command)()
            if rep == "success":
                self.broadcast(self.rtr("command._execute.success", prompt=self.rtr(f"command.{command}.success.{status_code}", title=False).to_legacy_text()))
                return True
            status_code = rep
        source.reply(self.rtr("command._execute.fail", prompt=self.rtr(f"command.{command}.fail.{status_code}", title=False).to_legacy_text()))
        return False


    def status_available(self, status):
        return status in ["unknown", "stopped", "stopping", "starting", "running"]


    @catch_api_error
    @pre_check(command="status")
    def status(self, source: CommandSource, context: CommandContext):
        status_code = self.server_api.status()
        flag = "success" if self.status_available(status_code) else "fail"
        self.broadcast(self.rtr(f"command._execute.{flag}", prompt=self.rtr(f"command.status.{flag}.{status_code}", title=False).to_legacy_text()))


    @pre_check(command="start")
    def start(self, source: CommandSource, context: CommandContext):
        return self._execute(source, "start", ["stopped"])


    @pre_check(command="stop")
    def stop(self, source: CommandSource, context: CommandContext):
        return self._execute(source, "stop", ["running"])


    @pre_check(command="kill")
    def kill(self, source: CommandSource, context: CommandContext):
        return self._execute(source, "kill", ["stopping", "starting", "running"])


    @pre_check(command="sync")
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
            
            if status_code == "stopped":
                pass
            elif status_code != "running" or not sync_action_config["auto_server_restart"]:
                source.reply(self.rtr(f"command.sync.fail.{status_code}"))
                return
            else: # restart server
                self.broadcast(self.rtr("command.sync.auto_restart.restarting"))
                if not self.stop(source, context, confirm=True):
                    return
                interval, times = sync_action_config["check_status_interval"], sync_action_config["max_attempt_times"]
                for i in range(times): # wait for server to stop
                    time.sleep(interval)
                    status_code = self.server_api.status()
                    if status_code == "stopped":
                        break
                    if not self.status_available(status_code): # if status command is not available, skip and end
                        self.broadcast(self.rtr("command.sync.auto_restart.fail", status=self.rtr(f"command.status.failed.{status_code}", title=False)))
                        return
                else:
                    self.broadcast(self.rtr("command.sync.auto_restart.fail", status=self.rtr(f"command.status.success.{status_code}", title=False)))
                    return
                auto_restart_flag = True

        self.sync_flag = True
        try:
            self.broadcast(self.rtr("command.sync.success"))
            t = time.time()

            # save the world
            save_world_config = sync_action_config["save_world"]
            turn_off_auto_save = save_world_config["turn_off_auto_save"]
            if turn_off_auto_save:
                self.server.execute(save_world_config["commands"]["auto_save_off"])
            self.save_world_wait.clear()
            self.server.execute(save_world_config["commands"]["save_all_worlds"])
            self.save_world_wait.wait(timeout=save_world_config["save_world_max_wait_sec"]) # wait for finishing saving world
            if turn_off_auto_save:
                self.server.execute(save_world_config["commands"]["auto_save_on"])

            # sync
            changed_files_count, paths_notfound = self.world_sync.sync()

            # calc time
            m, s = divmod(time.time()-t, 60)
            h, m = divmod(m, 60)
            t = ("%02d:"%h if h else "") + ("%02d:"%m if m else "") + ("%02d"%s if m or h else ("%.02f"%s).zfill(5))
            if paths_notfound:
                self.broadcast(self.rtr("command.sync.skip_dictionary", paths='§f`§7'.join(paths_notfound)))
            self.broadcast(self.rtr("command.sync.completed", time=t, changed_files_count=changed_files_count) if changed_files_count != 0 else self.rtr("command.sync.identical"))
        except Exception as e:
            self.broadcast(self.rtr("command.sync.error", e=e))
        self.sync_flag = False

        if auto_restart_flag:
            self.start(source, context)


    def confirm(self, source: CommandSource, context: CommandContext):
        operator = source.player if source.is_player else "[console]"
        if operator not in self.confirmation.keys():
            if self.confirmation.keys():
                source.reply(self.rtr("command.confirm.others"))
                return
            source.reply(self.rtr("command.confirm.none"))
            return
        self.confirm_end(operator, source, context)


    def confirm_timer(self, source: CommandSource, context: CommandContext, operator):
        source.reply(self.rtr("command.confirm.timeout", action=self.confirmation[operator]['action']))
        self.confirmation.pop(operator)


    def confirm_end(self, operator, source: CommandSource=None, context: CommandContext=None):
        self.confirmation[operator]["timer"].cancel()
        if source != None and context != None:
            self.confirmation[operator]["func"](self, source, context)
        self.confirmation.pop(operator)


    def on_info(self, server: PluginServerInterface, info: Info):
        if self.config and not self.save_world_wait.is_set() and info.is_from_server and re.match(self.command_action["sync"]["save_world"]["saved_world_regex"], info.content):
            self.save_world_wait.set() # stop waiting in sync function


    def on_user_info(self, server: PluginServerInterface, info: Info):
        operator = info.player
        if info.content[:len(self.command_prefix)] == self.command_prefix:
            return
        if operator in self.confirmation.keys():
            server.reply(info, self.rtr("command.confirm.cancel", action=self.confirmation[operator]['action']))
            self.confirm_end(operator)