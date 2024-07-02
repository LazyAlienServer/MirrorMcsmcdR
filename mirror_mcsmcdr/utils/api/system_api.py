import os, re
from abc import ABC, abstractmethod

from mirror_mcsmcdr.constants import PLUGIN_ID

class SystemAPI:
    
    def __init__(self, new_terminal: str, launch_path: str, launch_command: str, port: int, regex_strict: bool, system: str) -> None:
        self.system_api: AbstractSystemAPI
        if system == "Linux":
            self.system_api = LinuxAPI(new_terminal+"_"+PLUGIN_ID, launch_path, launch_command, port, regex_strict)
        elif system == "Windows":
            self.system_api = WindowsAPI(new_terminal+"_"+PLUGIN_ID, launch_path, launch_command, port, regex_strict)

    def start(self):
        return self.system_api.start()
    
    def status(self):
        return self.system_api.status()
    
    def stop(self):
        return self.system_api.stop()

class AbstractSystemAPI(ABC):

    def __init__(self, new_terminal: str, path: str, command: str, port: int, regex_strict: bool) -> None:
        self.new_terminal, self.path, self.command = new_terminal, path, command
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

class LinuxAPI(AbstractSystemAPI):

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        new_terminal = self.new_terminal
        command = f'cd "{self.path}"&&screen -dmS {new_terminal}&&screen -x -S {new_terminal} -p 0 -X stuff "{self.command}&&exit\n"'
        os.popen(command)
        return "success"
    
    def status(self) -> bool:
        port = self.port
        text = os.popen(f"lsof -i:{port}").read()
        if not self.regex_strict or not text:
            return "running" if text else "stopped"
        return "running" if re.search(r"\njava.+:%s"%port, text) else "stopped"
    
    def stop(self):
        command = f'screen -x -S {self.new_terminal} -p 0 -X stuff "\nstop\n"'
        os.popen(command)
        return "success"

class WindowsAPI(AbstractSystemAPI):

    def start(self):
        if not os.path.exists(self.path):
            return "path_not_found"
        new_terminal = self.new_terminal
        command = f'''cd "{self.path}"&&start cmd.exe cmd /C python -c "import os;os.system('title {new_terminal}');os.system('{self.command}')"'''
        os.popen(command)
        return "success"
    
    def status(self):
        port = self.port
        text = os.popen(f"netstat -ano | findstr {port}").read()
        if not self.regex_strict or not text:
            return "running" if text else "stopped"
        for pid in set(re.findall(":30001.*?([0-9]+)\n"), text):
            if re.match("java.exe", os.popen(f"tasklist | findstr {pid}")):
                return "running"
        return "stopped"
    
    def stop(self):
        return "unavailable_windows"