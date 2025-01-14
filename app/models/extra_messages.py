"""Extra messages model."""

from datetime import datetime
from sqlalchemy.dialects.mysql import INTEGER
from app.database import db


class ExtraMessages(db.Model):
    """Model for the extra_messages table."""

    __tablename__ = "extra_messages"

    user_id = db.Column(
        db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"), primary_key=True
    )
    quantity = db.Column(INTEGER(unsigned=True), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.TIMESTAMP, nullable=True, default=datetime.utcnow)
    updated_at = db.Column(
        db.TIMESTAMP, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationship to User
    user = db.relationship("User", back_populates="extra_messages")

    def __repr__(self):
        """Return a string representation of the extra message entry."""
        return f"<ExtraMessages user_id={self.user_id}, quantity={self.quantity}, \
is_active={self.is_active}>"
