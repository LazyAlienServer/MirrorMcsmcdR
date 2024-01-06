from mcdreforged.api.all import PluginServerInterface, CommandSource, CommandContext, Info, new_thread
from mirror_mcsmcdr.constants import DEFAULT_CONFIG, REPLY_TITLE, TITLE, VERSION
from mirror_mcsmcdr.mcsm_api import MCSManagerApi, MCSManagerApiError
from mirror_mcsmcdr.file_operation import WorldSync
from threading import Event
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


class MirrorManager:


    def __init__(self, server: PluginServerInterface) -> None:
        global SERVER_NAME
        self.server = server
        self.config = server.load_config_simple(default_config=DEFAULT_CONFIG)
        if None in self.config["MCSManager"].values():
            server.logger.warn("请设置配置文件")
            return
        self.mcsm_api = MCSManagerApi(**self.config["MCSManager"])
        self.world_sync = WorldSync(**self.config["sync"])
        self.permission = self.config["command"]["permission"]
        SERVER_NAME = self.config["display"]["server_name"]
        self.sync_flag = False
        self.save_world_wait = Event()

        command_prefix = self.config["command"]["prefix"]
        self.help_msg = [
            {"text":""},
            {"text":f"§7----- §e{TITLE} §b{VERSION} §7-----§f\n"},
            {"text":f"§7{command_prefix} help §f","clickEvent":{"action":"run_command","value":f"{command_prefix} help"}},
            {"text":"显示此帮助信息\n"},
            {"text":f"§7{command_prefix} status §f","clickEvent":{"action":"run_command","value":f"{command_prefix} status"}},
            {"text":f"查看{SERVER_NAME}状态\n"},
            {"text":f"§7{command_prefix} start §f","clickEvent":{"action":"run_command","value":f"{command_prefix} start"}},
            {"text":f"启动{SERVER_NAME}\n"},
            {"text":f"§7{command_prefix} stop §f","clickEvent":{"action":"run_command","value":f"{command_prefix} stop"}},
            {"text":f"停止{SERVER_NAME}\n"},
            {"text":f"§7{command_prefix} kill §f","clickEvent":{"action":"run_command","value":f"{command_prefix} kill"}},
            {"text":f"强制终止{SERVER_NAME}\n"},
            {"text":f"§7{command_prefix} sync §f","clickEvent":{"action":"run_command","value":f"{command_prefix} sync"}},
            {"text":f"同步{SERVER_NAME}"},
        ]
        self.command_prefix = command_prefix


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
            source.reply(f"{REPLY_TITLE} §c权限不足")
            return
        status_code = self.mcsm_api.status()
        if status_code in failed_prompt.keys():
            source.reply(f"{REPLY_TITLE} §c失败: "+failed_prompt[status_code])
        elif status_code in succeeded_prompt.keys():
            rep = eval(f"self.mcsm_api.{command}()")
            self.server.logger.info(rep)
            self.broadcast(f"{REPLY_TITLE} §a"+succeeded_prompt[status_code])

        
    @catch_api_error
    def status(self, source: CommandSource, context: CommandContext):
        if not source.has_permission_higher_than(self.permission["status"]):
            source.reply(f"{REPLY_TITLE} §c权限不足")
            return
        source.reply(f"{REPLY_TITLE} : {SERVER_NAME}{self.mcsm_api.status_to_text[self.mcsm_api.status()]}")


    def start(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "start",
            {-1: f"{SERVER_NAME}状态未知, 请回报管理员",
             1: f"{SERVER_NAME}正在停止, 请等待{SERVER_NAME}停止后重新启动",
             2: f"{SERVER_NAME}正在启动, 请稍等",
             3: f"{SERVER_NAME}正在运行"},
            {0: f"正在启动{SERVER_NAME}..."})
    

    def stop(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "stop",
            {-1: f"{SERVER_NAME}状态未知, 请回报管理员",
             0: f"{SERVER_NAME}已停止",
             1: f"{SERVER_NAME}正在停止, 请稍等",
             2: f"{SERVER_NAME}正在启动, 请等待{SERVER_NAME}启动后重新停止",},
            {3: f"正在关闭{SERVER_NAME}..."})
    

    def kill(self, source: CommandSource, context: CommandContext):
        self._execute(
            source,
            "stop",
            {-1: f"{SERVER_NAME}状态未知, 请回报管理员",
             0: f"{SERVER_NAME}已停止"},
            {1: f"强制终止{SERVER_NAME}...",
             2: f"强制终止{SERVER_NAME}...",
             3: f"强制终止{SERVER_NAME}..."})


    @new_thread(f"{TITLE}-sync")
    @catch_api_error
    def sync(self, source: CommandSource, context: CommandContext):
        if not source.has_permission_higher_than(self.permission["status"]):
            source.reply(f"{REPLY_TITLE} §c权限不足")
            return
        status_code = self.mcsm_api.status()
        if status_code != 0:
            source.reply({
                -1: f"{REPLY_TITLE} §c失败 / {SERVER_NAME}状态未知, 请回报管理员",
                1: f"{REPLY_TITLE} §c失败 / {SERVER_NAME}正在停止, 请等待{SERVER_NAME}停止后进行同步",
                2: f"{REPLY_TITLE} §c失败 / {SERVER_NAME}正在启动, 请等待{SERVER_NAME}启动后重新停止并进行同步",
                3: f"{REPLY_TITLE} §c失败 / {SERVER_NAME}正在运行, 请先停止{SERVER_NAME}再进行同步"}[status_code]
            )
            return
        if self.sync_flag:
            source.reply(f"{REPLY_TITLE} §c已有正在进行中的同步任务")
        self.sync_flag = True
        try:
            self.broadcast(f"{REPLY_TITLE} §a正在进行同步...")
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
            changed_files_count = self.world_sync.sync()

            # calc time
            m, s = divmod(time.time()-t, 60)
            h, m = divmod(m, 60)
            t = ("%02d:"%h if h else "") + ("%02d:"%m if m else "") + ("%02d"%s if m or h else ("%.02f"%s).zfill(5))
            self.broadcast(f"{REPLY_TITLE} §a同步完成! §f用时 §b{t}s §7/ §f更新了§b{changed_files_count}§f个文件")
        except Exception as e:
            self.broadcast(f"{REPLY_TITLE} §c同步时发生错误, 请回报管理员: {e}")
        self.sync_flag = False
    

    def on_info(self, server: PluginServerInterface, info: Info):
        if not self.save_world_wait.is_set() and info.is_from_server and re.match(self.config["server"]["saved_world_regex"], info.content):
            self.save_world_wait.set() # stop waiting in sync function
    
