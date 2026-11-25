"""
Backs up the mirror world with the mirror's own PrimeBackup, through its command line tool.

Nothing here touches MCDR: paths of the main server are relative to the current working directory,
paths read from the mirror's files are relative to the mirror's MCDR directory.
"""
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import pathspec
import psutil

from mirror_mcsmcdr.mcdr_config import CONFIG_FILE, MCDRConfigError, read_mcdr_config

PRIME_BACKUP_ID = "prime_backup"
# the first version whose command line tool can make a backup
MIN_PRIME_BACKUP_VERSION = (1, 13, 0)

# MCDR's own constants (mcdreforged.constants.plugin_constant), so that plugins are found like MCDR finds them
_PLUGIN_CONFIG_DIRECTORY = "config"
_PLUGIN_META_FILE = "mcdreforged.plugin.json"
_LINK_DIRECTORY_PLUGIN_FILE = "mcdreforged.linked_directory_plugin.json"
_PACKED_PLUGIN_SUFFIXES = (".mcdr", ".pyz")
_DISABLED_PLUGIN_SUFFIX = ".disabled"

# PrimeBackup's own defaults (prime_backup.config), for the keys its config file leaves out
_DB_FILE_NAME = "prime_backup.db"
_DEFAULT_STORAGE_ROOT = "./pb_files"
_DEFAULT_SOURCE_ROOT = "./server"
_DEFAULT_TARGETS = ["world"]
_DEFAULT_IGNORE_PATTERNS = ["session.lock"]

_VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?")
# a log line of PrimeBackup's command line tool; it is meant for humans, so anything unexpected is a failure
_BACKUP_DONE = re.compile(r"^\[[^\]\n]*\] Create backup #(\d+) done", re.MULTILINE)
_OUTPUT_TAIL_LINES = 20
_VERSION_PROBE_TIMEOUT = 30


class BackupError(Exception):
    """
    A reason why there is no backup; ``reason`` names a translation below ``command.sync.backup.reason``.

    That translation is shown in game, so it must not use the values that reveal paths; those go to the console as :attr:`detail`.
    """

    def __init__(self, reason: str, output: str = "", **kwargs: Any) -> None:
        super().__init__(reason, kwargs)
        self.reason = reason
        self.kwargs = kwargs
        # what the command line tool printed, if it ran
        self.output = output

    @property
    def detail(self) -> str:
        return ", ".join(f"{key}={value}" for key, value in self.kwargs.items())

    @property
    def output_tail(self) -> str:
        return "\n".join(self.output.splitlines()[-_OUTPUT_TAIL_LINES:])


class BackupUnavailable(BackupError):
    """The backup cannot be made, so it is not attempted."""

    @classmethod
    def from_mcdr_config(cls, error: MCDRConfigError) -> "BackupUnavailable":
        """For the mirror's MCDR config that cannot be read, or holds something MCDR does not accept."""
        if error.error is None:
            return cls("mcdr_config_invalid", path=str(error.path), option="/")
        return cls("mcdr_config_unreadable", path=str(error.path), error=str(error.error))


class BackupFailed(BackupError):
    """The command line tool ran but did not report a backup."""


@dataclass(frozen=True)
class BackupWarning:
    """
    A setting of the mirror's PrimeBackup that keeps part of what the sync overwrites out of the backup.

    ``key`` names a translation below ``command.sync.backup.warning``; it may reveal paths, so it is for the console only.
    """

    key: str
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedBackup:
    """Where the mirror's PrimeBackup is and what it backs up; all paths are absolute."""

    mcdr_path: str
    plugin_path: str
    plugin_version: str
    config_path: str
    # the "backup" section of the mirror's PrimeBackup config
    backup_config: dict[str, Any]
    storage_path: str
    source_path: str
    # the directories the sync copies into, as configured or derived
    targets: tuple[str, ...]
    # what the sync copies into each target: its worlds and extra paths, relative and joined with "/"
    paths: tuple[str, ...]


@dataclass(frozen=True)
class _PluginFile:
    plugin_id: Any
    version: Any
    # what the interpreter runs: the packed file, the plugin directory or the target of a link
    runnable_path: Path


class MirrorBackup:
    """
    Resolves the mirror's PrimeBackup and backs the mirror up with it, with its settings as they are.

    Nothing is cached: every call reads the mirror's files again, so a result is only as current as the call.
    """

    def __init__(self, mcdr_path: Optional[str], sync_patterns: list[str], timeout: float) -> None:
        """
        :param mcdr_path: the mirror's MCDR directory, None for a plain server, which has none
        :param sync_patterns: the sync's ignore and retain patterns, which it does not copy
        :param timeout: seconds a backup may take
        """
        if timeout <= 0:
            raise ValueError("sync.backup.timeout must be positive")
        self.mcdr_path = mcdr_path
        self.sync_patterns = sync_patterns
        self.timeout = timeout

    # ---------- resolution ----------

    def resolve(self, targets: Sequence[str], paths: Sequence[str]) -> ResolvedBackup:
        """
        Locate the mirror's PrimeBackup: its plugin, its config, its storage and the directory it backs up.

        :param targets: the directories the sync copies into. A sync passes those it copies into,
            so that what is backed up and checked is what gets overwritten
        :param paths: what the sync copies into them, relative to each and joined with "/"
        """
        if not self.mcdr_path:
            raise BackupUnavailable("plain_server")
        mcdr_path = Path(os.path.abspath(self.mcdr_path))
        if not mcdr_path.is_dir():
            raise BackupUnavailable("mcdr_path_not_found", path=str(mcdr_path))

        mcdr_config = self._read_mcdr_config(mcdr_path)
        plugin = self._find_plugin(mcdr_path, self._plugin_directories(mcdr_path, mcdr_config))
        plugin_config_path = mcdr_path / _PLUGIN_CONFIG_DIRECTORY / PRIME_BACKUP_ID / "config.json"
        plugin_config = self._read_plugin_config(plugin_config_path)

        storage_root = plugin_config.get("storage_root", _DEFAULT_STORAGE_ROOT)
        backup_config = plugin_config.get("backup", {})
        if not isinstance(storage_root, str):
            raise BackupUnavailable("pb_config_invalid", path=str(plugin_config_path), option="storage_root")
        if not isinstance(backup_config, dict):
            raise BackupUnavailable("pb_config_invalid", path=str(plugin_config_path), option="backup")
        storage_path = Path(os.path.abspath(mcdr_path / storage_root))
        if not (storage_path / _DB_FILE_NAME).is_file():
            raise BackupUnavailable("database_not_found", path=str(storage_path / _DB_FILE_NAME))
        source_path = self._source_path(mcdr_path, mcdr_config, backup_config, plugin_config_path)

        return ResolvedBackup(
            mcdr_path=str(mcdr_path),
            plugin_path=str(plugin.runnable_path),
            plugin_version=str(plugin.version),
            config_path=str(plugin_config_path),
            backup_config=backup_config,
            storage_path=str(storage_path),
            source_path=str(source_path),
            targets=tuple(targets),
            paths=tuple(paths),
        )

    @classmethod
    def _read_mcdr_config(cls, mcdr_path: Path) -> dict[str, Any]:
        try:
            return read_mcdr_config(mcdr_path / CONFIG_FILE)
        except MCDRConfigError as e:
            raise BackupUnavailable.from_mcdr_config(e) from e

    @staticmethod
    def _plugin_directories(mcdr_path: Path, mcdr_config: dict[str, Any]) -> list[Path]:
        directories = mcdr_config.get("plugin_directories", ["plugins"])
        # MCDR reads a null as no plugin directory at all
        if directories is None:
            directories = []
        if not isinstance(directories, list) or not all(isinstance(directory, str) for directory in directories):
            raise BackupUnavailable("mcdr_config_invalid", path=str(mcdr_path / CONFIG_FILE), option="plugin_directories")
        # MCDR drops duplicates as Paths, so "plugins" and "./plugins" are one directory
        return list(dict.fromkeys(mcdr_path / directory for directory in directories))

    @classmethod
    def _find_plugin(cls, mcdr_path: Path, directories: list[Path]) -> _PluginFile:
        # every entry is read: stopping at the first match would hide a duplicate
        found: list[_PluginFile] = []
        for directory in directories:
            if not directory.is_dir():
                continue
            try:
                names = os.listdir(directory)
            except OSError as e:
                # it may hold the plugin, so passing over it could hide a duplicate as well
                raise BackupUnavailable("plugin_directory_unreadable", path=str(directory), error=str(e)) from e
            for name in names:
                plugin = cls._read_plugin(mcdr_path, directory / name)
                if plugin is None or plugin.plugin_id != PRIME_BACKUP_ID:
                    continue
                # the same plugin reached twice, e.g. through two spellings of one directory, is still one plugin
                if not any(_same_path(plugin.runnable_path, other.runnable_path) for other in found):
                    found.append(plugin)
        if not found:
            raise BackupUnavailable("plugin_not_found")
        if len(found) > 1:
            raise BackupUnavailable("plugin_duplicated", paths=", ".join(str(plugin.runnable_path) for plugin in found))
        plugin = found[0]
        if not _version_supported(plugin.version):
            raise BackupUnavailable("plugin_too_old", version=str(plugin.version), path=str(plugin.runnable_path))
        return plugin

    @staticmethod
    def _read_plugin(mcdr_path: Path, path: Path) -> Optional[_PluginFile]:
        """
        Read the metadata of a plugin as MCDR recognizes it (mcdreforged.plugin.plugin_factory).

        :return: None if MCDR would not load ``path`` as a packed or directory plugin, or its metadata is unreadable
        """
        try:
            if path.is_file():
                # a disabled file ends with ".disabled", so its suffix rules it out already
                suffix = path.name[path.name.rfind("."):] if "." in path.name else ""
                if suffix not in _PACKED_PLUGIN_SUFFIXES:
                    return None
                with zipfile.ZipFile(path) as archive, archive.open(_PLUGIN_META_FILE) as file:
                    meta = json.load(file)
                runnable_path = path
            elif path.is_dir() and not path.name.endswith(_DISABLED_PLUGIN_SUFFIX):
                # MCDR does not take a python package as a directory plugin
                if (path / "__init__.py").is_file():
                    return None
                if (path / _PLUGIN_META_FILE).is_file():
                    runnable_path = path
                elif (path / _LINK_DIRECTORY_PLUGIN_FILE).is_file():
                    with (path / _LINK_DIRECTORY_PLUGIN_FILE).open("r", encoding="utf8") as file:
                        link = json.load(file)
                    if not isinstance(link, dict) or not isinstance(link.get("target"), str):
                        return None
                    # MCDR resolves the target against its working directory
                    runnable_path = Path(os.path.abspath(mcdr_path / link["target"]))
                else:
                    return None
                with (runnable_path / _PLUGIN_META_FILE).open("r", encoding="utf8") as file:
                    meta = json.load(file)
            else:
                return None
        except (OSError, ValueError, zipfile.BadZipFile, KeyError):
            # MCDR cannot load it either, so it is not the PrimeBackup the mirror runs
            return None
        if not isinstance(meta, dict):
            return None
        return _PluginFile(meta.get("id"), meta.get("version"), runnable_path)

    @staticmethod
    def _read_plugin_config(path: Path) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf8") as file:
                data = json.load(file)
        except (OSError, ValueError) as e:
            raise BackupUnavailable("pb_config_unreadable", path=str(path), error=str(e)) from e
        if not isinstance(data, dict):
            raise BackupUnavailable("pb_config_invalid", path=str(path), option="/")
        return data

    @staticmethod
    def _source_path(mcdr_path: Path, mcdr_config: dict[str, Any], backup_config: dict[str, Any], plugin_config_path: Path) -> Path:
        use_working_directory = backup_config.get("source_root_use_mcdr_working_directory", False)
        if not isinstance(use_working_directory, bool):
            raise BackupUnavailable("pb_config_invalid", path=str(plugin_config_path), option="backup.source_root_use_mcdr_working_directory")
        # the plugin reads this switch from the running MCDR, the command line tool ignores it
        if use_working_directory:
            source_root = mcdr_config.get("working_directory", "server")
            if not isinstance(source_root, str):
                raise BackupUnavailable("mcdr_config_invalid", path=str(mcdr_path / CONFIG_FILE), option="working_directory")
        else:
            source_root = backup_config.get("source_root", _DEFAULT_SOURCE_ROOT)
            if not isinstance(source_root, str):
                raise BackupUnavailable("pb_config_invalid", path=str(plugin_config_path), option="backup.source_root")
        return Path(os.path.abspath(mcdr_path / source_root))

    # ---------- checks ----------

    def probe(self, resolved: ResolvedBackup) -> None:
        """Run ``--version``: an interpreter without PrimeBackup's dependencies fails here."""
        code, output = _run([sys.executable, resolved.plugin_path, "--version"], resolved.mcdr_path, _VERSION_PROBE_TIMEOUT)
        if code != 0:
            raise BackupUnavailable("probe_failed", output=output, code=code)

    def warnings(self, resolved: ResolvedBackup) -> list[BackupWarning]:
        """
        Where the mirror's PrimeBackup settings differ from the sync settings, so that its backup
        would not hold everything the sync overwrites.

        The backup is made with those settings anyway; this is what whoever syncs has to be told first.
        """
        found: list[BackupWarning] = []
        targets = [os.path.abspath(target) for target in resolved.targets]
        backed_up = [target for target in targets if _same_directory(target, resolved.source_path)]
        if not backed_up:
            found.append(BackupWarning("source_mismatch", {"source": resolved.source_path, "targets": ", ".join(targets)}))
        elif len(backed_up) < len(targets):
            found.append(BackupWarning("targets_not_backed_up", {"targets": ", ".join(target for target in targets if target not in backed_up)}))

        patterns = self._patterns(resolved, "targets", _DEFAULT_TARGETS)
        untargeted = self._untargeted_worlds(resolved, patterns)
        if untargeted:
            found.append(BackupWarning("worlds_not_targeted", {"worlds": ", ".join(untargeted), "targets": ", ".join(patterns)}))

        # only the same string is known to leave out the same: patterns are not compared by what they match
        ignored = [
            pattern
            for pattern in (*self._patterns(resolved, "ignore_patterns", _DEFAULT_IGNORE_PATTERNS), *self._patterns(resolved, "ignored_files", []))
            if pattern not in self.sync_patterns
        ]
        if ignored:
            found.append(BackupWarning("ignored", {"patterns": ", ".join(ignored)}))
        retained = [pattern for pattern in self._patterns(resolved, "retain_patterns", []) if pattern not in self.sync_patterns]
        if retained:
            found.append(BackupWarning("retained", {"patterns": ", ".join(retained)}))
        if resolved.backup_config.get("reuse_stat_unchanged_file", False):
            found.append(BackupWarning("reuse_stat_unchanged_file"))
        if resolved.backup_config.get("creation_skip_missing_file", False):
            found.append(BackupWarning("creation_skip_missing_file"))

        # the sync deletes what only the target has, which would be the backup itself
        for path in (os.path.join(target, *path.split("/")) for target in targets for path in resolved.paths):
            if _is_inside(resolved.storage_path, path):
                found.append(BackupWarning("storage_in_world", {"storage": resolved.storage_path, "world": path}))
        return found

    @staticmethod
    def _patterns(resolved: ResolvedBackup, key: str, default: list[str]) -> list[str]:
        patterns = resolved.backup_config.get(key, default)
        if not isinstance(patterns, list) or not all(isinstance(pattern, str) for pattern in patterns):
            raise BackupUnavailable("pb_config_invalid", path=resolved.config_path, option=f"backup.{key}")
        return [pattern for pattern in patterns if pattern.strip()]

    @staticmethod
    def _untargeted_worlds(resolved: ResolvedBackup, patterns: list[str]) -> list[str]:
        """
        The top-level names of the synced paths that PrimeBackup does not select:
        it matches gitignore patterns against the entries of its source directory.
        """
        try:
            spec = pathspec.GitIgnoreSpec.from_lines(patterns)
        except ValueError as e:
            raise BackupUnavailable("pb_config_invalid", path=resolved.config_path, option="backup.targets", error=str(e)) from e
        try:
            # matched as they are spelled on disk, also where the file system ignores case
            entries = {os.path.normcase(entry): entry for entry in os.listdir(resolved.source_path)}
        except OSError:
            entries = {}
        names = dict.fromkeys(path.split("/")[0] for path in resolved.paths)
        return [name for name in names if not spec.match_file(entries.get(os.path.normcase(name), name))]

    def has_existing_path(self, resolved: ResolvedBackup) -> bool:
        """Whether a target holds one of the paths yet; if none does, the sync has nothing to overwrite."""
        return any(os.path.lexists(os.path.join(target, *path.split("/"))) for target in resolved.targets for path in resolved.paths)

    # ---------- backup ----------

    def make(self, resolved: ResolvedBackup, operator: str) -> int:
        """
        Make a backup with the mirror's PrimeBackup, as it is configured.

        :return: the id of the new backup
        """
        command = [
            sys.executable, resolved.plugin_path,
            "-d", resolved.storage_path,
            "-c", resolved.config_path,
            "make", "-s", resolved.source_path,
            f"MirrorMcsmcdR pre-sync by {operator}",
        ]
        code, output = _run(command, resolved.mcdr_path, self.timeout)
        return _parse_make_output(code, output)


def _parse_make_output(code: int, output: str) -> int:
    """Judge the output of ``make``: it must succeed and name one backup."""
    if code != 0:
        raise BackupFailed("exit_code", output=output, code=code)
    ids = set(_BACKUP_DONE.findall(output))
    if not ids:
        raise BackupFailed("no_backup_id", output=output)
    if len(ids) > 1:
        raise BackupFailed("backup_id_mismatch", output=output, ids=", ".join(sorted(ids)))
    return int(ids.pop())


def _run(command: list[str], cwd: str, timeout: float) -> tuple[int, str]:
    """
    Run ``command`` without a console window and return its exit code and merged output.

    On timeout the process and everything it started is killed and gone before this returns.
    """
    environment = dict(os.environ, PYTHONIOENCODING="utf8")
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=creationflags,
        )
    except OSError as e:
        raise BackupFailed("launch", error=str(e)) from e
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        output, _ = process.communicate()
        raise BackupFailed("timeout", output=output.decode("utf8", errors="replace"), timeout=timeout)
    except BaseException:
        _kill_tree(process)
        raise
    return process.returncode, output.decode("utf8", errors="replace")


def _kill_tree(process: "subprocess.Popen[bytes]") -> None:
    # a venv interpreter on Windows is a launcher that runs the real interpreter as its child
    try:
        children = psutil.Process(process.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            child.kill()
        except psutil.Error:
            pass
    process.kill()
    psutil.wait_procs(children)
    process.wait()


def _version_supported(version: Any) -> bool:
    match = _VERSION.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        return False
    core = tuple(int(part) for part in match.group(1, 2, 3))
    # a pre-release comes before its release
    return core > MIN_PRIME_BACKUP_VERSION or (core == MIN_PRIME_BACKUP_VERSION and match.group(4) is None)


def _same_path(a: Path, b: Path) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def _same_directory(a: str, b: str) -> bool:
    """Compare by filesystem identity; directories that do not exist yet by their normalized real paths."""
    if os.path.exists(a) and os.path.exists(b):
        return os.path.samefile(a, b)
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def _is_inside(path: str, directory: str) -> bool:
    """Whether ``path`` is ``directory`` or below it, with links resolved."""
    path, directory = (os.path.normcase(os.path.realpath(p)) for p in (path, directory))
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:
        # different drives
        return False
