from mcdreforged.api.all import PluginServerInterface, RTextBase, RTextList
from copy import deepcopy
from pathlib import Path
from mirror_mcsmcdr.config.mirror_config import MirrorConfig, MultiMirrorConfig
from mirror_mcsmcdr.constants import PLUGIN_ID, REPLY_TITLE
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from typing import Any, Dict, List, Optional, Tuple
import hashlib
import os
import time


class MultiConfigLoader:
    """Load, validate, merge, and save the annotated plugin YAML config."""

    CONFIG_FILE_NAME = 'config.yml'
    LEGACY_CONFIG_FILE_NAME = 'config.json'
    DEFAULT_CONFIG_DIR = 'default_config'
    DEFAULT_LANGUAGE = 'en_us'

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

        schema = MirrorConfig().serialize()
        unknown: Dict[str, List[Tuple[str, Any]]] = {}
        for prefix, data in user_config.items():
            if not isinstance(data, dict):
                continue
            kept, removed = self._strip_unknown(schema, data)
            if removed:
                user_config[prefix] = kept
                unknown[prefix] = removed

        template_prefix = next(iter(template))
        if user_config:
            first_prefix = next(iter(user_config))
            first_data = user_config[first_prefix]
            parent_config = MirrorConfig.deserialize(self._inherit(MirrorConfig().serialize(), first_data))
            needs_save = parent_config.serialize() != first_data
            if needs_save:
                self.server.logger.info(self._rtr("merged"))
        else:
            first_prefix = template_prefix
            parent_config = MirrorConfig()
            user_config = {first_prefix: parent_config.serialize()}
            first_data = user_config[first_prefix]
            # written out with its annotations, also over a file without any entry
            needs_save = True
            if source_path is not None:
                self.server.logger.info(self._rtr("merged"))
        self.parent_config = parent_config
        self.user_config = user_config

        annotated_first = deepcopy(template[template_prefix])
        self._apply_values(annotated_first, parent_config.serialize())
        first_data_defined = bool(user_config) and first_prefix in user_config
        needs_save = needs_save or source_path is None or source_path != self.config_path or (first_data_defined and first_data != annotated_first) or bool(unknown)
        if not needs_save:
            return
        export_config = deepcopy(template)
        if template_prefix != first_prefix:
            del export_config[template_prefix]
        export_config[first_prefix] = annotated_first
        self._report_unknown(unknown, source_path)
        if source_path is None:
            self.server.logger.warning(self._rtr("created"))
        else:
            for prefix, config in user_config.items():
                if prefix != first_prefix:
                    export_config[prefix] = deepcopy(config)
        export_config.ca.comment = template.ca.comment
        export_config.ca.end = template.ca.end
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
        # merged as plain data: a deserialized entry would bring its defaults along and override the parent with them
        return MirrorConfig.deserialize(self._inherit(self.parent_config.serialize(), self.user_config[command_prefix]))

    def _rtr(self, key: str, **kwargs: Any) -> RTextBase:
        # not text_utils.rtr: importing it here would import the config package from itself through the server package
        return self.server.rtr(f"{PLUGIN_ID}.config_loader.{key}", **kwargs)

    def _report_unknown(self, unknown: Dict[str, List[Tuple[str, Any]]], source_path: Optional[Path]) -> None:
        """Tell what is about to be removed; a YAML source is backed up first, a legacy JSON one already is."""
        if not unknown:
            return
        for prefix, removed in unknown.items():
            for path, value in removed:
                self.server.logger.warning(self._rtr("unknown_key", prefix=prefix, path=path, value=repr(value)))
        if source_path == self.config_path:
            content = source_path.read_bytes()
            stamp = time.strftime('%Y%m%d-%H%M%S')
            backup_path = source_path.with_name(f"{source_path.name}.{stamp}-{hashlib.sha256(content).hexdigest()[:6]}.bak")
            backup_path.write_bytes(content)
            self.server.logger.warning(self._rtr("backup", path=backup_path))
        count = sum(map(len, unknown.values()))
        self.server.broadcast(RTextList(REPLY_TITLE + " ", self._rtr("unknown_removed", count=count)))

    @classmethod
    def _strip_unknown(cls, schema: dict, data: dict, path: str = '') -> Tuple[dict, List[Tuple[str, Any]]]:
        """
        Split ``data`` into the keys ``schema`` knows and the ones it does not, the latter as (full dotted path, value).

        A dotted key such as ``display.server_name`` is known if its whole path is; it is kept as written.
        """
        kept: dict = {}
        removed: List[Tuple[str, Any]] = []
        for key, value in data.items():
            head, _, rest = str(key).partition(".")
            if head not in schema:
                removed.append((f"{path}{key}", value))
                continue
            node = schema[head]
            if rest:
                if not isinstance(node, dict):
                    removed.append((f"{path}{key}", value))
                    continue
                inner_kept, inner_removed = cls._strip_unknown(node, {rest: value}, f"{path}{head}.")
                removed += inner_removed
                if inner_kept:
                    kept[key] = inner_kept[rest]
            elif isinstance(node, dict) and isinstance(value, dict):
                kept[key], inner_removed = cls._strip_unknown(node, value, f"{path}{key}.")
                removed += inner_removed
            else:
                kept[key] = value
        return kept, removed

    def _load_template(self, yaml: YAML) -> CommentedMap:
        lang = self.server.get_mcdr_language()
        template_name = f'{self.DEFAULT_CONFIG_DIR}/{lang}.yml'
        try:
            with self.server.open_bundled_file(template_name) as file:
                return yaml.load(file.read().decode('utf8'))
        except (FileNotFoundError, OSError):
            fallback_name = f'{self.DEFAULT_CONFIG_DIR}/{self.DEFAULT_LANGUAGE}.yml'
            with self.server.open_bundled_file(fallback_name) as file:
                return yaml.load(file.read().decode('utf8'))

    def _load_user_config(self) -> Tuple[Dict[str, dict], Optional[Path]]:
        path = self.config_path
        if not path.is_file():
            if self.legacy_config_path.is_file():
                path = self.legacy_config_path
                self.server.logger.warning(self._rtr("legacy_json"))
                config = self.server.load_config_simple("config.json")
                if not isinstance(config, dict):
                    raise ValueError("Legacy config.json must contain a JSON object")
                os.rename(path, path.with_suffix('.json.bak'))
                return config, path
            else:
                return {}, None

        yaml = YAML(typ='safe')
        with path.open('r', encoding='utf8') as file:
            # a blank or comment-only file parses as None; it is taken as no entries, so the defaults apply
            return yaml.load(file) or {}, path

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
    def _inherit(cls, parent: dict, child: Optional[dict]) -> dict:
        """
        Return ``parent`` with the values of ``child`` on top; only mappings are merged, anything else is replaced.

        A key of ``child`` may be a dotted path: ``display.server_name: x`` is ``display: {server_name: x}``.
        """
        merged = dict(parent)
        for key, value in (child or {}).items():
            head, _, rest = str(key).partition(".")
            if rest:
                key, value = head, {rest: value}
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = cls._inherit(merged[key], value)
            else:
                merged[key] = value
        return merged

    @classmethod
    def _apply_values(cls, target: dict, values: dict) -> None:
        """Apply resolved config values while retaining template comments."""
        for key, value in values.items():
            if key not in target:
                continue
            if isinstance(target[key], dict) and isinstance(value, dict):
                cls._apply_values(target[key], value)
            elif isinstance(target[key], CommentedSeq) and isinstance(value, list) and value:
                # the comment of the next key hangs on the last item of this list, so the list is refilled, not replaced
                sequence = target[key]
                trailing = sequence.ca.items.pop(len(sequence) - 1, None)
                sequence[:] = value
                if trailing is not None:
                    sequence.ca.items[len(sequence) - 1] = trailing
            else:
                target[key] = value
