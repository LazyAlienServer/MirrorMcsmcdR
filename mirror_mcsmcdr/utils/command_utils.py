import os
import subprocess
from typing import Sequence


def capture_command_output(command: Sequence[str]) -> str:
    encoding = "oem" if os.name == "nt" else "utf-8"
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        text=True,
        encoding=encoding,
        shell=True
    )
    return process.communicate()[0]
