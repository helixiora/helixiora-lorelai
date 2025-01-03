"""Google Drive model."""

from datetime import datetime
from . import db


class GoogleDriveItem(db.Model):
    """Model for a Google Drive item."""

    __tablename__ = "google_drive_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    google_drive_id = db.Column(db.String(255), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    item_type = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    item_url = db.Column(db.String(255), nullable=False)
    icon_url = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_indexed_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        """Return a string representation of the Google Drive item."""
        return f"<GoogleDriveItem {self.item_name} ({self.item_type})>"

    def __str__(self):
        """Return a string representation of the Google Drive item."""
        return f"{self.item_name} ({self.item_type})"
