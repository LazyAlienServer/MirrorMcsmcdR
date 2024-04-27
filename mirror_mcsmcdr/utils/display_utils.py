from mcdreforged.api.all import RTextTranslation, ServerInterface
from mirror_mcsmcdr.utils.constants import PLUGIN_ID

server = ServerInterface.get_instance()

def display(key, *args, **kwargs):
    return ServerInterface.rtr(PLUGIN_ID+"."+key, *args, **kwargs)