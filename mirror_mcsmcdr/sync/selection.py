"""
What a sync copies: gitignore patterns, matched the way the mirror's PrimeBackup matches its own.

``sync.world`` is matched against the bare names of the source's top-level entries, as PrimeBackup's ``backup.targets``;
``sync.extra_patterns``, ``sync.ignore_patterns`` and ``sync.retain_patterns`` against paths relative to the server directory,
the latter two as PrimeBackup's patterns of the same names. Matching is case-sensitive on every platform.
"""
import os
from dataclasses import dataclass
from typing import Sequence

import pathspec


def compile_patterns(option: str, patterns: Sequence[str]) -> pathspec.GitIgnoreSpec:
    """:raise ValueError: naming ``sync.<option>``, if a pattern is not valid"""
    try:
        return pathspec.GitIgnoreSpec.from_lines(patterns)
    except ValueError as e:
        raise ValueError(f"sync.{option}: {e}") from e


@dataclass(frozen=True)
class Selection:
    """What a sync copies from one source directory."""

    # names of the top-level directories ``sync.world`` selects
    worlds: tuple[str, ...]
    # ``/``-separated paths ``sync.extra_patterns`` selects outside the worlds; a selected directory is one path
    extras: tuple[str, ...]
    # names of the top-level files ``sync.world`` matches and ``sync.extra_patterns`` does not:
    # a world is a directory, so these are not synced
    world_files: tuple[str, ...]
    # the ``sync.world`` patterns that are not negated and select no directory on their own
    missing_worlds: tuple[str, ...]

    @property
    def paths(self) -> tuple[str, ...]:
        """Everything selected, relative to the server directory."""
        return self.worlds + self.extras


class Selector:
    def __init__(self, world: Sequence[str], extra_patterns: Sequence[str]) -> None:
        """:raise ValueError: if a pattern is not valid"""
        self._world = compile_patterns("world", world)
        # a negation or a comment selects nothing by itself, so only the others can be missing
        self._selecting_world = [
            (pattern, spec)
            for pattern in world
            for spec in [pathspec.GitIgnoreSpec.from_lines([pattern])]
            if any(compiled.include for compiled in spec.patterns)
        ]
        self._extra = compile_patterns("extra_patterns", extra_patterns)
        # without a pattern that selects, nothing outside the worlds has to be walked
        self._walks_extra = any(compiled.include for compiled in self._extra.patterns)

    def select(self, source: str) -> Selection:
        try:
            names = sorted(os.listdir(source))
        except (FileNotFoundError, NotADirectoryError):
            # nothing is there to select, so every pattern is missing
            names = []
        matched = [name for name in names if self._world.match_file(name)]
        directories = {name for name in names if os.path.isdir(os.path.join(source, name))}
        worlds = tuple(name for name in matched if name in directories)
        extras = tuple(self._find_extras(source, set(worlds))) if self._walks_extra and names else ()
        return Selection(
            worlds=worlds,
            extras=extras,
            world_files=tuple(name for name in matched if name not in directories and name not in extras),
            missing_worlds=tuple(pattern for pattern, spec in self._selecting_world if not any(spec.match_file(name) for name in directories)),
        )

    def _find_extras(self, source: str, worlds: set[str]) -> list[str]:
        """
        Walk ``source`` outside the worlds. A directory is matched as ``path/``, so that a pattern such as ``config/``
        selects it as a whole; it is then not descended into, nor is a link to a directory.
        """
        found: list[str] = []

        def walk(directory: str, prefix: str) -> None:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name)
            for entry in entries:
                if not prefix and entry.name in worlds:
                    continue
                path = prefix + entry.name
                is_dir = entry.is_dir()
                if self._extra.match_file(path + "/" if is_dir else path):
                    found.append(path)
                elif is_dir and not entry.is_symlink():
                    walk(entry.path, path + "/")

        walk(source, "")
        return found


class PathPatterns:
    """
    What a sync leaves alone inside the paths it copies; a path matched by both is retained.

    A matched directory is not descended into. Paths are relative to the server directory and joined with ``/``.
    """

    def __init__(self, ignore_patterns: Sequence[str], retain_patterns: Sequence[str]) -> None:
        self._ignore = compile_patterns("ignore_patterns", ignore_patterns)
        self._retain = compile_patterns("retain_patterns", retain_patterns)

    def ignored(self, path: str) -> bool:
        """Not copied, and deleted in the target."""
        return self._ignore.match_file(path)

    def retained(self, path: str) -> bool:
        """Not copied, and the target's copy is kept as it is."""
        return self._retain.match_file(path)
