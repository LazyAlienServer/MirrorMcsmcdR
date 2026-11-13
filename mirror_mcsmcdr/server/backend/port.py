import os

from mirror_mcsmcdr.server.backend.shell import get_command_output


class PortListener:
    """Finds the processes that listen on a local TCP port."""

    def __init__(self, port: int, java_only: bool) -> None:
        """
        :param java_only: ignore listeners that are not java processes
        """
        self.port = port
        self.java_only = java_only

    def pids(self) -> set[int]:
        return self._windows_pids() if os.name == "nt" else self._posix_pids()

    def _posix_pids(self) -> set[int]:
        # -F prints one field per line: "p<pid>" opens a process, "c<command>" names it
        text = get_command_output(f"lsof -nP -iTCP:{self.port} -sTCP:LISTEN -Fpc")
        pids = set()
        pid = None
        for line in text.splitlines():
            if line.startswith("p") and line[1:].isdigit():
                pid = int(line[1:])
            elif line.startswith("c") and pid is not None:
                if not self.java_only or line[1:].startswith("java"):
                    pids.add(pid)
        return pids

    def _windows_pids(self) -> set[int]:
        port = str(self.port)
        pids = set()
        for line in get_command_output(f"netstat -ano | findstr :{port}").splitlines():
            fields = line.split()
            if len(fields) < 5 or fields[0].upper() not in ("TCP", "TCPv6"):
                continue
            if fields[-2].upper() != "LISTENING" or not fields[-1].isdigit():
                continue
            if fields[1].rsplit(":", 1)[-1] == port:
                pids.add(int(fields[-1]))
        if not pids or not self.java_only:
            return pids

        java_pids = set()
        for line in get_command_output(["tasklist"]).splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[0].lower() == "java.exe" and fields[1].isdigit():
                java_pids.add(int(fields[1]))
        return pids & java_pids
