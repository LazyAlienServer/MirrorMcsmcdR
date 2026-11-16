from typing import Optional

from mirror_mcsmcdr.server.action import Action
from mirror_mcsmcdr.server.status import Anomaly, Evidence, ServerState, StatusSnapshot


class StatusResolver:
    """Turns what the backends observed, plus what the plugin itself last asked for, into a status."""

    @staticmethod
    def resolve(evidence: Evidence, intent: Optional[Action]) -> StatusSnapshot:
        """
        :param intent: :attr:`Action.START` or :attr:`Action.STOP` while such an action is still settling.
            It only decides between states the evidence cannot tell apart
        """
        if evidence.panel_state is not None:
            return StatusSnapshot(evidence.panel_state, frozenset(), evidence)

        stopping = intent is Action.STOP
        pending = {Action.START: ServerState.STARTING, Action.STOP: ServerState.STOPPING}.get(intent) if intent else None
        anomaly: Optional[Anomaly] = None

        if evidence.port_listening is None:
            state = ServerState.UNKNOWN
        elif evidence.foreign_listeners:
            # the port is held by something the plugin did not launch
            state = ServerState.UNKNOWN
        elif not evidence.members_alive:
            state = ServerState.STOPPED
        elif not (evidence.mcdr_alive or evidence.server_alive or evidence.others_alive):
            # only the terminal is there: it has not got to the command yet, or it is closing after it
            if pending is not None:
                state = pending
            elif evidence.endpoint_alive:
                # left behind by a command that failed
                state, anomaly = ServerState.STOPPED, Anomaly.ORPHAN_SCREEN
            else:
                state = ServerState.STOPPING
        elif not evidence.endpoint_alive:
            state, anomaly = ServerState.RUNNING, Anomaly.ORPHAN_PROCESS
        elif evidence.server_alive or (evidence.others_alive and evidence.mcdr_alive is False):
            if evidence.port_listening:
                state = ServerState.STOPPING if stopping else ServerState.RUNNING
            else:
                # the port opens a while after the server process is there, and stays closed if it is not the right one
                state = pending or ServerState.STARTING
            if evidence.mcdr_alive is False:
                anomaly = Anomaly.MCDR_MISSING
        else:
            # MCDR without a server: it is loading or unloading, or it was told to stop the server only
            state = pending or ServerState.UNKNOWN

        return StatusSnapshot(state, frozenset() if anomaly is None else frozenset({anomaly}), evidence)
