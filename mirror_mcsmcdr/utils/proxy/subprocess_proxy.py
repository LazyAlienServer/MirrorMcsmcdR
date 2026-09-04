import os
import subprocess
from threading import Event, Thread
from typing import Optional

from mcdreforged.api.all import RText, ServerInterface


from mirror_mcsmcdr.utils.proxy.system_proxy import AbstractSystemProxy
from mirror_mcsmcdr.utils.status import ServerStatus


class SubprocessProxy(AbstractSystemProxy):
    """Run the mirror server as a child process with piped console I/O."""

    def __init__(
        self,
        terminal_name: str,
        path: str,
        command: str,
        port: int,
        regex_strict: bool,
        is_mcdr: bool = True,
        console_log: bool = False,
    ) -> None:
        super().__init__(terminal_name, path, command, port, regex_strict, is_mcdr)
        self.process: Optional[subprocess.Popen] = None
        self.console_log_enabled = console_log
        self.console_log_limit: Optional[int] = None
        self._output_count = 0
        self._output_thread: Optional[Thread] = None
        self._stop_event = Event()

    def start(self) -> str:
        if self.process is not None and self.process.poll() is None:
            return "already running"

        if self._output_thread is not None:
            self._output_thread.join(timeout=3)
        self._stop_event.clear()
        self._output_count = 0

        if not os.path.isdir(self.path):
            return "path_not_found"

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
        )
        self._output_thread = Thread(
            target=self._read_output_loop,
            name=f"{self.terminal_name}-output",
            daemon=True,
        )
        self._output_thread.start()
        return "success"

    def status(self) -> ServerStatus:
        if self.process is None or self.process.poll() is not None:
            return ServerStatus.STOPPED
        return ServerStatus.RUNNING

    def stop(self) -> str:
        if self.status() == ServerStatus.STOPPED:
            return ServerStatus.STOPPED

        stop_command = "!!MCDR server stop_exit" if self.is_mcdr else "stop"
        sent = self._send_command(stop_command)
        if not sent:
            self.reset_log_limit()
            return ServerStatus.STOPPING
        return "success"
    def kill(self) -> str:
        if self.status() == ServerStatus.STOPPED:
            self.reset_log_limit()
            return ServerStatus.STOPPED

        process = self.process
        assert process is not None
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return "timeout"
        self._cleanup_process()
        return "success"

    def forcekill(self) -> str:
        if self.status() == ServerStatus.STOPPED:
            self.reset_log_limit()
            return ServerStatus.STOPPED

        process = self.process
        assert process is not None
        process.kill()
        process.wait()
        self._cleanup_process()
        return "success"

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

    def _format_log_line(self, line: str) -> RText:
        return RText(f"§7[{self.terminal_name}] {line}")

    def _send_command(self, cmd: str) -> bool:
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
