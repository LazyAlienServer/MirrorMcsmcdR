import functools
import os
import re
import time
from typing import Optional
from mirror_mcsmcdr.utils.command_utils import get_command_output, run_shell_command


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
    def __init__(self, name: str, path: str, pid: Optional[int] = None) -> None:
        self.name = name
        self.path = path
        self.pid = pid
        self.pid_path = os.path.join(path, "mirror.pid")

        self._load_pid()

    def _load_pid(self):
        if self.pid is None and os.path.exists(self.pid_path):
            with open(self.pid_path, 'r') as f:
                self.pid = int(f.read().strip())
            if not self.check_existence():
                self.pid = None

    def create(self, command: str):
        if os.path.exists(self.pid_path):
            with open(self.pid_path, 'r') as f:
                existing_pid = int(f.read().strip())
            if self._screen_exists(existing_pid):
                self.pid = existing_pid
                raise Exception(f"PID {existing_pid} already exists")
            else:
                os.remove(self.pid_path)

        pre_ls = get_command_output("screen -ls").splitlines()
        screen_process = run_shell_command(f"screen -dmS {self.name}", cwd=self.path)
        if screen_process.wait() == 0:
            run_shell_command(f"screen -x -S {self.name} -p 0 -X stuff '{command}&&exit\\n'")
        time.sleep(0.1)
        post_ls = get_command_output("screen -ls").splitlines()
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
        ls_output = get_command_output("screen -ls")
        return f"{pid}.{self.name}" in ls_output

    @_check_existence_decorator()
    def execute_command(self, cmd: str):
        run_shell_command(f"screen -S {self.pid}.{self.name} -p 0 -X stuff '{cmd}\n'")

    @_check_existence_decorator()
    def stop(self, command: str):
        run_shell_command(f"screen -x -S {self.pid}.{self.name} -p 0 -X stuff '{command}\n'")

    @_check_existence_decorator()
    def kill(self, command: str):
        run_shell_command(f"screen -x -S {self.pid}.{self.name} -p 0 -X stuff '{command}\n'")

    @_check_existence_decorator()
    def forcekill(self):
        run_shell_command(f"screen -S {self.pid}.{self.name} -X quit")
