import os
import re
import sys
from pathlib import Path
from typing import Callable, Collection, Optional

import psutil

from mirror_mcsmcdr.mcdr_config import CONFIG_FILE, MCDRConfigError, read_mcdr_config
from mirror_mcsmcdr.server.status import Origin, ProcessInfo

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


def is_console_host(process: psutil.Process) -> bool:
    """Whether the process hosts the console window of its parent on Windows. :raise psutil.Error: if the name cannot be read"""
    return process.name().lower() == "conhost.exe"


def is_server_of(process: psutil.Process, mcdr: psutil.Process) -> bool:
    """
    Whether ``process``, a child of ``mcdr``, is the server as the config of that MCDR describes it now.

    MCDR runs a ``start_command`` string through the shell and a list directly, in ``working_directory``.
    False whenever something cannot be read, or the config was changed after the server started.
    """
    try:
        mcdr_cwd = Path(mcdr.cwd())
        config = read_mcdr_config(mcdr_cwd / _config_argument(mcdr.cmdline()))
        cmdline = process.cmdline()
    except (psutil.Error, MCDRConfigError):
        return False
    command = config.get("start_command")
    if isinstance(command, str):
        matches = _shell_runs(cmdline, command)
    elif isinstance(command, list) and all(isinstance(arg, str) for arg in command):
        matches = cmdline == command
    else:
        matches = False
    working_directory = config.get("working_directory", "server")
    if not matches or not isinstance(working_directory, str):
        return matches
    try:
        cwd = process.cwd()
    except psutil.Error:
        # the command alone has to do
        return True
    return _same_path(cwd, str(mcdr_cwd / working_directory))


def _config_argument(mcdr_cmdline: list[str]) -> str:
    """The value of ``--config`` that MCDR was started with, which is relative to its working directory."""
    for index, arg in enumerate(mcdr_cmdline):
        if arg == "--config" and index + 1 < len(mcdr_cmdline):
            return mcdr_cmdline[index + 1]
        if arg.startswith("--config="):
            return arg[len("--config="):]
    return CONFIG_FILE


def _shell_runs(cmdline: list[str], command: str) -> bool:
    """Whether ``cmdline`` is the shell that ``subprocess`` starts for ``command`` with ``shell=True``."""
    if sys.platform == "win32":
        # "cmd.exe /c <command>": its arguments are read back split at spaces and without their quotes
        return (
            len(cmdline) > 2 and os.path.basename(cmdline[0]).lower() == "cmd.exe" and cmdline[1].lower() == "/c"
            and " ".join(cmdline[2:]).replace('"', "").split() == command.replace('"', "").split()
        )
    return cmdline == ["/bin/sh", "-c", command]


def find_mcdr_in(path: str, exclude: Collection[int]) -> list[psutil.Process]:
    """
    The MCDR instances of this user that run with ``path`` as their working directory, looked for among all processes.

    Only the outermost of a chain counts: an entry point launcher and the interpreter it starts are one instance.
    A process whose working directory, owner or arguments cannot be read is passed over.

    :param exclude: pids not to look at
    """
    def named(name: str) -> bool:
        name = name.lower()
        return bool(_PYTHON.match(name)) or name in _MCDR_SCRIPTS

    return _find_in(path, exclude, named, is_mcdr)


def find_java_in(path: str, exclude: Collection[int], name: re.Pattern[str]) -> list[psutil.Process]:
    """
    The Java processes of this user that run with ``path`` as their working directory, as :func:`find_mcdr_in` finds MCDR.

    :param name: what the name of the process has to match, searched for in it as it is
    """
    return _find_in(path, exclude, lambda process_name: name.search(process_name) is not None, lambda _: True)


def _find_in(
    path: str, exclude: Collection[int], named: Callable[[str], bool], matches: Callable[[psutil.Process], bool],
) -> list[psutil.Process]:
    target = _normalized(path)
    owner = _owner(psutil.Process())
    found: dict[int, psutil.Process] = {}
    # by name first: the working directory and the arguments are read from the process itself, which is slow on Windows
    for process in psutil.process_iter(["name"]):
        if process.pid in exclude or not named(process.info["name"] or ""):
            continue
        try:
            if _normalized(process.cwd()) == target and _owner(process) == owner and matches(process):
                found[process.pid] = process
        except psutil.Error:
            continue
    outermost = []
    for process in found.values():
        try:
            if process.ppid() in found:
                continue
        except psutil.Error:
            continue
        outermost.append(process)
    return outermost


def _owner(process: psutil.Process) -> object:
    """:raise psutil.Error: if the owner cannot be read"""
    return process.uids().real if sys.platform.startswith("linux") else process.username()


def _normalized(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def _same_path(a: str, b: str) -> bool:
    return _normalized(a) == _normalized(b)


def describe(process: psutil.Process, origin: Origin) -> ProcessInfo:
    """What can be said about a process; what cannot be read is left empty."""
    try:
        name = process.name()
    except psutil.Error:
        name = ""
    try:
        cmdline = " ".join(process.cmdline())
    except psutil.Error:
        cmdline = ""
    return ProcessInfo(process.pid, name, cmdline, origin)
