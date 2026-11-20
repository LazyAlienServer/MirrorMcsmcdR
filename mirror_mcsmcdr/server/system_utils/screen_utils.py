import re
import subprocess
import time
from threading import Lock
from typing import Optional, Sequence


class ScreenError(RuntimeError):
    """A screen command failed, or what became of it cannot be told."""


class Screen:
    """
    A detached GNU screen session with the server launched from the shell inside it, addressed by its pid.

    The pid is set by :meth:`create`, or given by whoever kept it from an earlier launch.
    Every method may be called from any thread.
    """

    # screen accepts 80 bytes after -S, and "<pid>." takes up to 8 of them
    _MAX_NAME_BYTES = 64
    # screen rebuilds a command received through -X in a 768 byte buffer and cuts off the rest without an error
    _MAX_STUFF_BYTES = 740
    _COMMAND_TIMEOUT = 5.0
    _DISCOVERY_TIMEOUT = 2.0
    _LIVE_STATES = ("attached", "detached")

    # Shared by all sessions: a new session is told from the difference between two listings,
    # which another mirror creating a session of the same name in between would spoil.
    # Taken before the lock of the instance, never the other way round.
    _create_lock = Lock()

    def __init__(self, name: str, path: str, pid: Optional[int] = None, window: str = "0") -> None:
        """
        :param window: the window commands are typed into; a session the plugin creates has only window 0
        :raise ScreenError: if screen cannot address a session of this name
        """
        if not name or len(name.encode()) > self._MAX_NAME_BYTES or any(ord(char) < 0x20 or ord(char) == 0x7F for char in name):
            raise ScreenError(f"Invalid screen name {name!r}: 1 to {self._MAX_NAME_BYTES} bytes without control characters are required")
        self.name = name
        self.path = path
        # None until a session is created or given
        self.pid = pid
        self.window = window
        self._lock = Lock()
        self._parses_remote_commands: Optional[bool] = None

    def exists(self) -> bool:
        """
        :raise ScreenError: if the sessions could not be listed
        """
        with self._lock:
            return self._session_pid() is not None

    def create(self, command: str) -> None:
        """
        Start a session in ``path`` and type ``command`` into its shell.

        The session closes itself when the command ends successfully, and stays open for inspection when it fails.

        :raise ScreenError: if the session could not be started, or could not be told from the others.
            In the last case a session that nothing refers to may be left behind.
            :attr:`pid` is set if a session was started that may be running the command after all
        """
        with self._create_lock, self._lock:
            text = self._stuff_text(command + "&&exit")
            known = self._sessions()
            started = self._run(["-dmS", self.name], cwd=self.path)
            if started.returncode != 0:
                raise ScreenError(f"Cannot start screen {self.name}: {self._output(started)}")
            self.pid = self._discover(known)
            try:
                self._send_to(self.pid, ["-p", "0", "-X", "stuff", text])
            except ScreenError as error:
                raise ScreenError(f"Cannot launch in screen {self.name}: {error}{self._discard(self.pid)}") from error

    def send(self, command: str) -> None:
        """
        Type a command into the session.

        Returning means that screen took the command, not that whatever runs in the session acted on it.

        :raise ScreenError: if there is no session, or screen did not take the command
        """
        with self._lock:
            text = self._stuff_text(command)
            pid = self._session_pid()
            if pid is None:
                raise ScreenError(f"Screen {self.name} does not exist")
            self._send_to(pid, ["-p", self.window, "-X", "stuff", text])

    def quit(self) -> None:
        """
        Close the session, which hangs up on everything in it; nothing happens if there is none.

        The session may take a moment to disappear after this returns.

        :raise ScreenError: if the session is still there and screen did not take the command
        """
        with self._lock:
            pid = self._session_pid()
            if pid is None:
                return
            try:
                self._send_to(pid, ["-X", "quit"])
            except ScreenError:
                # it may have ended by itself in the meantime, which is just as good
                if self._session_pid() is not None:
                    raise

    def _session_pid(self) -> Optional[int]:
        """The pid of the session if it is alive."""
        if self.pid is not None and (self.pid, self.name) in self._sessions():
            return self.pid
        return None

    def _sessions(self) -> set[tuple[int, str]]:
        """
        The live sessions of this user as (pid, name). A dead socket waiting for ``screen -wipe`` is not one.

        :raise ScreenError: if the listing is not recognized, since "none" would make the callers forget their session
        """
        listing = self._run(["-ls"])
        output = self._output(listing)
        sessions = set()
        recognized = "No Sockets found" in output
        for line in listing.stdout.splitlines():
            # "\t<pid>.<name>\t(<date>)\t(<state>)", the date only since screen 4.1
            fields = line.strip().split("\t")
            pid, _, name = fields[0].partition(".")
            if len(fields) < 2 or not pid.isdigit() or not name:
                continue
            recognized = True
            if fields[-1].strip("()").lower().endswith(self._LIVE_STATES):
                sessions.add((int(pid), name))
        if not recognized:
            raise ScreenError(f"Cannot list screens: {output}")
        return sessions

    def _discover(self, known: set[tuple[int, str]]) -> int:
        """Wait for the session that was just started to show up, which happens a moment after screen returns."""
        deadline = time.monotonic() + self._DISCOVERY_TIMEOUT
        while True:
            new = [pid for pid, name in self._sessions() - known if name == self.name]
            if len(new) == 1:
                return new[0]
            if len(new) > 1:
                raise ScreenError(f"Several screens named {self.name} appeared at once ({new}), none of them is used")
            if time.monotonic() >= deadline:
                raise ScreenError(f"Screen {self.name} was started but did not show up")
            time.sleep(0.1)

    def _discard(self, pid: int) -> str:
        """
        Close a session that could not be used.

        :return: what is left to say about it: nothing if it is gone.
            Otherwise :attr:`pid` stays set, since the launch may have gone through after all
        """
        try:
            self._send_to(pid, ["-X", "quit"])
        except ScreenError:
            try:
                gone = (pid, self.name) not in self._sessions()
            except ScreenError:
                gone = False
            if not gone:
                return f"; screen {pid}.{self.name} could not be closed and may still be running"
        self.pid = None
        return ""

    def _send_to(self, pid: int, args: Sequence[str]) -> None:
        # always by pid: the name alone is ambiguous as soon as two mirrors share it
        sent = self._run(["-S", f"{pid}.{self.name}", *args])
        if sent.returncode != 0:
            raise ScreenError(f"Screen {self.name} rejected `{' '.join(args[:3])}`: {self._output(sent)}")

    def _run(self, args: Sequence[str], cwd: Optional[str] = None) -> "subprocess.CompletedProcess[str]":
        try:
            return subprocess.run(["screen", *args], cwd=cwd, capture_output=True, text=True, errors="replace", timeout=self._COMMAND_TIMEOUT)
        except OSError as error:
            raise ScreenError(f"Cannot run screen: {error}") from error
        except subprocess.TimeoutExpired:
            raise ScreenError(f"`screen {' '.join(args[:3])}` did not return in time; it may have taken effect all the same") from None

    @staticmethod
    def _output(completed: "subprocess.CompletedProcess[str]") -> str:
        return (completed.stdout + completed.stderr).strip()

    def _stuff_text(self, line: str) -> str:
        """
        One line of input, followed by Enter, in the form the ``stuff`` command of the installed screen types it literally.

        :raise ScreenError: if the line is longer than screen can take
        """
        if self._parses_remote_commands is None:
            # "Screen version 4.09.01 (GNU) 20-Aug-23"; anything unreadable is taken for a current version
            version = re.search(r"Screen version (\d+)\.(\d+)", self._output(self._run(["-v"])))
            self._parses_remote_commands = version is None or (int(version.group(1)), int(version.group(2))) >= (4, 1)
        if not self._parses_remote_commands:
            # up to 4.0 the text is typed exactly as it is given
            return line + "\n"
        # Since 4.1 a command received through -X is parsed like a line of screenrc, even without a shell in between:
        # ^x is a control character, \ an escape and $ a variable.
        text = line.replace("\\", "\\\\").replace("^", "\\^").replace("$", "\\$") + "\n"
        # a double quote costs one more byte when screen rebuilds the command
        size = len(text.encode()) + text.count('"')
        if size > self._MAX_STUFF_BYTES:
            raise ScreenError(f"The command is too long for screen ({size} bytes, at most {self._MAX_STUFF_BYTES}): put it into a script and run that instead")
        return text
