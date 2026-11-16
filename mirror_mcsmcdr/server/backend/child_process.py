import os
import signal
import subprocess
import sys
from threading import Event, Thread
from typing import Optional

from mcdreforged.api.all import RText, ServerInterface

from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.server.action import Action, ActionResult
from mirror_mcsmcdr.server.backend.base import TerminalProxy
from mirror_mcsmcdr.server.status import Evidence
from mirror_mcsmcdr.server.system_utils.port_utils import PortListener


class SubprocessProxy(TerminalProxy):
    """Run the mirror server as a child process with piped console I/O."""

    supports = frozenset(Action)

    def __init__(self, config: TerminalConfig) -> None:
        super().__init__(config)
        assert config.port is not None
        self.listener = PortListener(config.port, config.regex_strict)
        self.process: Optional[subprocess.Popen] = None
        self.console_log_enabled = config.console_log
        self.console_log_limit: Optional[int] = None
        self._output_count = 0
        self._output_thread: Optional[Thread] = None
        self._stop_event = Event()

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def observe(self) -> Evidence:
        return Evidence(process_alive=self.alive, port_listening=self.listener.is_listening())

    def _start(self, result: ActionResult) -> ActionResult:
        if self.alive:
            return result.reject(ActionResult.Outcome.WRONG_STATE)

        if self._output_thread is not None:
            self._output_thread.join(timeout=3)
        self._stop_event.clear()
        self._output_count = 0

        if not os.path.isdir(self.path):
            return result.reject(ActionResult.Outcome.PATH_NOT_FOUND)

        encoding = "oem" if os.name == "nt" else "utf-8"
        self.process = subprocess.Popen(
            self.command,
            cwd=self.path,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding=encoding,
            errors="replace",
            bufsize=1,
            # its own process group, so that the shell can be signalled together with the server it launched
            start_new_session=sys.platform != "win32",
        )
        self._output_thread = Thread(
            target=self._read_output_loop,
            name=self.terminal_name,
            daemon=True,
        )
        self._output_thread.start()
        return result

    def _stop(self, result: ActionResult) -> ActionResult:
        if not self.send_command(self.stop_command):
            self.reset_log_limit()
            return result.reject(ActionResult.Outcome.WRONG_STATE)
        return result

    def _kill(self, result: ActionResult) -> ActionResult:
        process = self.process
        if process is not None:
            self._signal_tree(process, force=False)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                return result.reject(ActionResult.Outcome.TIMEOUT)
            self._cleanup_process()
        return result

    def _forcekill(self, result: ActionResult) -> ActionResult:
        self.forcekill()
        return result

    def forcekill(self) -> None:
        """Kill the child process, if there is one, and wait until it is gone."""
        process = self.process
        if process is None:
            return
        self._signal_tree(process, force=True)
        process.wait()
        self._cleanup_process()

    @staticmethod
    def _signal_tree(process: subprocess.Popen, force: bool) -> None:
        """Signal the launching shell and everything below it; the server is a child of that shell."""
        if sys.platform == "win32":
            # Windows has no graceful signal for a process tree
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            return
        try:
            os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
        except ProcessLookupError:
            pass

    def _read_output_loop(self) -> None:
        process = self.process
        server = ServerInterface.si()
        if process is None or process.stdout is None:
            return

        try:
            while not self._stop_event.is_set():
                line = process.stdout.readline()
                if not line:
                    break
                line = line.rstrip("\r\n")
                if server is not None and self.console_log_enabled or self.console_log_limit is not None:
                    if self.console_log_limit is None or self._output_count < self.console_log_limit:
                        self._output_count += 1
                        server.logger.info(self._format_log_line(line))
                        if self.console_log_limit is not None and self._output_count == self.console_log_limit:
                            server.logger.info(
                                server.rtr("mirror_mcsmcdr.command.log.output_end", count=self.console_log_limit)
                            )
        finally:
            limit = self.console_log_limit
            self.reset_log_limit()
            if limit is not None and server is not None:
                server.logger.info(server.rtr("mirror_mcsmcdr.command.log.reset_on_stop"))

    @staticmethod
    def _format_log_line(line: str) -> RText:
        return RText(f"§7{line}")

    def send_command(self, cmd: str) -> bool:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None:
            return False
        try:
            process.stdin.write(cmd + "\n")
            process.stdin.flush()
        except (BrokenPipeError, ValueError):
            return False
        return True

    def set_console_log(self, enabled: bool) -> None:
        self.console_log_enabled = enabled

    def set_console_log_limit(self, limit: int) -> None:
        self.console_log_limit = limit
        self._output_count = 0

    def reset_log_limit(self) -> None:
        self.console_log_limit = None
        self._output_count = 0

    def _cleanup_process(self) -> None:
        self.reset_log_limit()
        self._stop_event.set()
        if self._output_thread is not None:
            self._output_thread.join(timeout=3)
        self.process = None
        self._output_thread = None
