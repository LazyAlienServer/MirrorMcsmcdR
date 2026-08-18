import functools
import os, subprocess
import re
import time
from typing import TYPE_CHECKING, Optional
from mirror_mcsmcdr.utils.command_utils import capture_command_output

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
    def __init__(self, system_proxy: 'LinuxProxy', name: Optional[str] = None, pid: Optional[int] = None) -> None:
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

        pre_ls = capture_command_output(["screen", "-ls"]).splitlines()
        self.system_proxy.create_screen()
        time.sleep(0.1)
        post_ls = capture_command_output(["screen", "-ls"]).splitlines()

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
        ls_output = capture_command_output(["screen", "-ls"])
        return f"{pid}.{self.name}" in ls_output

    @_check_existence_decorator()
    def execute_command(self, cmd: str):
        command = ["screen", "-S", f"{self.pid}.{self.name}", "-p", "0", "-X", "stuff", f"{cmd}\n"]
        subprocess.Popen(command)

    @_check_existence_decorator()
    def stop(self, is_mcdr: bool = True):
        command = "!!MCDR server stop_exit" if is_mcdr else "stop"
        subprocess.Popen([
            "screen", "-x", "-S", f"{self.pid}.{self.name}", "-p", "0", "-X", "stuff",
            f"{command}\n",
        ])

    @_check_existence_decorator()
    def kill(self):
        subprocess.Popen(["screen", "-x", "-S", f"{self.pid}.{self.name}", "-p", "0", "-X", "stuff", "!!MCDR server kill\n"])

    @_check_existence_decorator()
    def forcekill(self):
        subprocess.Popen(["screen", "-S", f"{self.pid}.{self.name}", "-X", "quit"])
