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
    # the ``sync.extra_patterns`` patterns that are not negated and match nothing outside the worlds on their own
    missing_extras: tuple[str, ...]
    # the source directories that the sync would have to read and cannot, each with the reason:
    # the source itself, a directory walked for ``sync.extra_patterns``, and each selected directory
    unreadable: tuple[tuple[str, str], ...] = ()

    @property
    def paths(self) -> tuple[str, ...]:
        """Everything selected, relative to the server directory."""
        return self.worlds + self.extras


def _selecting(patterns: Sequence[str]) -> list[tuple[str, pathspec.GitIgnoreSpec]]:
    """Each pattern that selects something on its own: a negation or a comment selects nothing, so it cannot be missing."""
    return [
        (pattern, spec)
        for pattern in patterns
        for spec in [pathspec.GitIgnoreSpec.from_lines([pattern])]
        if any(compiled.include for compiled in spec.patterns)
    ]


class Selector:
    def __init__(self, world: Sequence[str], extra_patterns: Sequence[str]) -> None:
        """:raise ValueError: if a pattern is not valid"""
        self._world = compile_patterns("world", world)
        self._selecting_world = _selecting(world)
        self._extra = compile_patterns("extra_patterns", extra_patterns)
        # without a pattern that selects, nothing outside the worlds has to be walked
        self._selecting_extra = _selecting(extra_patterns)

    def select(self, source: str) -> Selection:
        try:
            names = sorted(os.listdir(source))
        except (FileNotFoundError, NotADirectoryError):
            # nothing is there to select, so every pattern is missing
            names = []
        except OSError as e:
            # whether anything is missing cannot be told
            return Selection(worlds=(), extras=(), world_files=(), missing_worlds=(), missing_extras=(), unreadable=((source, _reason(e)),))
        unreadable: list[tuple[str, str]] = []
        matched = [name for name in names if self._world.match_file(name)]
        directories = {name for name in names if os.path.isdir(os.path.join(source, name))}
        worlds = tuple(name for name in matched if name in directories)
        if self._selecting_extra and names:
            extras, missing_extras = self._find_extras(source, set(worlds), unreadable)
        else:
            extras, missing_extras = (), tuple(pattern for pattern, _ in self._selecting_extra)
        # a selected directory that cannot be listed would fail only once the mirror is stopped and the target partly deleted;
        # only its top level is tried, as walking every world before each sync would cost as much as the sync itself
        for path in worlds + extras:
            full_path = os.path.join(source, *path.split("/"))
            if os.path.isdir(full_path):
                try:
                    with os.scandir(full_path):
                        pass
                except OSError as e:
                    unreadable.append((full_path, _reason(e)))
        return Selection(
            worlds=worlds,
            extras=extras,
            world_files=tuple(name for name in matched if name not in directories and name not in extras),
            missing_worlds=tuple(pattern for pattern, spec in self._selecting_world if not any(spec.match_file(name) for name in directories)),
            missing_extras=missing_extras,
            unreadable=tuple(unreadable),
        )

    def _find_extras(self, source: str, worlds: set[str], unreadable: list[tuple[str, str]]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """
        Walk ``source`` outside the worlds. A directory is matched as ``path/``, so that a pattern such as ``config/``
        selects it as a whole; it is then not descended into, nor is a link to a directory.

        :param unreadable: receives each directory that cannot be walked, with the reason
        :return: the selected paths, and the patterns that match nothing on their own. A pattern that matches only
            inside a selected directory is not missing, so for such patterns those directories are walked as well
        """
        found: list[str] = []
        unmatched = dict(self._selecting_extra)

        def walk(directory: str, prefix: str, selecting: bool) -> None:
            if not selecting and not unmatched:
                return
            try:
                with os.scandir(directory) as iterator:
                    entries = sorted(iterator, key=lambda entry: entry.name)
            except OSError as e:
                unreadable.append((directory, _reason(e)))
                return
            for entry in entries:
                if not prefix and entry.name in worlds:
                    continue
                path = prefix + entry.name
                is_dir = entry.is_dir()
                tested = path + "/" if is_dir else path
                for pattern in [pattern for pattern, spec in unmatched.items() if spec.match_file(tested)]:
                    del unmatched[pattern]
                selected = selecting and self._extra.match_file(tested)
                if selected:
                    found.append(path)
                if is_dir and not entry.is_symlink() and (not selected or unmatched):
                    walk(entry.path, path + "/", selecting and not selected)
                if not selecting and not unmatched:
                    return

        walk(source, "", True)
        return tuple(found), tuple(unmatched)


def _reason(error: OSError) -> str:
    return error.strerror or type(error).__name__


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
