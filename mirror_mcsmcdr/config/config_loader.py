from mcdreforged.api.all import PluginServerInterface
from copy import deepcopy
from pathlib import Path
from mirror_mcsmcdr.config.mirror_config import MirrorConfig, MultiMirrorConfig
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from typing import Dict, Optional, Tuple


class MultiConfigLoader:
    """Load, validate, merge, and save the annotated plugin YAML config."""

    CONFIG_FILE_NAME = 'config.yml'
    LEGACY_CONFIG_FILE_NAME = 'config.json'
    DEFAULT_CONFIG_FILE_NAME = 'default_config.yml'

    def __init__(self, server: PluginServerInterface) -> None:
        self.user_config: Optional[dict[str, dict]] = None
        self.parent_config: Optional[MirrorConfig] = None
        self.server = server
        data_folder = Path(server.get_data_folder())
        self.config_path = data_folder / self.CONFIG_FILE_NAME
        self.legacy_config_path = data_folder / self.LEGACY_CONFIG_FILE_NAME

    def load(self):
        """Load all mirror configs and preserve annotations when saving."""
        yaml = self._create_yaml()
        template = self._load_template(yaml)
        user_config, source_path = self._load_user_config()

        template_prefix = next(iter(template))
        if user_config:
            first_prefix = next(iter(user_config))
            first_data = user_config[first_prefix]
        else:
            first_prefix = template_prefix
            first_data = {}

        parent_config = MirrorConfig().deserialize(first_data)
        needs_save = parent_config.serialize() != first_data
        if needs_save:
            self.server.logger.info("Merge missing keys for mirror config.")
        self.parent_config = parent_config
        self.user_config = user_config

        annotated_first = deepcopy(template[template_prefix])
        self._apply_values(annotated_first, parent_config.serialize())
        needs_save = needs_save or source_path is None or source_path != self.config_path or first_data != annotated_first
        if not needs_save:
            return
        if source_path is None:
            export_config = CommentedMap({first_prefix: annotated_first})
            self.server.logger.warning("Config missing. Create new config.yml with default values.")
        else:
            export_config = deepcopy(user_config)
            export_config[first_prefix] = annotated_first
        self._save(yaml, export_config)

    def get_all_prefix(self):
        if not self.user_config:
            raise RuntimeError("Config not loaded. Call load() first.")
        return list(self.user_config.keys())

    def get_mirror_config(self, command_prefix: str) -> MirrorConfig:
        if not isinstance(self.parent_config, MirrorConfig) or not self.user_config:
            raise RuntimeError("Config not loaded. Call load() first.")
        if command_prefix not in self.user_config:
            raise RuntimeError("Command prefix not found in user config.")
        config = deepcopy(self.parent_config)
        config.merge_from(MirrorConfig().deserialize(self.user_config[command_prefix]))
        return config

    def _load_template(self, yaml: YAML) -> CommentedMap:
        with self.server.open_bundled_file(self.DEFAULT_CONFIG_FILE_NAME) as file:
            return yaml.load(file.read().decode('utf8'))

    def _load_user_config(self) -> Tuple[Dict[str, dict] | {}, Optional[Path]]:
        path = self.config_path
        if not path.is_file():
            if self.legacy_config_path.is_file():
                path = self.legacy_config_path
                self.server.logger.warning("JSON format is outdated. Convert legacy config.json to config.yml")
                return self.server.load_config_simple("config.json"), path
            else:
                return {}, None

        yaml = YAML(typ='safe')
        with path.open('r', encoding='utf8') as file:
            return yaml.load(file), path

    @staticmethod
    def _create_yaml() -> YAML:
        yaml = YAML()
        yaml.width = 1048576
        return yaml

    def _save(self, yaml: YAML, data: CommentedMap | dict) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open('w', encoding='utf8', newline='\n') as file:
            yaml.dump(data, file)

    @classmethod
    def _apply_values(cls, target: dict, values: dict) -> None:
        """Apply resolved config values while retaining template comments."""
        for key, value in values.items():
            if key not in target:
                continue
            if isinstance(target[key], dict) and isinstance(value, dict):
                cls._apply_values(target[key], value)
            else:
                target[key] = value
