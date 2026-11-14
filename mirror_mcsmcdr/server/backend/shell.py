import subprocess
from typing import Any, Optional, Sequence, Union


ShellCommand = Union[str, Sequence[str]]


def run_shell_command(
    command: ShellCommand,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> subprocess.Popen:
    return subprocess.Popen(command, shell=True, cwd=cwd, **kwargs)
