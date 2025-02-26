"""User model."""

from datetime import datetime
from flask_login import UserMixin
from app.database import db

VALID_ROLES = {"super_admin", "org_admin", "user"}


class User(UserMixin, db.Model):
    """Model for a user."""

    __tablename__ = "user"

    # the actual field name is user_id
    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="user_id")
    email = db.Column(db.String(255), unique=True, nullable=False)
    user_name = db.Column(db.String(255), nullable=True)
    full_name = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    profile = db.relationship(
        "Profile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    roles = db.relationship(
        "Role", secondary="user_roles", back_populates="users", cascade="save-update"
    )
    user_plans = db.relationship(
        "UserPlan", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    logins = db.relationship("UserLogin", backref="user", lazy=True, cascade="all, delete-orphan")
    organisation = db.relationship("Organisation", back_populates="users", lazy=True)
    extra_messages = db.relationship(
        "ExtraMessages", back_populates="user", lazy=True, cascade="all, delete-orphan"
    )
    api_keys = db.relationship(
        "UserAPIKey", back_populates="user", lazy=True, cascade="all, delete-orphan"
    )
    indexing_runs = db.relationship(
        "IndexingRun", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        """Return a string representation of the user."""
        return f"<User {self.email}>"

    def has_role(self, role_name):
        """Check if the user has a role."""
        return any(role.name == role_name for role in self.roles)

    def is_admin(self) -> bool:
        """Check if the user is an admin."""
        return self.has_role("org_admin") or self.has_role("super_admin")

    def is_org_admin(self) -> bool:
        """Check if the user is an organization admin."""
        return self.has_role("org_admin")

    def is_super_admin(self) -> bool:
        """Check if the user is a super admin."""
        return self.has_role("super_admin")
