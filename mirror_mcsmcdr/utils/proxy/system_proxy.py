import os, re
from abc import ABC, abstractmethod

from mirror_mcsmcdr.constants import PLUGIN_ID

class SystemProxy:
    
    def __init__(self, terminal_name: str, launch_path: str, launch_command: str, port: int, regex_strict: bool, system: str) -> None:
        self.system_api: AbstractSystemProxy
        if system == "Linux":
            self.system_api = LinuxProxy(terminal_name+"_"+PLUGIN_ID, launch_path, launch_command, port, regex_strict)
        elif system == "Windows":
            self.system_api = WindowsProxy(terminal_name+"_"+PLUGIN_ID, launch_path, launch_command, port, regex_strict)

    def start(self):
        return self.system_api.start()
    
    def status(self):
        return self.system_api.status()
    
    def stop(self):
        return self.system_api.stop()

class AbstractSystemProxy(ABC):

    def __init__(self, terminal_name: str, path: str, command: str, port: int, regex_strict: bool) -> None:
        self.terminal_name, self.path, self.command = terminal_name, path, command
        self.port, self.regex_strict =  port, regex_strict
    
    @abstractmethod
    def start(self):
        ...
    
    @abstractmethod
    def status(selfl) -> str:
        ...
    
    @abstractmethod
    def stop(self):
        ...

class LinuxProxy(AbstractSystemProxy):

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        terminal_name = self.terminal_name
        command = f'cd "{self.path}"&&screen -dmS {terminal_name}&&screen -x -S {terminal_name} -p 0 -X stuff "{self.command}&&exit\n"'
        os.popen(command)
        return "success"
    
    def status(self) -> bool:
        port = self.port
        text = os.popen(f"lsof -i:{port}").read()
        if not self.regex_strict or not text:
            return "running" if text else "stopped"
        return "running" if re.search(r"\njava.+:%s"%port, text) else "stopped"
    
    def stop(self):
        command = f'screen -x -S {self.terminal_name} -p 0 -X stuff "\nstop\n"'
        os.popen(command)
        return "success"

class WindowsProxy(AbstractSystemProxy):

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        terminal_name = self.terminal_name
        command = f'''cd "{self.path}"&&start cmd.exe cmd /C python -c "import os;os.system('title {terminal_name}');os.system('{self.command}')"'''
        os.popen(command)
        return "success"
    
    def status(self):
        port = self.port
        text = os.popen(f"netstat -ano | findstr {port}").read()
        if not self.regex_strict or not text:
            return "running" if text else "stopped"
        for pid in set(re.findall(f":{port}.*?([0-9]+)\n", text)):
            if re.match("java.exe", os.popen(f"tasklist | findstr {pid}")):
                return "running"
        return "stopped"
    
    def stop(self):
        return "unavailable_windows"