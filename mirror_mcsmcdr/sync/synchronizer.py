import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Sequence

import xxhash

from mirror_mcsmcdr.config.synchronize_config import MissingConfig
from mirror_mcsmcdr.sync.selection import PathPatterns, Selection, Selector


@dataclass(frozen=True)
class MissingPath:
    """Something the config names that is not there, as ``command.sync.missing.<kind>`` tells it."""

    kind: str
    kwargs: dict[str, str]


@dataclass(frozen=True)
class SyncPlan:
    """What a sync copies where, settled before the mirror is stopped."""

    source: str
    selection: Selection
    # the targets copied into, in the configured order
    targets: tuple[str, ...]
    # those among them that do not exist yet; each is made first
    created: tuple[str, ...]
    refused: tuple[MissingPath, ...]
    skipped: tuple[MissingPath, ...]

    @property
    def existing_targets(self) -> tuple[str, ...]:
        """The targets the sync overwrites, as opposed to those it makes."""
        return tuple(target for target in self.targets if target not in self.created)

    @property
    def empty(self) -> bool:
        """Whether what was skipped leaves nothing to copy."""
        return not self.targets or not self.selection.paths


class SourceVanished(Exception):
    """A selected source path was gone when it was to be copied; copying it would have emptied the target."""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self.path = path


class ClassicWorldSynchronizer:
    

    def __init__(self, world: Sequence[str], extra_patterns: Sequence[str], missing: MissingConfig, concurrency: int, ignore_patterns: Sequence[str], retain_patterns: Sequence[str]) -> None:
        """:raise ValueError: if a pattern is not valid"""
        self.selector = Selector(world, extra_patterns)
        self.paths = PathPatterns(ignore_patterns, retain_patterns)
        self.missing = missing
        self.concurrency = concurrency
    

    def _get_md5(self, filename):
        m = xxhash.xxh128()
        with open(filename, "rb") as file:
            data = file.read(1000000) # 1MB
            m.update(data)
            while data: # python doesn't have "do while" !!!  :-(
                data = file.read(1000000)
                m.update(data)
            file.close()
        return m.digest()


    def _copy_if_changed(self, src_file: str, dst_file: str) -> bool:
        if os.path.exists(dst_file) and self._get_md5(src_file) == self._get_md5(dst_file):
            return False
        shutil.copyfile(src_file, dst_file)
        return True


    def plan(self, source: str, target_paths: Sequence[str]) -> SyncPlan:
        """Select what to copy and judge, by ``sync.missing``, what is not there."""
        source = os.path.normpath(source)
        selection = self.selector.select(source)
        refused: list[MissingPath] = []
        skipped: list[MissingPath] = []

        def judge(refuse: bool, kind: str, **kwargs: str) -> None:
            (refused if refuse else skipped).append(MissingPath(kind, kwargs))

        for pattern in selection.missing_worlds:
            judge(self.missing.source_world == "refuse", "source_world", pattern=pattern, source=source)
        for pattern in selection.missing_extras:
            judge(self.missing.extra_pattern == "refuse", "extra_pattern", pattern=pattern, source=source)
        targets: list[str] = []
        created: list[str] = []
        for target in (os.path.normpath(path) for path in target_paths):
            if os.path.isdir(target):
                targets.append(target)
                if self.missing.target_world == "refuse":
                    for world in selection.worlds:
                        if not os.path.isdir(_join(target, world)):
                            refused.append(MissingPath("target_world", {"path": _join(target, world)}))
            elif os.path.lexists(target):
                refused.append(MissingPath("target_not_directory", {"path": target}))
            elif self.missing.target == "create":
                # only the last component, so that a mistyped path does not grow a tree of its own
                if os.path.isdir(os.path.dirname(os.path.abspath(target))):
                    targets.append(target)
                    created.append(target)
                else:
                    refused.append(MissingPath("target_parent", {"path": target}))
            else:
                judge(self.missing.target == "refuse", "target", path=target)
        return SyncPlan(source, selection, tuple(targets), tuple(created), tuple(refused), tuple(skipped))

    def overlapping(self, source: str, target_paths: Sequence[str], paths: Sequence[str]) -> list[tuple[str, str]]:
        """
        The pairs of a selected source path and a target path that are one, or one inside the other:
        syncing them would delete or overwrite the very files it copies from.
        """
        sources = [_join(source, path) for path in paths]
        targets = [_join(target, path) for target in target_paths for path in paths]
        return [(source_path, target_path) for source_path in sources for target_path in targets if _overlap(source_path, target_path)]

    def clashing(self, source: str, target_paths: Sequence[str], extras: Sequence[str]) -> list[tuple[str, str]]:
        """
        The pairs of a source extra path and what stands in its way in a target: a file where it needs a directory,
        or the other way round. Replacing that would delete what the sync was not told to touch.
        A world is not checked, as it is the sync's own, nor what the sync leaves alone or deletes anyway.
        """
        found = []
        for path in extras:
            if self.paths.retained(path) or self.paths.ignored(path):
                continue
            is_dir = os.path.isdir(_join(source, path))
            for target in target_paths:
                if not os.path.isdir(target):
                    continue
                parts = path.split("/")
                for depth in range(1, len(parts) + 1):
                    target_path = _join(target, "/".join(parts[:depth]))
                    if not os.path.lexists(target_path):
                        break
                    if os.path.isdir(target_path) != (is_dir if depth == len(parts) else True):
                        found.append((_join(source, path), target_path))
                        break
        return found

    def sync(self, plan: SyncPlan) -> int:
        """
        :return: how many files were copied
        :raise SourceVanished: if a selected source path is gone when it is to be copied
        """
        changed_files_count = 0
        worlds = set(plan.selection.worlds)
        for target_path in plan.targets:
            if target_path in plan.created and not os.path.isdir(target_path):
                os.mkdir(target_path)

            copies: list[str] = []
            for path in plan.selection.paths:
                source_path = _join(plan.source, path)
                if not (os.path.isdir(source_path) if path in worlds else os.path.lexists(source_path)):
                    raise SourceVanished(source_path)
                # what is left alone or deleted needs no parent; a world's parent is the target
                if path not in worlds and not (self.paths.retained(path) or self.paths.ignored(path)):
                    os.makedirs(os.path.dirname(_join(target_path, path)), exist_ok=True)
                self._sync_entry(plan.source, target_path, path, copies)
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                changed = executor.map(self._copy_if_changed, [_join(plan.source, path) for path in copies], [_join(target_path, path) for path in copies])
                changed_files_count += sum(changed)
        
        return changed_files_count

    def _sync_entry(self, source: str, target: str, path: str, copies: list[str]) -> None:
        """
        Make ``path`` in ``target`` what it is in ``source``, except for what the patterns leave alone.

        Directories are made and what only the target has is deleted right away;
        the files to compare and copy are collected into ``copies``, so that they are copied in parallel.
        """
        if self.paths.retained(path):
            return
        if self.paths.ignored(path):
            self._remove(target, path)
            return
        src, dst = _join(source, path), _join(target, path)
        if not os.path.isdir(src):
            if os.path.isdir(dst) and not os.path.islink(dst):
                self._remove(target, path)
            copies.append(path)
            return
        if os.path.lexists(dst) and not os.path.isdir(dst):
            os.remove(dst)
        os.makedirs(dst, exist_ok=True)
        names = os.listdir(src)
        for name in set(os.listdir(dst)).difference(names):
            self._remove(target, f"{path}/{name}")
        for name in names:
            self._sync_entry(source, target, f"{path}/{name}", copies)

    def _remove(self, root: str, path: str) -> None:
        """Delete ``path`` in ``root``, except for what is retained; a directory that still holds some is kept."""
        if self.paths.retained(path):
            return
        full_path = _join(root, path)
        if os.path.isdir(full_path) and not os.path.islink(full_path):
            for name in os.listdir(full_path):
                self._remove(root, f"{path}/{name}")
            if not os.listdir(full_path):
                os.rmdir(full_path)
        elif os.path.lexists(full_path):
            os.remove(full_path)


def _join(root: str, path: str) -> str:
    """Join a ``/``-separated relative path to ``root`` with the separator of this platform."""
    return os.path.join(root, *path.split("/"))


def _overlap(a: str, b: str) -> bool:
    a, b = (os.path.normcase(os.path.realpath(path)) for path in (a, b))
    try:
        return os.path.commonpath([a, b]) in (a, b)
    except ValueError:
        # on different drives
        return False
