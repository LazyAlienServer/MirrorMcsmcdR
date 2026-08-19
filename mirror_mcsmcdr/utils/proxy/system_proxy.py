import os, subprocess
import re
import signal
from abc import ABC, abstractmethod
from typing import Union

from mirror_mcsmcdr.utils.screen_utils import Screen
from mirror_mcsmcdr.utils.command_utils import get_command_output, run_shell_command
from mirror_mcsmcdr.utils.status import ServerStatus


class AbstractSystemProxy(ABC):

    def __init__(
        self,
        terminal_name: str,
        path: str,
        command: str,
        port: int,
        regex_strict: bool,
        is_mcdr: bool = True
    ) -> None:
        self.terminal_name, self.path, self.command = terminal_name, path, command
        self.port, self.regex_strict =  port, regex_strict
        self.is_mcdr = is_mcdr
    
    @abstractmethod
    def start(self) -> str:
        ...
    
    @abstractmethod
    def status(self) -> ServerStatus:
        ...
    
    @abstractmethod
    def stop(self) -> str:
        ...

    @abstractmethod
    def kill(self) -> str:
        ...

    @abstractmethod
    def forcekill(self) -> str:
        ...


class SystemProxy(AbstractSystemProxy):

    def __init__(
        self, terminal_name: str,
        launch_path: str,
        launch_command: str,
        port: int,
        regex_strict: bool,
        system: str,
        is_mcdr: bool = True
    ) -> None:
        super().__init__(terminal_name, launch_path, launch_command, port, regex_strict, is_mcdr)
        self.system_api: Union[LinuxProxy, WindowsProxy]
        if system == "Linux":
            self.system_api = LinuxProxy(terminal_name, launch_path, launch_command, port, regex_strict, is_mcdr)
        elif system == "Windows":
            self.system_api = WindowsProxy(terminal_name, launch_path, launch_command, port, regex_strict, is_mcdr)

    def start(self):
        return self.system_api.start()
    
    def status(self) -> ServerStatus:
        return self.system_api.status()
    
    def stop(self):
        return self.system_api.stop()

    def kill(self):
        return self.system_api.kill()

    def forcekill(self):
        return self.system_api.forcekill()


class LinuxProxy(AbstractSystemProxy):

    def __init__(
        self,
        terminal_name: str,
        launch_path: str,
        launch_command: str,
        port: int,
        regex_strict: bool,
        is_mcdr: bool = True
    ) -> None:
        super().__init__(terminal_name, launch_path, launch_command, port, regex_strict, is_mcdr)
        self.screen = Screen(self)

    def create_screen(self):
        terminal_name = self.terminal_name
        screen_process = run_shell_command(f"screen -dmS {terminal_name}", cwd=self.path)
        if screen_process.wait() != 0:
            return
        run_shell_command(f"screen -x -S {terminal_name} -p 0 -X stuff '{self.command}&&exit\\n'")

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        self.screen.create()
        return "success"

    def status(self) -> ServerStatus:
        terminal_open = self.screen.check_existence()
        port = self.port
        text = get_command_output(f"lsof -i:{port}")
        if not text:
            java_running = False
        else:
            java_running = not self.regex_strict or re.search(r"\njava.+:%s" % port, text)

        if terminal_open and java_running:
            return ServerStatus.RUNNING
        elif terminal_open and not java_running:
            return ServerStatus.DETACHED_JAVA
        elif not terminal_open and java_running:
            return ServerStatus.DETACHED_SCREEN
        else:
            return ServerStatus.STOPPED

    def stop(self):
        self.screen.stop(self.is_mcdr)
        return "success"

    def kill(self):
        if not self.is_mcdr:
            return self.forcekill()
        status = self.status()
        if status == ServerStatus.DETACHED_SCREEN:
            return "force_required"
        if status == ServerStatus.DETACHED_JAVA:
            self.screen.forcekill()
            return "success"
        if status == ServerStatus.STOPPED:
            return ServerStatus.STOPPED
        self.screen.kill()
        return "success"

    def forcekill(self):
        text = get_command_output(f"lsof -t -iTCP:{self.port} -sTCP:LISTEN")
        try:
            for pid in {int(pid) for pid in text.split() if pid.isdigit()}:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        finally:
            if self.screen.check_existence():
                self.screen.forcekill()
        return "success"


class WindowsProxy(AbstractSystemProxy):

    def _get_listening_pids(self) -> set[int]:
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
        return pids

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        terminal_name = self.terminal_name
        run_shell_command(f'''start cmd.exe cmd /C "title {terminal_name}&&{self.command}"''', cwd=self.path)
        return "success"
    
    def status(self) -> ServerStatus:
        pids = self._get_listening_pids()
        if not pids:
            return ServerStatus.STOPPED
        if not self.regex_strict:
            return ServerStatus.RUNNING

        tasklist_lines = get_command_output(["tasklist"]).splitlines()
        for line in tasklist_lines:
            fields = line.split()
            if len(fields) >= 2 and fields[0].lower() == "java.exe" and fields[1].isdigit():
                if int(fields[1]) in pids:
                    return ServerStatus.RUNNING
        return ServerStatus.STOPPED
    
    def stop(self):
        pids = self._get_listening_pids()
        if not pids:
            return ServerStatus.STOPPED
        for pid in pids:
            try:
                os.kill(pid, signal.SIGINT)
            except (ProcessLookupError, PermissionError):
                pass
        return "success"
    
    def kill(self):
        pids = self._get_listening_pids()
        if not pids:
            return ServerStatus.STOPPED
        for pid in pids:
            run_shell_command(["taskkill", "/PID", str(pid), "/F"])
        return "success"

    def forcekill(self):
        return ServerStatus.UNAVAILABLE
