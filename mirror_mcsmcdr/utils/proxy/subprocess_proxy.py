import os
import subprocess
from threading import Event, Thread
from typing import Optional

from mcdreforged.api.all import RText, ServerInterface


from mirror_mcsmcdr.config.proxy_config import TerminalConfig
from mirror_mcsmcdr.utils.port_utils import PortListener
from mirror_mcsmcdr.utils.proxy.system_proxy import TerminalProxy
from mirror_mcsmcdr.utils.status import Action, ActionResult, Evidence


class SubprocessProxy(TerminalProxy):
    """Run the mirror server as a child process with piped console I/O."""

    supports = frozenset(Action)

    def __init__(self, config: TerminalConfig) -> None:
        super().__init__(config)
        # without a port the server cannot be told apart from one that is still starting
        self.listener = PortListener(config.port, config.regex_strict) if config.port else None
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
        return Evidence(
            process_alive=self.alive,
            port_listening=bool(self.listener.pids()) if self.listener is not None else None,
        )

    def perform(self, result: ActionResult) -> ActionResult:
        action = result.action
        if action is Action.START:
            return self._start(result)
        if action is Action.STOP:
            if not self.send_command(self.stop_command):
                self.reset_log_limit()
                return result.reject(ActionResult.Outcome.WRONG_STATE)
        elif action is Action.KILL:
            process = self.process
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    return result.reject(ActionResult.Outcome.TIMEOUT)
                self._cleanup_process()
        else:
            self.forcekill()
        return result

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
        )
        self._output_thread = Thread(
            target=self._read_output_loop,
            name=self.terminal_name,
            daemon=True,
        )
        self._output_thread.start()
        return result

    def forcekill(self) -> None:
        """Kill the child process, if there is one, and wait until it is gone."""
        process = self.process
        if process is None:
            return
        process.kill()
        process.wait()
        self._cleanup_process()

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
