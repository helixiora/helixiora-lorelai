"""User API key model."""

from datetime import datetime
from app.database import db


class UserAPIKey(db.Model):
    """Model for a user API key."""

    __tablename__ = "user_api_keys"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="user_api_key_id")
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    api_key = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    user = db.relationship("User", back_populates="api_keys")

    def __repr__(self):
        """Return a string representation of the user API key."""
        return f"<UserAPIKey {self.api_key}>"

    def is_expired(self) -> bool:
        """Check if the API key is expired."""
        return self.expires_at and self.expires_at < datetime.utcnow()
