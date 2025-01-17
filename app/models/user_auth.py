"""User auth model."""

from app.database import db


class UserAuth(db.Model):
    """Model for a user auth."""

    __tablename__ = "user_auth"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="user_auth_id")
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    datasource_id = db.Column(db.Integer, db.ForeignKey("datasource.datasource_id"), nullable=False)
    auth_key = db.Column(db.String(255), nullable=False)
    auth_value = db.Column(db.String(255), nullable=False)
    auth_type = db.Column(db.String(255), nullable=False)
