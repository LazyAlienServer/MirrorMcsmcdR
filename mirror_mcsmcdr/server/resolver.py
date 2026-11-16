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

        starting = intent is Action.START
        stopping = intent is Action.STOP
        # whatever the server runs in; None on Windows, where only the port can be observed
        host = evidence.process_alive if evidence.process_alive is not None else evidence.screen_exists
        listening = evidence.port_listening
        running = ServerState.STOPPING if stopping else ServerState.RUNNING
        anomaly: Optional[Anomaly] = None

        if host is None and listening is None:
            state = ServerState.UNKNOWN
        elif listening if listening is not None else host:
            if host is False:
                # a dead child process means the port belongs to something else
                if evidence.screen_exists is False:
                    state, anomaly = ServerState.RUNNING, Anomaly.ORPHAN_PROCESS
                else:
                    state = ServerState.STOPPED
            else:
                state = running
        elif host:
            if starting:
                state = ServerState.STARTING
            elif stopping:
                state = ServerState.STOPPING
            elif evidence.screen_exists:
                state, anomaly = ServerState.STOPPED, Anomaly.ORPHAN_SCREEN
            else:
                # a child process that never opened its port within the start timeout
                state = ServerState.RUNNING
        else:
            state = ServerState.STARTING if starting and host is None else ServerState.STOPPED

        return StatusSnapshot(state, frozenset() if anomaly is None else frozenset({anomaly}), evidence)
