"""Profile model."""

from app.database import db
from lorelai.datasources.registry import DatasourceRegistry
from flask import current_app


class Profile(db.Model):
    """Model for a profile."""

    __tablename__ = "user_profile"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="profile_id")
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.user_id"),
        unique=True,
        nullable=False,
    )
    bio = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    # Relationships
    user = db.relationship("User", back_populates="profile")

    def __repr__(self):
        """Return a string representation of the profile."""
        return f"<Profile of {self.user.email}>"

    def get_plugin_configs(self):
        """Fetch plugin configurations if the plugin architecture is enabled."""
        if current_app.config["FEATURE_PLUGIN_ARCHITECTURE"]:
            registry = DatasourceRegistry(current_app.config["DATASOURCE_PLUGIN_DIR"])
            registry.load_plugins()
            return registry.get_plugin_configs()
        return []
