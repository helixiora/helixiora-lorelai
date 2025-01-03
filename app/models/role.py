"""Role models."""

from .database import db
from .user import VALID_ROLES


class UserRole(db.Model):
    """Model for a user role."""

    __tablename__ = "user_roles"

    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), primary_key=True)


class Role(db.Model):
    """Model for a role."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="role_id")
    name = db.Column(db.String(255), unique=True, nullable=False, name="role_name")

    # Relationships
    users = db.relationship("User", secondary="user_roles", back_populates="roles")

    def __repr__(self) -> str:
        """Return a string representation of the role."""
        return f"<Role {self.name}>"

    def has_role(self, role_name: str) -> bool:
        """Check if the role has a role."""
        if not role_name:
            return False
        if not isinstance(role_name, str):
            raise ValueError("Role name must be a string")
        if role_name not in VALID_ROLES:
            raise ValueError(f"Invalid role name: {role_name}")
        return any(role.name == role_name for role in self.users)
