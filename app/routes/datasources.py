"""Routes for datasource configuration."""

from flask import Blueprint, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.models.datasource_config import DatasourceConfig
from app.database import db

datasources_bp = Blueprint("datasources", __name__)


@datasources_bp.route("/datasources/<plugin_name>/config", methods=["POST"])
@login_required
def save_config(plugin_name: str):
    """Save the configuration for a datasource plugin.

    Args:
        plugin_name: The name of the plugin to save configuration for
    """
    # Get the plugin's manifest to validate fields
    from lorelai.datasources.registry import DatasourceRegistry

    registry = DatasourceRegistry()
    registry.load_plugins()

    plugin = next((p for p in registry.plugins if p["name"] == plugin_name), None)
    if not plugin:
        flash(f"Plugin {plugin_name} not found", "error")
        return redirect(url_for("auth.profile"))

    # Save each field from the form
    for field in plugin["config"]:
        field_key = field["key"]
        field_value = request.form.get(field_key, "")

        # Skip empty optional fields
        if not field_value and not field["required"]:
            continue

        # Validate required fields
        if field["required"] and not field_value:
            flash(f"Field {field['title']} is required", "error")
            return redirect(url_for("auth.profile"))

        # Update or create config in database
        config = DatasourceConfig.query.filter_by(
            user_id=current_user.id, plugin_name=plugin_name, field_name=field_key
        ).first()

        if config:
            config.value = field_value
        else:
            config = DatasourceConfig(
                user_id=current_user.id,
                plugin_name=plugin_name,
                field_name=field_key,
                value=field_value,
            )
            db.session.add(config)

    try:
        db.session.commit()
        flash(f"Configuration saved for {plugin_name}", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving configuration: {str(e)}", "error")

    return redirect(url_for("auth.profile"))
