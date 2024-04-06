from mcdreforged.api.all import PluginServerInterface, CommandSource, CommandContext, Info, SimpleCommandBuilder, event_listener, new_thread
from mirror_mcsmcdr.constants import DEFAULT_CONFIG, REPLY_TITLE, TITLE, VERSION
from mirror_mcsmcdr.mcsm_api import MCSManagerApi, MCSManagerApiError
from mirror_mcsmcdr.file_operation import WorldSync
from threading import Event
from copy import deepcopy
import time, json, re
 
 
def catch_api_error(func):
    def wrapper(self, source: CommandSource, command: str, *args, **kwargs):
        try:
            return func(self, source, command, *args, **kwargs)
        except MCSManagerApiError as e:
            source.reply(f"{REPLY_TITLE} §cMCSM请求错误, 请回报管理员: {e}")
        except Exception as e:
            source.reply(f"{REPLY_TITLE} §c未知错误, 请回报管理员: {e}")
            raise e
    return wrapper


class MultiMirrorManager: # The manager at large which manage multi single mirror server manager

    def __init__(self, server: PluginServerInterface) -> None:
        try:
            config = server.load_config_simple()
        except:
            config = server.load_config_simple(default_config=DEFAULT_CONFIG)

        default_conf = config[list(config.keys())[0]]
        self.managers = {}
        for tag, single_conf in config.items():
            server.logger.info(f"{tag}正在注册")
            single_conf = self._conf_update(default_conf, single_conf)
            single_manager = MirrorManager(server, single_conf, tag)
            server.register_event_listener('mcdr.general_info', single_manager.on_info)
            self.managers[tag] = single_manager
    

    def _conf_update(self, default_conf: dict, new_conf: dict):
        default_conf = deepcopy(default_conf)
        for key, value in new_conf.items():
            if type(value) == dict:
                default_conf[key] =  self._conf_update(default_conf[key], new_conf[key])
            elif default_conf[key] != value:
                default_conf[key] = value
        return default_conf
        
        
class MirrorManager: # The single mirror server manager which manage a specific mirror server


    def __init__(self, server: PluginServerInterface, config: dict, tag="default") -> None:
        self.server = server

        server.logger.info(f"{tag}已加载")
        command_prefix = tag
        # check config
        self.config = config
        if None in self.config["mcsm"].values():
            server.logger.warn(f"请设置配置文件({command_prefix})")
            server.say(f"§c请设置配置文件§7({command_prefix})")
            self.config = None
            return
        
        # register api and file operation method
        self.mcsm_api = MCSManagerApi(**self.config["mcsm"])
        self.world_sync = WorldSync(**self.config["sync"])

        # set constants
        self.permission = self.config["command"]["permission"]
        self.server_name = self.config["display"]["server_name"]

        # init flag
        self.sync_flag = False
        self.save_world_wait = Event()

        # help info
        self.help_msg = [
            {"text":""},
            {"text":f"§7----- §e{TITLE} §b{VERSION} §7-----§f\n"},
            {"text":f"§7{command_prefix} help §f","clickEvent":{"action":"run_command","value":f"{command_prefix} help"}},
            {"text":"显示此帮助信息\n"},
            {"text":f"§7{command_prefix} status §f","clickEvent":{"action":"run_command","value":f"{command_prefix} status"}},
            {"text":f"查看{self.server_name}状态\n"},
            {"text":f"§7{command_prefix} start §f","clickEvent":{"action":"run_command","value":f"{command_prefix} start"}},
            {"text":f"启动{self.server_name}\n"},
            {"text":f"§7{command_prefix} stop §f","clickEvent":{"action":"run_command","value":f"{command_prefix} stop"}},
            {"text":f"停止{self.server_name}\n"},
            {"text":f"§7{command_prefix} kill §f","clickEvent":{"action":"run_command","value":f"{command_prefix} kill"}},
            {"text":f"强制终止{self.server_name}\n"},
            {"text":f"§7{command_prefix} sync §f","clickEvent":{"action":"run_command","value":f"{command_prefix} sync"}},
            {"text":f"同步{self.server_name}"},
        ]

        # register mcdr command
        builder = SimpleCommandBuilder()
        builder.command(f"{command_prefix}", self.help)
        builder.command(f"{command_prefix} help", self.help)
        builder.command(f"{command_prefix} status", self.status)
        builder.command(f"{command_prefix} start", self.start)
        builder.command(f"{command_prefix} stop", self.stop)
        builder.command(f"{command_prefix} kill", self.kill)
        builder.command(f"{command_prefix} sync", self.sync)
        builder.command(f"{command_prefix} sync", self.sync)
        builder.register(server)


    def broadcast(self, text):
        self.server.say(text)
        self.server.logger.info(text)


    def help(self, source: CommandSource, context: CommandContext):
        if source.is_player:
            self.server.execute(f"tellraw {source.player} {json.dumps(self.help_msg)}")
        elif source.is_console:
            self.server.logger.info("\n"+"".join([i["text"] for i in self.help_msg]))


    @catch_api_error
    def _execute(self, source: CommandSource, command: str, failed_prompt: dict, succeeded_prompt: dict): # <failed_prompt> & <succeeded_prompt> : {status_code: "prompt"}
        if not source.has_permission_higher_than(self.permission[command]):
            source.reply(f"{REPLY_TITLE} §7({self.server_name})§c权限不足")
            return
        status_code = self.mcsm_api.status()
        if status_code in failed_prompt.keys():
            source.reply(f"{REPLY_TITLE} §7({self.server_name})§c失败: "+failed_prompt[status_code])
        elif status_code in succeeded_prompt.keys():
            rep = eval(f"self.mcsm_api.{command}()")
            self.server.logger.info(rep)
            self.broadcast(f"{REPLY_TITLE} §a"+succeeded_prompt[status_code])

        
    @catch_api_error
    def status(self, source: CommandSource, context: CommandContext):
        if not source.has_permission_higher_than(self.permission["status"]):
            source.reply(f"{REPLY_TITLE} §7({self.server_name})§c权限不足")
            return
        source.reply(f"{REPLY_TITLE} §7({self.server_name})§b{self.server_name}§f{self.mcsm_api.status_to_text[self.mcsm_api.status()]}")


    def start(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "start",
            {-1: f"{self.server_name}状态未知, 请回报管理员",
             1: f"{self.server_name}正在停止, 请等待{self.server_name}停止后重新启动",
             2: f"{self.server_name}正在启动, 请稍等",
             3: f"{self.server_name}正在运行"},
            {0: f"正在启动{self.server_name}..."})
    

    def stop(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "stop",
            {-1: f"{self.server_name}状态未知, 请回报管理员",
             0: f"{self.server_name}已停止",
             1: f"{self.server_name}正在停止, 请稍等",
             2: f"{self.server_name}正在启动, 请等待{self.server_name}启动后重新停止",},
            {3: f"正在关闭{self.server_name}..."})
    

    def kill(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "stop",
            {-1: f"{self.server_name}状态未知, 请回报管理员",
             0: f"{self.server_name}已停止"},
            {1: f"强制终止{self.server_name}...",
             2: f"强制终止{self.server_name}...",
             3: f"强制终止{self.server_name}..."})


    @new_thread(f"{TITLE}-sync")
    @catch_api_error
    def sync(self, source: CommandSource, context: CommandContext):
        if not source.has_permission_higher_than(self.permission["status"]):
            source.reply(f"{REPLY_TITLE} §c权限不足")
            return
        status_code = self.mcsm_api.status()
        if status_code != 0:
            source.reply({
                -1: f"{REPLY_TITLE} §7({self.server_name})§c失败 / {self.server_name}状态未知, 请回报管理员",
                1: f"{REPLY_TITLE} §7({self.server_name})§c失败 / {self.server_name}正在停止, 请等待{self.server_name}停止后进行同步",
                2: f"{REPLY_TITLE} §7({self.server_name})§c失败 / {self.server_name}正在启动, 请等待{self.server_name}启动后重新停止并进行同步",
                3: f"{REPLY_TITLE} §7({self.server_name})§c失败 / {self.server_name}正在运行, 请先停止{self.server_name}再进行同步"}[status_code]
            )
            return
        if self.sync_flag:
            source.reply(f"{REPLY_TITLE} §7({self.server_name})§c已有正在进行中的同步任务")
        self.sync_flag = True
        try:
            self.broadcast(f"{REPLY_TITLE} §7({self.server_name})§a正在进行同步...")
            t = time.time()

            # save the world
            sync_server_config = self.config["server"]
            turn_off_auto_save = sync_server_config["turn_off_auto_save"]
            if turn_off_auto_save:
                self.server.execute(sync_server_config["commands"]["auto_save_off"])
            self.save_world_wait.clear()
            self.server.execute(sync_server_config["commands"]["save_all_worlds"])
            self.save_world_wait.wait(timeout=sync_server_config["save_world_max_wait_sec"]) # wait for finishing saving world
            if turn_off_auto_save:
                self.server.execute(sync_server_config["commands"]["auto_save_on"])

            # sync
            changed_files_count, paths_notfound = self.world_sync.sync()

            # calc time
            m, s = divmod(time.time()-t, 60)
            h, m = divmod(m, 60)
            t = ("%02d:"%h if h else "") + ("%02d:"%m if m else "") + ("%02d"%s if m or h else ("%.02f"%s).zfill(5))
            if paths_notfound:
                self.broadcast(f"{REPLY_TITLE} §7({self.server_name})§c以下文件目录不存在, 已跳过: §f`§7{'§f`§7'.join(paths_notfound)}§f`")
            self.broadcast(f"{REPLY_TITLE} §7({self.server_name})§a同步完成! §f用时 §b{t}s §7/ §f更新了§b{changed_files_count}§f个文件" if changed_files_count != 0 else f"{REPLY_TITLE} §a文件完全相同, 无需同步")
        except Exception as e:
            self.broadcast(f"{REPLY_TITLE} §7({self.server_name})§c同步时发生错误, 请回报管理员: {e}")
        self.sync_flag = False
    

    def on_info(self, server: PluginServerInterface, info: Info):
        if self.config and not self.save_world_wait.is_set() and info.is_from_server and re.match(self.config["server"]["saved_world_regex"], info.content):
            self.save_world_wait.set() # stop waiting in sync function