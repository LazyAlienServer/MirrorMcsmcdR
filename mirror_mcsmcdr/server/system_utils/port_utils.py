from typing import Optional

import psutil


class PortListener:
    """Finds what listens on a local TCP port."""

    def __init__(self, port: int, java_only: bool) -> None:
        """
        :param java_only: ignore listeners that are not known to be java processes
        """
        self.port = port
        self.java_only = java_only

    def is_listening(self) -> bool:
        """Whether the port is taken, which includes a listener whose process cannot be told."""
        owners = self._owners()
        if self.java_only:
            return any(pid is not None and self._is_java(pid) for pid in owners)
        return bool(owners)

    def pids(self) -> set[int]:
        """
        The listening processes that can be told.

        A listener of another user usually cannot, so an empty set does not mean that the port is free;
        that is what :meth:`is_listening` is for.
        """
        return {pid for pid in self._owners() if pid is not None and (not self.java_only or self._is_java(pid))}

    def processes(self) -> list[psutil.Process]:
        """Same as :meth:`pids`, as handles that stay bound to these very processes when a pid gets reused."""
        processes = []
        for pid in self.pids():
            try:
                processes.append(psutil.Process(pid))
            except psutil.NoSuchProcess:
                pass
        return processes

    def _owners(self) -> set[Optional[int]]:
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

    @staticmethod
    def _is_java(pid: int) -> bool:
        try:
            return psutil.Process(pid).name().lower().startswith("java")
        except psutil.Error:
            return False
