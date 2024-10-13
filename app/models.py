"""Models for the app."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
import secrets

db = SQLAlchemy()

# Association table for User and Role
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    """Model for a user."""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    user_name = db.Column(db.String(255), nullable=True)
    full_name = db.Column(db.String(255), nullable=True)
    google_id = db.Column(db.String(255), unique=True, nullable=True)
    org_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    slack_token = db.Column(db.String(255), nullable=True)

    profile = db.relationship("Profile", back_populates="user", uselist=False)
    roles = db.relationship("Role", secondary=user_roles, back_populates="users")
    api_tokens = db.relationship("APIToken", backref="owner", lazy=True)
    user_plans = db.relationship("UserPlan", backref="user", lazy=True)
    logins = db.relationship("UserLogin", backref="user", lazy=True)

    def __repr__(self):
        """Return a string representation of the user."""
        return f"<User {self.email}>"

    def has_role(self, role_name):
        """Check if the user has a role."""
        return any(role.name == role_name for role in self.roles)


class Role(db.Model):
    """Model for a role."""

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    users = db.relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self):
        """Return a string representation of the role."""
        return f"<Role {self.name}>"


class Organisation(db.Model):
    """Model for an organisation."""

    __tablename__ = "organisation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    users = db.relationship("User", backref="organisation", lazy=True)

    def __repr__(self):
        """Return a string representation of the organisation."""
        return f"<Organisation {self.name}>"


class Profile(db.Model):
    """Model for a profile."""

    __tablename__ = "profile"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(255), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", back_populates="profile")

    def __repr__(self):
        """Return a string representation of the profile."""
        return f"<Profile of {self.user.email}>"


class APIToken(db.Model):
    """Model for an API token."""

    __tablename__ = "api_token"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, user, name, expires_in_days=30):
        """Initialize an API token."""
        self.user = user
        self.name = name
        self.token = secrets.token_urlsafe(32)
        self.expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    def is_valid(self):
        """Check if the API token is valid."""
        return datetime.utcnow() < self.expires_at

    def __repr__(self):
        """Return a string representation of the API token."""
        return f"<APIToken {self.name}>"


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


class UserPlan(db.Model):
    """Model for a user plan."""

    __tablename__ = "user_plans"

    user_plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
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
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
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


class ChatThread(db.Model):
    """Model for a chat thread."""

    __tablename__ = "chat_threads"

    thread_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    thread_name = db.Column(db.String(255), nullable=True)
    marked_deleted = db.Column(db.Boolean, default=False)

    messages = db.relationship("ChatMessage", backref="chat_thread", lazy=True)


class ChatMessage(db.Model):
    """Model for a chat message."""

    __tablename__ = "chat_messages"

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    thread_id = db.Column(db.String(50), db.ForeignKey("chat_threads.thread_id"), nullable=False)
    sender = db.Column(db.Enum("bot", "user"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sources = db.Column(db.JSON, nullable=True)
