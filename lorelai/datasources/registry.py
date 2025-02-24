"""Registry for all datasources."""

import os
import json
import logging
import re
import importlib.util
from typing import Any
from flask import current_app
from packaging import version
from lorelai.datasources.datasource import DatasourceBase
from lorelai.datasources.datatypes import is_supported_datatype, get_form_attributes


class DatasourceRegistry:
    """Registry for all datasources."""

    # Regex for valid plugin names and field keys
    VALID_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

    # Class-level cache for plugin configs
    _plugin_configs_cache = {}

    def __init__(self):
        """Initialize the registry using the plugin directory from config."""
        self.plugin_dir = current_app.config["DATASOURCE_PLUGIN_DIR"]
        self.plugins = []
        self.datasource_classes = {}
        self.plugin_errors = {}  # Store errors by plugin name/directory
        self._load_plugins()  # Load plugins once during initialization

    @staticmethod
    def _validate_version(ver: str) -> bool:
        """Validate version string format."""
        try:
            version.parse(ver)
            return True
        except version.InvalidVersion:
            return False

    @classmethod
    def _validate_name(cls, name: str) -> bool:
        """Validate plugin or field name format."""
        return bool(cls.VALID_NAME_PATTERN.match(name))

    def _load_plugins(self):
        """Load plugins from the plugin directory."""
        self.plugins = []
        self.datasource_classes = {}
        self.plugin_errors = {}

        for subdir in os.listdir(self.plugin_dir):
            try:
                manifest_path = os.path.join(self.plugin_dir, subdir, "manifest.json")
                if not os.path.isfile(manifest_path):
                    continue

                with open(manifest_path) as manifest_file:
                    try:
                        manifest = json.load(manifest_file)
                        self.validate_manifest(manifest)

                        # Validate plugin name format
                        if not self._validate_name(manifest["name"]):
                            raise ValueError(
                                f"Invalid plugin name format: {manifest['name']}. "
                                "Must start with a letter and contain only letters, numbers, "
                                "underscores, and hyphens."
                            )

                        # Validate version format
                        if not self._validate_version(manifest["version"]):
                            raise ValueError(
                                f"Invalid version format: {manifest['version']}. "
                                "Must be a valid semantic version (e.g., 1.0.0)."
                            )

                        # Validate the config schema format
                        self._validate_config_schema(manifest["name"], manifest["config"])

                        # Load the datasource class
                        module_path = os.path.join(self.plugin_dir, subdir, f"{subdir}.py")
                        if not os.path.isfile(module_path):
                            raise ValueError(f"Missing plugin implementation file: {subdir}.py")

                        spec = importlib.util.spec_from_file_location(subdir, module_path)
                        if not spec or not spec.loader:
                            raise ImportError(f"Failed to load plugin module: {subdir}")

                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Find the datasource class
                        datasource_class = None
                        for item in dir(module):
                            obj = getattr(module, item)
                            if (
                                isinstance(obj, type)
                                and issubclass(obj, DatasourceBase)
                                and obj != DatasourceBase
                            ):
                                datasource_class = obj
                                break

                        if not datasource_class:
                            raise ValueError(f"No valid datasource class found in {subdir}")

                        # If we get here, the plugin is valid
                        self.plugins.append(manifest)
                        self.datasource_classes[manifest["name"]] = datasource_class

                    except (json.JSONDecodeError, KeyError, ValueError, ImportError) as e:
                        error_msg = f"Failed to load plugin: {str(e)}"
                        logging.error(f"Error loading plugin {subdir}: {error_msg}")
                        self.plugin_errors[subdir] = error_msg

            except Exception as e:
                error_msg = f"Unexpected error loading plugin: {str(e)}"
                logging.error(f"Error loading plugin {subdir}: {error_msg}")
                self.plugin_errors[subdir] = error_msg

    def load_plugins(self):
        """Public method to reload plugins if needed."""
        self._load_plugins()
        self.clear_cache()  # Clear cache when plugins are reloaded

    def _validate_config_schema(self, plugin_name: str, config: list[dict]):
        """Validate that manifest config follows the required format."""
        # Check that each config item has the required fields
        required_fields = {"key", "datatype", "title", "description", "sensitive", "required"}

        # Track keys to ensure uniqueness
        seen_keys = set()

        for field in config:
            missing_fields = required_fields - set(field.keys())
            if missing_fields:
                raise ValueError(
                    f"Plugin {plugin_name} config field {field.get('key', 'unknown')} "
                    f"is missing required attributes: {missing_fields}"
                )

            # Check key uniqueness
            if field["key"] in seen_keys:
                raise ValueError(f"Duplicate field key '{field['key']}' in plugin {plugin_name}")
            seen_keys.add(field["key"])

            # Validate key format
            if not self._validate_name(field["key"]):
                raise ValueError(
                    f"Invalid field key format: {field['key']}. "
                    "Must start with a letter and contain only letters, numbers, underscores, and "
                    "hyphens."
                )

            # Validate field types
            if not isinstance(field["key"], str):
                raise ValueError(f"Field 'key' must be a string in {field['key']}")
            if not isinstance(field["datatype"], str):
                raise ValueError(f"Field 'datatype' must be a string in {field['key']}")
            if not isinstance(field["title"], str):
                raise ValueError(f"Field 'title' must be a string in {field['key']}")
            if not isinstance(field["description"], str):
                raise ValueError(f"Field 'description' must be a string in {field['key']}")
            if not isinstance(field["sensitive"], bool):
                raise ValueError(f"Field 'sensitive' must be a boolean in {field['key']}")
            if not isinstance(field["required"], bool):
                raise ValueError(f"Field 'required' must be a boolean in {field['key']}")

            # Validate that the datatype is supported
            if not is_supported_datatype(field["datatype"]):
                raise ValueError(
                    f"Plugin {plugin_name} config field {field['key']} "
                    f"has unsupported datatype: {field['datatype']}"
                )

    @staticmethod
    def validate_manifest(manifest: dict):
        """Validate the manifest file."""
        required_fields = ["name", "version", "author", "description", "config"]
        missing_fields = [field for field in required_fields if field not in manifest]
        if missing_fields:
            raise KeyError(f"Missing required fields in manifest: {', '.join(missing_fields)}")

        # Validate logo URL if provided
        if "logo" in manifest and not isinstance(manifest["logo"], str):
            raise ValueError("Logo must be a string URL")

    @classmethod
    def clear_cache(cls):
        """Clear the plugin configs cache."""
        cls._plugin_configs_cache.clear()

    def get_plugin_configs(self, user_id: int | None = None) -> dict[str, Any]:
        """Return the configuration fields for all plugins and any errors encountered.

        Args:
            user_id: Optional user ID to fetch saved values for
        """
        # Use class-level cache with user_id as part of the key
        cache_key = f"plugins_{user_id}"
        if cache_key in self._plugin_configs_cache:
            return self._plugin_configs_cache[cache_key]

        plugins = []
        for plugin in self.plugins:
            config_fields = []
            for field in plugin["config"]:
                # Add form attributes to each field
                try:
                    field_with_attrs = field.copy()
                    field_with_attrs["form_attrs"] = get_form_attributes(field["datatype"])

                    # If user_id is provided, fetch saved value
                    if user_id:
                        from app.models.datasource_config import DatasourceConfig

                        try:
                            config = DatasourceConfig.query.filter_by(
                                user_id=user_id, plugin_name=plugin["name"], field_name=field["key"]
                            ).first()
                            if config and not field.get("sensitive"):
                                field_with_attrs["value"] = config.value
                                logging.debug(
                                    "Loaded config value for user %s, plugin %s, field %s",
                                    user_id,
                                    plugin["name"],
                                    field["key"],
                                )
                        except Exception as e:
                            logging.error(
                                "Error loading config for user %s, plugin %s, field %s: %s",
                                user_id,
                                plugin["name"],
                                field["key"],
                                str(e),
                            )

                    config_fields.append(field_with_attrs)
                except ValueError as e:
                    logging.error(f"Error getting form attributes for field {field['key']}: {e}")
                    # Still include the field even if we can't get form attributes
                    config_fields.append(field)

            plugins.append(
                {
                    "name": plugin["name"],
                    "version": plugin["version"],
                    "author": plugin["author"],
                    "description": plugin["description"],
                    "logo": plugin.get("logo"),
                    "config": config_fields,
                }
            )

        result = {
            "plugins": plugins,
            "errors": self.plugin_errors,
        }

        # Cache the result
        self._plugin_configs_cache[cache_key] = result
        return result
