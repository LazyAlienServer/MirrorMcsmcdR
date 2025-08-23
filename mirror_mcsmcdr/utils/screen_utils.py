import functools
import os
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # noinspection PyUnresolvedReferences
    from mirror_mcsmcdr.utils.proxy.system_proxy import AbstractSystemProxy
    # noinspection PyUnresolvedReferences
    from mirror_mcsmcdr.utils.proxy.system_proxy import LinuxProxy


class ScreenNotExistError(RuntimeError):
    pass


def _check_existence_decorator():
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if self.pid is None:
                if not self.check_existence():
                    raise ScreenNotExistError("Screen does not exist")
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class Screen:
    def __init__(self, system_proxy: 'LinuxProxy', name: str = None, pid: int = None) -> None:
        self.name = name or system_proxy.terminal_name
        self.pid = pid
        self.system_proxy: 'LinuxProxy' = system_proxy
        self.pid_path = os.path.join(self.system_proxy.path, "mirror.pid")

        self._load_pid()

    def _load_pid(self):
        if self.pid is None and os.path.exists(self.pid_path):
            with open(self.pid_path, 'r') as f:
                self.pid = int(f.read().strip())
            if not self.check_existence():
                self.pid = None

    def create(self):
        if os.path.exists(self.pid_path):
            with open(self.pid_path, 'r') as f:
                existing_pid = int(f.read().strip())
            if self._screen_exists(existing_pid):
                self.pid = existing_pid
                raise Exception(f"PID {existing_pid} already exists")
            else:
                os.remove(self.pid_path)

        # 通过对比前后screen -ls的变化来获取screen的pid
        pre_ls = os.popen("screen -ls").readlines()
        self.system_proxy.create_screen()
        time.sleep(0.1)
        post_ls = os.popen("screen -ls").readlines()

        diff_lines = set(post_ls) - set(pre_ls)
        if not diff_lines:
            raise RuntimeError("Failed to detect new screen session")

        for line in diff_lines:
            match = re.match(rf'(\d+)\.{self.name}\s', line.strip())
            if match:
                new_pid = int(match.group(1))
                self.pid = new_pid
                with open(self.pid_path, 'w') as f:
                    f.write(str(new_pid))
                return

        raise RuntimeError("Failed to extract pid from screen -ls")

    def check_existence(self) -> bool:
        if not os.path.exists(self.pid_path):
            return False
        if self.pid is None:
            with open(self.pid_path, 'r') as f:
                self.pid = int(f.read().strip())

        if not self._screen_exists(self.pid):
            os.remove(self.pid_path)
            self.pid = None
            return False

        return True

    def _screen_exists(self, pid: int) -> bool:
        ls_output = os.popen("screen -ls").read()
        return f"{pid}.{self.name}" in ls_output

    @_check_existence_decorator()
    def execute_command(self, cmd: str):
        command = f'screen -S {self.pid}.{self.name} -p 0 -X stuff "{cmd}\n"'
        os.popen(command)

    @_check_existence_decorator()
    def stop(self):
        os.popen(f'screen -x -S {self.pid}.{self.name} -p 0 -X stuff "\nstop\n"')
        if os.path.exists(self.pid_path):
            os.remove(self.pid_path)
        self.pid = None

    @_check_existence_decorator()
    def kill(self):
        os.popen(f'screen -S {self.pid}.{self.name} -X quit')
        if os.path.exists(self.pid_path):
            os.remove(self.pid_path)
        self.pid = None
