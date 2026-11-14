from typing import Any

from mcdreforged.api.all import RTextBase, RTextList, ServerInterface, RAction
from mirror_mcsmcdr.constants import PLUGIN_ID, REPLY_TITLE, TITLE
from mirror_mcsmcdr.server import ActionResult, StatusSnapshot


def rtr(key: str, title: bool = True, **kwargs: Any) -> RTextBase:
    text = ServerInterface.si().rtr(f"{PLUGIN_ID}.{key}", **kwargs)
    return RTextList(REPLY_TITLE + " ", text) if title else text


def help_msg(server_name, prefix):
    server = ServerInterface.si()
    msg = RTextList(server.rtr(PLUGIN_ID+".command.help.info", TITLE=TITLE, VERSION=server.get_plugin_metadata(PLUGIN_ID).version))
    for command in ["help", "reload", "status", "start", "stop", "kill", "sync", "history", "log", "execute"]:
        msg.append("\n", server.rtr(PLUGIN_ID+".command.help."+command, prefix=prefix, server_name=server_name).set_click_event(RAction.run_command, f"{prefix} {command}"))
    return msg


# Rejections that come with advice of their own, as command.<command>.fail.<label>.
# Every other rejection is explained by describing the status.
_ADVISED_REJECTIONS = {
    "start": {"unknown", "stopping", "starting", "orphan_screen", "orphan_process"},
    "stop": {"unknown", "stopping", "starting", "orphan_screen", "orphan_process"},
    "kill": {"unknown"},
}


def status_key(snapshot: StatusSnapshot) -> str:
    """The translation key describing what matters most about the status."""
    return f"command.{'anomaly' if snapshot.anomalies else 'state'}.{snapshot.label}"


def rejection_key(command: str, result: ActionResult) -> str:
    """The translation key explaining why ``command`` was rejected."""
    outcome = result.outcome
    if outcome is ActionResult.Outcome.UNSUPPORTED:
        return f"command.{command}.fail.unsupported"
    if outcome in (ActionResult.Outcome.WRONG_STATE, ActionResult.Outcome.ANOMALY):
        label = result.snapshot.label
        if label in _ADVISED_REJECTIONS[command]:
            return f"command.{command}.fail.{label}"
        return status_key(result.snapshot)
    return f"command.outcome.{outcome.value}"
