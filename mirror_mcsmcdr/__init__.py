from mcdreforged.api.all import PluginCommandSource
from mirror_mcsmcdr.mirror_manager import MultiMirrorManager
from mirror_mcsmcdr.utils.constants import TITLE

def on_load(server: PluginCommandSource, prev_module):
    manager = MultiMirrorManager(server)