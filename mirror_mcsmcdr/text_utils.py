from typing import Any, Protocol

from mcdreforged.api.all import RTextBase, RTextList, ServerInterface, RAction
from mirror_mcsmcdr.constants import PLUGIN_ID, REPLY_TITLE, TITLE
from mirror_mcsmcdr.server import Action, ActionResult, StatusSnapshot


class Translator(Protocol):
    """The rtr of a mirror manager, which fills in its prefix and server name."""

    def __call__(self, key: str, title: bool = True, **kwargs: Any) -> RTextBase:
        ...


def rtr(key: str, title: bool = True, **kwargs: Any) -> RTextBase:
    text = ServerInterface.si().rtr(f"{PLUGIN_ID}.{key}", **kwargs)
    return RTextList(REPLY_TITLE + " ", text) if title else text


def help_msg(server_name, prefix):
    server = ServerInterface.psi()
    msg = RTextList(server.rtr(PLUGIN_ID+".command.help.info", TITLE=TITLE, VERSION=server.get_self_metadata().version))
    for command in ["help", "reload", "status", "start", "stop", "kill", "recover", "sync", "history", "log", "input"]:
        msg.append("\n", server.rtr(PLUGIN_ID+".command.help."+command, prefix=prefix, server_name=server_name).set_click_event(RAction.run_command, f"{prefix} {command}"))
    return msg


# Refusals whose status alone does not tell what to do instead, as command.<command>.hint.<state>
_HINTS = {
    "start": {"stopping"},
    "stop": {"starting"},
    "sync": {"running", "starting", "stopping"},
}


def status_key(snapshot: StatusSnapshot) -> str:
    """The translation key describing what matters most about the status."""
    return f"command.{'anomaly' if snapshot.anomalies else 'state'}.{snapshot.label}"


def detail_lines(tr: Translator, snapshot: StatusSnapshot) -> list[RTextBase]:
    """Why the status is what it is and what can be done; nothing for a plain running or stopped one."""
    if snapshot.detail is None:
        return []
    detail = tr(f"command.detail.{snapshot.detail.value}", title=False).to_legacy_text()
    return [tr("command.detail.line", title=False, detail=detail)]


def refusal_lines(tr: Translator, command: str, snapshot: StatusSnapshot) -> list[RTextBase]:
    """The reply to ``command`` refused for the status: the status, its detail and what to do instead."""
    lines = [tr("command._execute.fail", prompt=tr(status_key(snapshot), title=False).to_legacy_text())]
    lines += detail_lines(tr, snapshot)
    if not snapshot.anomalies and snapshot.state.value in _HINTS.get(command, ()):
        lines.append(tr(f"command.{command}.hint.{snapshot.state.value}", title=False))
    return lines


def rejection_lines(tr: Translator, command: str, result: ActionResult) -> list[RTextBase]:
    """The reply to ``command`` that was not carried out."""
    outcome = result.outcome
    if outcome in (ActionResult.Outcome.WRONG_STATE, ActionResult.Outcome.ANOMALY):
        return refusal_lines(tr, command, result.snapshot)
    if outcome is ActionResult.Outcome.UNSUPPORTED:
        # with a panel, a kill is supported but a forced one is not, so it is told apart
        key = f"command.{command}.fail.unsupported" + ("_force" if result.action is Action.FORCEKILL else "")
    else:
        key = f"command.outcome.{outcome.value}"
    return [tr("command._execute.fail", prompt=tr(key, title=False).to_legacy_text())]
