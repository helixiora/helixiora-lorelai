"""Models for the app."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy.dialects.mysql import INTEGER

db = SQLAlchemy()


# Association table for User and Role
class UserRole(db.Model):
    """Model for a user role."""

    __tablename__ = "user_roles"

    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), primary_key=True)


class ChatMessage(db.Model):
    """Model for the chat_messages table."""

    __tablename__ = "chat_messages"

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(
        db.String(50), db.ForeignKey("chat_conversations.conversation_id"), nullable=False
    )
    sender = db.Column(db.Enum("bot", "user"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    sources = db.Column(db.JSON, nullable=True)

    # Relationship to the chat conversation
    conversation = db.relationship(
        "ChatConversation", back_populates="messages", foreign_keys=[conversation_id]
    )


class ChatConversation(db.Model):
    """Model for the chat_conversations table."""

    __tablename__ = "chat_conversations"

    conversation_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    conversation_name = db.Column(db.String(255), nullable=True)
    marked_deleted = db.Column(db.Integer, default=0)

    # Relationship to messages
    messages = db.relationship(
        "ChatMessage",
        back_populates="conversation",
        lazy=True,
        foreign_keys=[ChatMessage.conversation_id],
    )


class Datasource(db.Model):
    """Model for a datasource."""

    __tablename__ = "datasource"

    datasource_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, name="datasource_id"
    )
    name = db.Column(db.String(255), nullable=False, name="datasource_name", unique=True)
    type = db.Column(db.String(255), nullable=False, name="datasource_type")


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


class Organisation(db.Model):
    """Model for an organisation."""

    __tablename__ = "organisation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    users = db.relationship("User", back_populates="organisation", lazy=True)

    def __repr__(self):
        """Return a string representation of the organisation."""
        return f"<Organisation {self.name}>"


class Plan(db.Model):
    """Model for a plan."""

    __tablename__ = "plans"

    plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plan_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    duration_months = db.Column(INTEGER(unsigned=True), nullable=False)
    message_limit_daily = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_plans = db.relationship("UserPlan", backref="plan", lazy=True)


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

    user = db.relationship("User", back_populates="profile")

    def __repr__(self):
        """Return a string representation of the profile."""
        return f"<Profile of {self.user.email}>"


class Role(db.Model):
    """Model for a role."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="role_id")
    name = db.Column(db.String(255), unique=True, nullable=False, name="role_name")

    users = db.relationship("User", secondary="user_roles", back_populates="roles")

    def __repr__(self):
        """Return a string representation of the role."""
        return f"<Role {self.name}>"


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

    profile = db.relationship("Profile", back_populates="user", uselist=False)
    roles = db.relationship("Role", secondary="user_roles", back_populates="users")
    # api_tokens = db.relationship("APIToken", backref="owner", lazy=True)
    user_plans = db.relationship("UserPlan", backref="user", lazy=True)
    logins = db.relationship("UserLogin", backref="user", lazy=True)

    organisation = db.relationship("Organisation", back_populates="users", lazy=True)
    # Relationship to extra messages
    extra_messages = db.relationship("ExtraMessages", back_populates="user", lazy=True)

    def __repr__(self):
        """Return a string representation of the user."""
        return f"<User {self.email}>"

    def has_role(self, role_name):
        """Check if the user has a role."""
        return any(role.name == role_name for role in self.roles)

    def is_admin(self) -> bool:
        """Check if the user is an admin."""
        return self.has_role("org_admin") or self.has_role("super_admin")


class UserAuth(db.Model):
    """Model for a user auth."""

    __tablename__ = "user_auth"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, name="user_auth_id")
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    datasource_id = db.Column(db.Integer, db.ForeignKey("datasource.datasource_id"), nullable=False)
    auth_key = db.Column(db.String(255), nullable=False)
    auth_value = db.Column(db.String(255), nullable=False)
    auth_type = db.Column(db.String(255), nullable=False)


class UserLogin(db.Model):
    """Model for a user login."""

    __tablename__ = "user_login"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    login_time = db.Column(db.DateTime, nullable=False)
    login_type = db.Column(db.String(255), nullable=False)


class UserPlan(db.Model):
    """Model for a user plan."""

    __tablename__ = "user_plans"

    user_plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.plan_id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Fixing the index creation
    __table_args__ = (
        db.Index("idx_user_plans_plan_id", "plan_id"),
        db.Index("idx_user_plans_user_id", "user_id"),
    )


class Notification(db.Model):
    """Model for a notification."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    type = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(255), nullable=True)
    read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    dismissed = db.Column(db.Boolean, default=False)
    dismissed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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

    # Relationship to User (optional)
    user = db.relationship("User", back_populates="extra_messages")

    def __repr__(self):
        """Return a string representation of the extra message entry."""
        return f"<ExtraMessages user_id={self.user_id}, quantity={self.quantity}, is_active={self.is_active}>"  # noqa: E501
