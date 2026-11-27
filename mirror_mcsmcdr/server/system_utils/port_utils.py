from typing import Iterable, Optional

import psutil

from mirror_mcsmcdr.server.system_utils import process_utils


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
            for process in process_utils.all_processes():
                try:
                    # named connections() before psutil 6
                    list_connections = getattr(process, "net_connections", None) or process.connections
                    found += [(connection, process.pid) for connection in list_connections(kind="tcp")]
                except psutil.Error:
                    pass
        return {pid for connection, pid in found if connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == self.port}

    def listened_by(self, processes: Iterable[psutil.Process]) -> bool:
        """
        Whether one of ``processes`` listens on the port, from their own sockets only.

        Much cheaper than :meth:`owners` on Linux, which maps every socket of the machine to its process;
        a process whose sockets cannot be read counts as not listening.
        """
        for process in processes:
            try:
                # named connections() before psutil 6
                list_connections = getattr(process, "net_connections", None) or process.connections
                if any(
                    connection.status == psutil.CONN_LISTEN and connection.laddr and connection.laddr.port == self.port
                    for connection in list_connections(kind="tcp")
                ):
                    return True
            except psutil.Error:
                pass
        return False
