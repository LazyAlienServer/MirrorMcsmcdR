import os, platform, re, importlib
from abc import ABC, abstractmethod

from mirror_mcsmcdr.utils.constants import PLUGIN_ID
from mirror_mcsmcdr.utils.api.rcon_api import RConAPI

class SystemAPI:
    
    def __init__(self, new_terminal: str, rcon: RConAPI) -> None:
        system = platform.system()
        self.system_api: AbstractSystemAPI
        if system == "Linux":
            self.system_api = LinuxAPI(new_terminal+PLUGIN_ID)
        elif system == "windows":
            self.system_api = WindowsAPI(new_terminal+PLUGIN_ID)

    def start(self, path, command):
        return self.system_api.start(path, command)
    
    def status(self):
        return self.system_api.status()

class AbstractSystemAPI(ABC):

    def __init__(self, new_terminal: str) -> None:
        self.new_terminal = new_terminal
    
    @abstractmethod
    def start(self, path, command):
        ...
    
    @abstractmethod
    def status(self):
        ...

class LinuxAPI(AbstractSystemAPI):

    def start(self, path, command):
        new_terminal = self.new_terminal
        command = f'screen -dmS {new_terminal} && screen -x -S {new_terminal} -p 0 -X stuff "{command} && exit\n"'
        os.popen(f'cd "{path}" && {command}')
    
    def status(self):
        if re.search(r"\t[0-9]+.%s\t"%self.new_terminal, os.popen("screen -ls").read()):
            return True
        return False

class WindowsAPI(AbstractSystemAPI):

    def __init__(self, new_terminal: str) -> None:
        self.pgw = importlib.import_module("pygetwindow")
        super().__init__(new_terminal)

    def start(self, path, command):
        new_terminal = self.new_terminal
        command = f'''cd "{path}"&&start cmd.exe cmd /k python -c "import os;os.system('title {new_terminal}');os.system('{command}')"'''
        os.popen(f'cd "{path}" && {command}')
    
    def status(self):
        new_terminal = self.new_terminal
        return sum([new_terminal in i.title for i in self.pgw.getWindowsWithTitle(new_terminal)]) > 0