"""Reads the config of the mirror's MCDR, which is not the MCDR running this plugin."""
from pathlib import Path
from typing import Any, Optional

from ruamel.yaml import YAML

# mcdreforged.constants.core_constant.CONFIG_FILE_PATH, the file MCDR reads unless told otherwise by --config
CONFIG_FILE = "config.yml"


class MCDRConfigError(Exception):

    def __init__(self, path: Path, error: Optional[Exception]) -> None:
        """:param error: why the file cannot be read; None if it was read but holds no mapping"""
        super().__init__(f"{path}: {error if error is not None else 'not a mapping'}")
        self.path = path
        self.error = error


def read_mcdr_config(path: Path) -> dict[str, Any]:
    """:raise MCDRConfigError: if the file is no MCDR config"""
    try:
        with path.open("r", encoding="utf8") as file:
            data = YAML(typ="safe").load(file)
    except Exception as e:
        raise MCDRConfigError(path, e) from e
    if not isinstance(data, dict):
        raise MCDRConfigError(path, None)
    return data
