import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import Sequence

import xxhash

from mirror_mcsmcdr.sync.selection import PathPatterns, WorldPatterns, WorldSelection


class ClassicWorldSynchronizer:
    

    def __init__(self, world: Sequence[str], ignore_inexistent_target_path: bool, concurrency: int, ignore_patterns: Sequence[str], retain_patterns: Sequence[str]) -> None:
        """:raise ValueError: if a pattern is not valid"""
        self.world = WorldPatterns(world)
        self.paths = PathPatterns(ignore_patterns, retain_patterns)
        self.ignore_inexistent_target_path = ignore_inexistent_target_path
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


    def select(self, source: str) -> WorldSelection:
        return self.world.select(source)

    def overlapping(self, source: str, target_paths: list[str], worlds: Sequence[str]) -> list[tuple[str, str]]:
        """
        The pairs of a source world and a target world that are one directory, or one inside the other:
        syncing them would delete or overwrite the very files it copies from.
        """
        sources = [os.path.join(source, world) for world in worlds]
        targets = [os.path.join(target, world) for target in target_paths for world in worlds]
        return [(source_world, target_world) for source_world in sources for target_world in targets if _overlap(source_world, target_world)]

    def sync(self, source: str, target_paths: list[str], worlds: Sequence[str]):
        """:param worlds: names of the source's top-level directories to copy, as :meth:`select` found them"""
        source = os.path.normpath(source)

        changed_files_count = 0
        paths_notfound = []

        for target_path in target_paths:
            target_path = os.path.normpath(target_path)

            if not os.path.exists(target_path):
                if not self.ignore_inexistent_target_path:
                    paths_notfound.append(target_path)
                    continue
                os.makedirs(target_path)

            copies: list[str] = []
            for world in worlds:
                self._sync_entry(source, target_path, world, copies)
            with ThreadPoolExecutor(max_workers=self.concurrency) as executor:
                changed = executor.map(self._copy_if_changed, [_join(source, path) for path in copies], [_join(target_path, path) for path in copies])
                changed_files_count += sum(changed)
        
        return changed_files_count, paths_notfound

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
