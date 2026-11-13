import subprocess
import sys

# Runs in a process of its own: a process is attached to one console at a time,
# and detaching MCDR from its own console to borrow another one would break its console input.
_TYPE_INTO_CONSOLE = r"""
import ctypes, sys
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateFileW.restype = wintypes.HANDLE
GENERIC_READ_WRITE, FILE_SHARE_READ_WRITE, OPEN_EXISTING = 0xC0000000, 0x3, 3
KEY_EVENT, VK_RETURN = 1, 0x0D


class KeyEvent(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("UnicodeChar", wintypes.WCHAR),
        ("dwControlKeyState", wintypes.DWORD),
    ]


class InputRecord(ctypes.Structure):
    _fields_ = [("EventType", wintypes.WORD), ("Event", KeyEvent)]


pid, text = int(sys.argv[1]), sys.argv[2] + "\r"
kernel32.FreeConsole()
if not kernel32.AttachConsole(pid):
    sys.exit(1)
console_input = kernel32.CreateFileW("CONIN$", GENERIC_READ_WRITE, FILE_SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
if console_input == wintypes.HANDLE(-1).value:
    sys.exit(1)
records = (InputRecord * (len(text) * 2))()
for index, char in enumerate(text):
    for offset, key_down in enumerate((True, False)):
        record = records[index * 2 + offset]
        record.EventType = KEY_EVENT
        record.Event = KeyEvent(key_down, 1, VK_RETURN if char == "\r" else 0, 0, char, 0)
written = wintypes.DWORD()
ok = kernel32.WriteConsoleInputW(console_input, records, len(records), ctypes.byref(written))
sys.exit(0 if ok and written.value == len(records) else 1)
"""


def send_console_command(pid: int, command: str) -> bool:
    """
    Type a command, followed by Enter, into the console window that the given process runs in.

    Windows only. Whatever reads that console receives the command,
    which is the given process itself or the one that launched it and shares the console with it.

    :return: whether the command was typed; ``False`` if the process is gone or has no console
    """
    assert sys.platform == "win32"
    try:
        return subprocess.run(
            [sys.executable, "-c", _TYPE_INTO_CONSOLE, str(pid), command],
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        ).returncode == 0
    except subprocess.TimeoutExpired:
        return False
