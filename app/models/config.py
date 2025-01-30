"""Configuration model for system settings."""

from app.database import db


class Config(db.Model):
    """Model for storing system configurations."""

    __tablename__ = "config"

    config_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp())
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp(),
    )

    @classmethod
    def get_value(cls, key: str, default: str = None) -> str:
        """Get a configuration value by key."""
        config = cls.query.filter_by(key=key).first()
        return config.value if config else default

    @classmethod
    def set_value(cls, key: str, value: str, description: str = None) -> None:
        """Set a configuration value."""
        config = cls.query.filter_by(key=key).first()
        if config:
            config.value = value
            if description:
                config.description = description
        else:
            config = cls(key=key, value=value, description=description)
            db.session.add(config)
        db.session.commit()
