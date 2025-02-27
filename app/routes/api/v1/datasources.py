"""API routes for datasource configuration."""

import logging
from flask_login import current_user
from flask_restx import Namespace, Resource
from app.models.datasource_config import DatasourceConfig

datasources_ns = Namespace(
    "datasources",
    description="Operations related to datasource configuration",
)


@datasources_ns.route("/<plugin_name>/config/<field_name>")
class DatasourceConfigValue(Resource):
    """Resource for getting sensitive configuration values."""

    @datasources_ns.doc(
        description="Get the current value of a sensitive field",
        responses={
            200: "Success",
            403: "Field is not sensitive",
            404: "Plugin or field not found",
        },
    )
    def get(self, plugin_name: str, field_name: str):
        """Get the current value of a sensitive field.

        This endpoint is used to fetch sensitive values that are masked in the UI.
        It will only return values for fields marked as sensitive in the plugin's manifest.
        """
        # Get the plugin's manifest to verify the field is sensitive
        from lorelai.datasources.registry import DatasourceRegistry

        registry = DatasourceRegistry()
        registry.load_plugins()

        plugin = next((p for p in registry.plugins if p["name"] == plugin_name), None)
        if not plugin:
            logging.warning(
                "Attempt to access non-existent plugin %s by user %s",
                plugin_name,
                current_user.id,
            )
            return {"error": "Plugin not found"}, 404

        # Find the field in the config
        field = next((f for f in plugin["config"] if f["key"] == field_name), None)
        if not field:
            logging.warning(
                "Attempt to access non-existent field %s in plugin %s by user %s",
                field_name,
                plugin_name,
                current_user.id,
            )
            return {"error": "Field not found"}, 404

        # Only allow fetching sensitive fields
        if not field.get("sensitive"):
            logging.warning(
                "Attempt to access non-sensitive field %s in plugin %s by user %s",
                field_name,
                plugin_name,
                current_user.id,
            )
            return {"error": "Field is not sensitive"}, 403

        # Get the value from the database
        config = DatasourceConfig.query.filter_by(
            user_id=current_user.id, plugin_name=plugin_name, field_name=field_name
        ).first()

        if not config:
            logging.info(
                "No value found for sensitive field %s in plugin %s for user %s",
                field_name,
                plugin_name,
                current_user.id,
            )
            return {"error": "Value not found"}, 404

        logging.info(
            "Sensitive value retrieved for field %s in plugin %s by user %s",
            field_name,
            plugin_name,
            current_user.id,
        )
        return {"value": config.value}
