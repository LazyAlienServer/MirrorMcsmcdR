from mcdreforged.api.all import PluginCommandSource, SimpleCommandBuilder
from mirror_mcsmcdr.mirror_manager import MirrorManager
from mirror_mcsmcdr.constants import TITLE

def on_load(server: PluginCommandSource, prev_module):
    global manager
    manager = MirrorManager(server)
    command_prefix = manager.command_prefix
    builder = SimpleCommandBuilder()
    builder.command(f"{command_prefix}", manager.help)
    builder.command(f"{command_prefix} help", manager.help)
    builder.command(f"{command_prefix} status", manager.status)
    builder.command(f"{command_prefix} start", manager.start)
    builder.command(f"{command_prefix} stop", manager.stop)
    builder.command(f"{command_prefix} kill", manager.kill)
    builder.command(f"{command_prefix} sync", manager.sync)
    builder.register(server)

    server.register_help_message(f"{command_prefix}", f"{TITLE}使用帮助")

def on_info(server, info):
    manager.on_info(server, info)