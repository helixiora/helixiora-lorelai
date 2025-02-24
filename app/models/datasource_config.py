"""Model for storing datasource configurations."""

from app.database import db


class DatasourceConfig(db.Model):
    """Model for storing datasource configurations."""

    __tablename__ = "datasource_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    plugin_name = db.Column(db.String(255), nullable=False)
    field_name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text, nullable=True)

    # Relationships
    user = db.relationship("User", backref=db.backref("datasource_configs", lazy=True))

    # Unique constraint to prevent duplicate configs
    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "plugin_name", "field_name", name="unique_user_plugin_field"
        ),
    )

    def __repr__(self):
        """Return string representation of the config."""
        return f"<DatasourceConfig {self.plugin_name}.{self.field_name}>"
