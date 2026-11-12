from typing import Any

from mcdreforged.api.all import RTextBase, RTextList, ServerInterface, RAction
from mirror_mcsmcdr.constants import PLUGIN_ID, REPLY_TITLE, TITLE


def rtr(key: str, title: bool = True, **kwargs: Any) -> RTextBase:
    text = ServerInterface.si().rtr(f"{PLUGIN_ID}.{key}", **kwargs)
    return RTextList(REPLY_TITLE + " ", text) if title else text


def help_msg(server_name, prefix):
    server = ServerInterface.si()
    msg = RTextList(server.rtr(PLUGIN_ID+".command.help.info", TITLE=TITLE, VERSION=server.get_plugin_metadata(PLUGIN_ID).version))
    for command in ["help", "reload", "status", "start", "stop", "kill", "sync", "history", "log", "execute"]:
        msg.append("\n", server.rtr(PLUGIN_ID+".command.help."+command, prefix=prefix, server_name=server_name).set_click_event(RAction.run_command, f"{prefix} {command}"))
    return msg
