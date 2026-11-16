from typing import Optional

import psutil


class PortListener:
    """Finds what listens on a local TCP port."""

    def __init__(self, port: int) -> None:
        self.port = port

    def owners(self) -> set[Optional[int]]:
        """
        The pids of the listening processes; None for one whose pid cannot be read.

        A listener of another user usually is one of those, so the port is free only if this is empty.
        """
        try:
            found = [(connection, connection.pid) for connection in psutil.net_connections(kind="tcp")]
        except psutil.AccessDenied:
            # macOS shows the sockets of the whole system to root only; those of the processes of this user remain
            found = []
            for process in psutil.process_iter():
                try:
                    # named connections() before psutil 6
                    list_connections = getattr(process, "net_connections", None) or process.connections
                    found += [(connection, process.pid) for connection in list_connections(kind="tcp")]
                except psutil.Error:
                    pass
        return {pid for connection, pid in found if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == self.port}
