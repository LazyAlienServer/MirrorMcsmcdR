from typing import Optional

from mirror_mcsmcdr.server.action import Action
from mirror_mcsmcdr.server.status import Anomaly, Detail, Evidence, ServerState, StatusSnapshot


class StatusResolver:
    """Turns what the backends observed, plus what the plugin itself last asked for, into a status."""

    @staticmethod
    def resolve(evidence: Evidence, intent: Optional[Action]) -> StatusSnapshot:
        """
        :param intent: :attr:`Action.START` or :attr:`Action.STOP` while such an action is still settling.
            It only decides between states the evidence cannot tell apart
        """
        if evidence.panel_state is not None:
            plain = evidence.panel_state in (ServerState.RUNNING, ServerState.STOPPED)
            return StatusSnapshot(evidence.panel_state, frozenset(), evidence, None if plain else Detail.PANEL)

        stopping = intent is Action.STOP
        pending = {Action.START: ServerState.STARTING, Action.STOP: ServerState.STOPPING}.get(intent) if intent else None
        pending_detail = {Action.START: Detail.START_PENDING, Action.STOP: Detail.STOP_PENDING}.get(intent) if intent else None
        anomaly: Optional[Anomaly] = None
        detail: Optional[Detail] = None

        if evidence.port_listening is None:
            state = ServerState.UNKNOWN
        elif evidence.untracked and not evidence.members_alive:
            # the mirror runs, but not under the plugin, whether the port is open yet or not
            state, detail = ServerState.UNKNOWN, Detail.UNTRACKED
        elif evidence.foreign_listeners:
            # the port is held by something the plugin did not launch
            state, detail = ServerState.UNKNOWN, Detail.FOREIGN_LISTENER
        elif not evidence.members_alive:
            state = ServerState.STOPPED
        elif not (evidence.mcdr_alive or evidence.server_alive or evidence.others_alive):
            # only the terminal is there: it has not got to the command yet, or it is closing after it
            if pending is not None:
                state, detail = pending, pending_detail
            elif evidence.endpoint_alive:
                # left behind by a command that failed
                state, anomaly = ServerState.STOPPED, Anomaly.ORPHAN_SCREEN
            else:
                state, detail = ServerState.STOPPING, Detail.CONSOLE_CLOSING
        elif not evidence.endpoint_alive:
            state, anomaly = ServerState.RUNNING, Anomaly.ORPHAN_PROCESS
        elif evidence.server_alive or (evidence.others_alive and evidence.mcdr_alive is False):
            if not evidence.port_listening:
                # the port opens a while after the server process is there, and stays closed if it is not the right one
                state, detail = pending or ServerState.STARTING, pending_detail or Detail.PORT_CLOSED
            elif stopping:
                state, detail = ServerState.STOPPING, Detail.STOP_PENDING
            else:
                state = ServerState.RUNNING
            if evidence.mcdr_alive is False:
                anomaly = Anomaly.MCDR_MISSING
        else:
            # MCDR without a server: it is loading or unloading, or it was told to stop the server only
            state, detail = pending or ServerState.MCDR_ONLY, pending_detail or Detail.MCDR_ONLY

        if anomaly is not None:
            # what is odd matters more than how the state came about
            detail = Detail(anomaly.value)
        return StatusSnapshot(state, frozenset() if anomaly is None else frozenset({anomaly}), evidence, detail)
