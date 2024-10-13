"""Models for the app."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Association table for User and Role
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.user_id"), primary_key=True),
    db.Column(
        "role_id", db.Integer, db.ForeignKey("roles.role_id"), primary_key=True
    ),  # Ensure this references the correct table
)


class ChatMessage(db.Model):
    """Model for a chat message."""

    __tablename__ = "chat_messages"

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    thread_id = db.Column(db.String(50), db.ForeignKey("chat_threads.thread_id"), nullable=False)
    sender = db.Column(db.Enum("bot", "user"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sources = db.Column(db.JSON, nullable=True)


class ChatThread(db.Model):
    """Model for a chat thread."""

    __tablename__ = "chat_threads"

    thread_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    thread_name = db.Column(db.String(255), nullable=True)
    marked_deleted = db.Column(db.Boolean, default=False)

    messages = db.relationship("ChatMessage", backref="chat_thread", lazy=True)


class Datasource(db.Model):
    """Model for a datasource."""

    __tablename__ = "datasources"

    datasource_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, name="datasource_id"
    )
    name = db.Column(db.String(255), nullable=False, name="datasource_name", unique=True)
    type = db.Column(db.String(255), nullable=False, name="datasource_type")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GoogleDriveItem(db.Model):
    """Model for a Google Drive item."""

    __tablename__ = "google_drive_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    google_drive_id = db.Column(db.String(255), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    item_type = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_indexed_at = db.Column(db.DateTime, nullable=True)


class Organisation(db.Model):
    """Model for an organisation."""

    __tablename__ = "organisation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    users = db.relationship("User", backref="organisation", lazy=True)

    def __repr__(self):
        """Return a string representation of the organisation."""
        return f"<Organisation {self.name}>"


class Plan(db.Model):
    """Model for a plan."""

    __tablename__ = "plans"

    plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plan_name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
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

    users = db.relationship("User", secondary=user_roles, back_populates="roles")

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
    roles = db.relationship("Role", secondary=user_roles, back_populates="users")
    # api_tokens = db.relationship("APIToken", backref="owner", lazy=True)
    user_plans = db.relationship("UserPlan", backref="user", lazy=True)
    logins = db.relationship("UserLogin", backref="user", lazy=True)

    def __repr__(self):
        """Return a string representation of the user."""
        return f"<User {self.email}>"

    def has_role(self, role_name):
        """Check if the user has a role."""
        return any(role.name == role_name for role in self.roles)


class UserLogin(db.Model):
    """Model for a user login."""

    __tablename__ = "user_logins"

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
