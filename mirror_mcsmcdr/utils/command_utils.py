import os
import subprocess
from typing import Any, Optional, Sequence, Union


ShellCommand = Union[str, Sequence[str]]


def run_shell_command(
    command: ShellCommand,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> subprocess.Popen:
    return subprocess.Popen(command, shell=True, cwd=cwd, **kwargs)


def get_command_output(command: ShellCommand) -> str:
    encoding = "oem" if os.name == "nt" else "utf-8"
    process = run_shell_command(
        command,
        stdout=subprocess.PIPE,
        text=True,
        encoding=encoding,
    )
    return process.communicate()[0]
