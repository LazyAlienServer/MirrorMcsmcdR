from mcdreforged.api.all import RTextList, ServerInterface, RAction
from mirror_mcsmcdr.constants import PLUGIN_ID, REPLY_TITLE, TITLE, VERSION


def rtr(key, title=True, *args, **kwargs):
    return RTextList(REPLY_TITLE+" ", ServerInterface.si().rtr(PLUGIN_ID+"."+key, *args, **kwargs)) if title else ServerInterface.si().rtr(PLUGIN_ID+"."+key, *args, **kwargs)


def help_msg(server_name, prefix):
    server = ServerInterface.si()
    msg = RTextList(server.rtr(PLUGIN_ID+".command.help.info", TITLE=TITLE, VERSION=VERSION))
    for command in ["help", "reload", "status", "start", "stop", "kill", "sync"]:
        msg.append("\n",server.rtr(PLUGIN_ID+".command.help."+command, prefix=prefix, server_name=server_name).set_click_event(RAction.run_command, f"{prefix} {command}"))
    return msg