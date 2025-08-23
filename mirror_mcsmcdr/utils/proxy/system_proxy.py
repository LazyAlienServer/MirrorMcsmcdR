import os
import re
from abc import ABC, abstractmethod
from typing import Union

from mirror_mcsmcdr.utils.screen_utils import Screen


class AbstractSystemProxy(ABC):

    def __init__(self, terminal_name: str, path: str, command: str, port: int, regex_strict: bool) -> None:
        self.terminal_name, self.path, self.command = terminal_name, path, command
        self.port, self.regex_strict =  port, regex_strict
    
    @abstractmethod
    def start(self) -> str:
        ...
    
    @abstractmethod
    def status(selfl) -> str:
        ...
    
    @abstractmethod
    def stop(self) -> str:
        ...

    @abstractmethod
    def kill(self) -> str:
        ...


class SystemProxy(AbstractSystemProxy):

    def __init__(self, terminal_name: str, launch_path: str, launch_command: str, port: int, regex_strict: bool,
                 system: str) -> None:
        super().__init__(terminal_name, launch_path, launch_command, port, regex_strict)
        self.system_api: Union[LinuxProxy, WindowsProxy]
        if system == "Linux":
            self.system_api = LinuxProxy(terminal_name, launch_path, launch_command, port, regex_strict)
        elif system == "Windows":
            self.system_api = WindowsProxy(terminal_name, launch_path, launch_command, port, regex_strict)

    def start(self):
        return self.system_api.start()
    
    def status(self):
        return self.system_api.status()
    
    def stop(self):
        return self.system_api.stop()

    def kill(self):
        return self.system_api.kill()


class LinuxProxy(AbstractSystemProxy):

    def __init__(self, terminal_name: str, launch_path: str, launch_command: str, port: int,
                 regex_strict: bool) -> None:
        super().__init__(terminal_name, launch_path, launch_command, port, regex_strict)
        self.screen: Union[Screen] = Screen(self)

    def create_screen(self):
        terminal_name = self.terminal_name
        command = f'cd "{self.path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{self.command}&&exit\n"'
        os.popen(command)

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        self.screen.create()
        return "success"

    def status(self):
        terminal_open = self.screen.check_existence()
        port = self.port
        text = os.popen(f"lsof -i:{port}").read()
        if not text:
            java_running = False
        else:
            java_running = not self.regex_strict or re.search(r"\njava.+:%s" % port, text)

        if terminal_open and java_running:
            return "running"
        elif terminal_open and not java_running:
            return "detached_java"
        elif not terminal_open and java_running:
            return "detached_screen"
        else:
            return "stopped"

    def stop(self):
        # command = f'screen -x -S {self.terminal_name} -p 0 -X stuff "\nstop\n"'
        # os.popen(command)
        self.screen.stop()
        return "success"

    def kill(self):
        self.screen.kill()
        return "success"


class WindowsProxy(AbstractSystemProxy):

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        terminal_name = self.terminal_name
        command = f'''cd "{self.path}"&&start cmd.exe cmd /C "title {terminal_name}&&{self.command}"'''
        os.popen(command)
        return "success"
    
    def status(self):
        port = self.port
        text = os.popen(f"netstat -ano | findstr {port}").read()
        if not self.regex_strict or not text:
            return "running" if text else "stopped"
        for pid in set(re.findall(f":{port}.*?([0-9]+)\n", text)):
            if re.match("java.exe", os.popen(f"tasklist | findstr {pid}").read()):
                return "running"
        return "stopped"
    
    def stop(self):
        return "unavailable_windows"
    
    def kill(self):
        ...