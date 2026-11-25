"""
What a sync copies: gitignore patterns, matched the way the mirror's PrimeBackup matches its own.

``sync.world`` is matched against the bare names of the source's top-level entries, as PrimeBackup's ``backup.targets``;
``sync.ignore_patterns`` and ``sync.retain_patterns`` against paths relative to the server directory,
as PrimeBackup's patterns of the same names. Matching is case-sensitive on every platform.
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
class WorldSelection:
    """The worlds ``sync.world`` selects in one source directory."""

    # names of the selected top-level directories
    worlds: tuple[str, ...]
    # names of the top-level files the patterns match: a world is a directory, so these are not synced
    files: tuple[str, ...]
    # the patterns that are not negated and select no directory on their own
    missing: tuple[str, ...]


class WorldPatterns:
    def __init__(self, patterns: Sequence[str]) -> None:
        self._spec = compile_patterns("world", patterns)
        # a negation or a comment selects nothing by itself, so only the others can be missing
        self._selecting = [
            (pattern, spec)
            for pattern in patterns
            for spec in [pathspec.GitIgnoreSpec.from_lines([pattern])]
            if any(compiled.include for compiled in spec.patterns)
        ]

    def select(self, source: str) -> WorldSelection:
        try:
            names = sorted(os.listdir(source))
        except (FileNotFoundError, NotADirectoryError):
            # nothing is there to select, so every pattern is missing
            names = []
        matched = [name for name in names if self._spec.match_file(name)]
        directories = {name for name in names if os.path.isdir(os.path.join(source, name))}
        return WorldSelection(
            worlds=tuple(name for name in matched if name in directories),
            files=tuple(name for name in matched if name not in directories),
            missing=tuple(pattern for pattern, spec in self._selecting if not any(spec.match_file(name) for name in directories)),
        )


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
