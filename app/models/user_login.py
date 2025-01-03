"""User login model."""

from . import db


class UserLogin(db.Model):
    """Model for a user login."""

    __tablename__ = "user_login"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    login_time = db.Column(db.DateTime, nullable=False)
    login_type = db.Column(db.String(255), nullable=False)
