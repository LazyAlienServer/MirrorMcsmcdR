import os
import re
import sys
from typing import Optional

import psutil

from mirror_mcsmcdr.server.status import ProcessInfo

# python, python3, python3.12, pythonw, pypy3 and their .exe forms
_PYTHON = re.compile(r"^(python|pythonw|pypy)(\d+(\.\d+)*)?(\.exe)?$")
# a script or launcher named like this runs MCDR: MCDReforged.py of a source checkout, or the mcdreforged entry point
_MCDR_SCRIPTS = frozenset({"mcdreforged.py", "mcdreforged", "mcdreforged.exe"})
# interpreter options that take the next argument as their value
_OPTIONS_WITH_VALUE = frozenset({"-X", "-W", "--check-hash-based-pycs"})
# what a launch command runs in: the terminal, its shell and, on Windows, the console host
_SHELLS = frozenset({"screen", "sh", "bash", "dash", "zsh", "ksh", "ash", "fish", "cmd.exe", "conhost.exe", "powershell.exe", "pwsh", "pwsh.exe"})

_boot_id: Optional[str] = None


def start_token(process: psutil.Process) -> str:
    """
    What tells this process from a later one that gets the same pid.

    On Linux the boot id and the start time in clock ticks since boot, which a change of the system clock leaves alone.
    Elsewhere the creation time.
    """
    if sys.platform.startswith("linux"):
        global _boot_id
        if _boot_id is None:
            with open("/proc/sys/kernel/random/boot_id", encoding="ascii") as file:
                _boot_id = file.read().strip()
        try:
            with open(f"/proc/{process.pid}/stat", encoding="utf8", errors="replace") as file:
                stat = file.read()
        except FileNotFoundError:
            raise psutil.NoSuchProcess(process.pid) from None
        # the name in parentheses may hold spaces; the start time is the 20th field after it
        return f"{_boot_id}:{stat[stat.rindex(')') + 2:].split()[19]}"
    return repr(process.create_time())


def is_alive(process: psutil.Process) -> bool:
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def is_mcdr(process: psutil.Process) -> bool:
    """
    Whether the process is an MCDR instance, told from its arguments as the interpreter parses them.

    A shell that merely carries an MCDR command line, such as ``cmd /C python -m mcdreforged``, is not.

    :raise psutil.Error: if the arguments cannot be read
    """
    cmdline = process.cmdline()
    if not cmdline:
        return False
    executable = os.path.basename(cmdline[0]).lower()
    if executable in ("mcdreforged", "mcdreforged.exe"):
        return True
    if not _PYTHON.match(executable):
        return False
    args = cmdline[1:]
    index = 0
    while index < len(args):
        arg = args[index]
        if arg.startswith("-m"):
            module = arg[2:] or (args[index + 1] if index + 1 < len(args) else "")
            return module == "mcdreforged"
        if arg.startswith("-c") or arg == "-":
            return False
        if arg.startswith("-"):
            index += 2 if arg in _OPTIONS_WITH_VALUE else 1
            continue
        return os.path.basename(arg).lower() in _MCDR_SCRIPTS
    return False


def is_shell(process: psutil.Process) -> bool:
    """:raise psutil.Error: if the name cannot be read"""
    return process.name().lower() in _SHELLS


def describe(process: psutil.Process, in_record: bool) -> ProcessInfo:
    """What can be said about a process; what cannot be read is left empty."""
    try:
        name = process.name()
    except psutil.Error:
        name = ""
    try:
        cmdline = " ".join(process.cmdline())
    except psutil.Error:
        cmdline = ""
    return ProcessInfo(process.pid, name, cmdline, in_record)
