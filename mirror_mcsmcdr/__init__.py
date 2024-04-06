from mcdreforged.api.all import PluginCommandSource, SimpleCommandBuilder, Text
from mirror_mcsmcdr.mirror_manager import MultiMirrorManager
from mirror_mcsmcdr.constants import TITLE

def on_load(server: PluginCommandSource, prev_module):
    manager = MultiMirrorManager(server)