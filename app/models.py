"""Models for the app."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db_instance = SQLAlchemy()

# Association table for User and Role
user_roles = db_instance.Table(
    "user_roles",
    db_instance.Column(
        "user_id", db_instance.Integer, db_instance.ForeignKey("user.user_id"), primary_key=True
    ),
    db_instance.Column(
        "role_id", db_instance.Integer, db_instance.ForeignKey("roles.role_id"), primary_key=True
    ),  # Ensure this references the correct table
)


class ChatMessage(db_instance.Model):
    """Model for a chat message."""

    __tablename__ = "chat_messages"

    message_id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    thread_id = db_instance.Column(
        db_instance.String(50), db_instance.ForeignKey("chat_threads.thread_id"), nullable=False
    )
    sender = db_instance.Column(db_instance.Enum("bot", "user"), nullable=False)
    message_content = db_instance.Column(db_instance.Text, nullable=False)
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    sources = db_instance.Column(db_instance.JSON, nullable=True)


class ChatThread(db_instance.Model):
    """Model for a chat thread."""

    __tablename__ = "chat_threads"

    thread_id = db_instance.Column(db_instance.String(50), primary_key=True)
    user_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("user.user_id"), nullable=False
    )
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    thread_name = db_instance.Column(db_instance.String(255), nullable=True)
    marked_deleted = db_instance.Column(db_instance.Boolean, default=False)

    messages = db_instance.relationship("ChatMessage", backref="chat_thread", lazy=True)


class Datasource(db_instance.Model):
    """Model for a datasource."""

    __tablename__ = "datasources"

    datasource_id = db_instance.Column(
        db_instance.Integer, primary_key=True, autoincrement=True, name="datasource_id"
    )
    name = db_instance.Column(
        db_instance.String(255), nullable=False, name="datasource_name", unique=True
    )
    type = db_instance.Column(db_instance.String(255), nullable=False, name="datasource_type")
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)


class GoogleDriveItem(db_instance.Model):
    """Model for a Google Drive item."""

    __tablename__ = "google_drive_items"

    id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    user_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("user.user_id"), nullable=False
    )
    google_drive_id = db_instance.Column(db_instance.String(255), nullable=False)
    item_name = db_instance.Column(db_instance.String(255), nullable=False)
    item_type = db_instance.Column(db_instance.String(255), nullable=False)
    mime_type = db_instance.Column(db_instance.String(255), nullable=False)
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    last_indexed_at = db_instance.Column(db_instance.DateTime, nullable=True)


class Organisation(db_instance.Model):
    """Model for an organisation."""

    __tablename__ = "organisation"

    id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    name = db_instance.Column(db_instance.String(255), unique=True, nullable=False)

    users = db_instance.relationship("User", backref="organisation", lazy=True)

    def __repr__(self):
        """Return a string representation of the organisation."""
        return f"<Organisation {self.name}>"


class Plan(db_instance.Model):
    """Model for a plan."""

    __tablename__ = "plans"

    plan_id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    plan_name = db_instance.Column(db_instance.String(50), nullable=False)
    description = db_instance.Column(db_instance.Text, nullable=True)
    message_limit_daily = db_instance.Column(db_instance.Integer, nullable=True)
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    updated_at = db_instance.Column(
        db_instance.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user_plans = db_instance.relationship("UserPlan", backref="plan", lazy=True)


class Profile(db_instance.Model):
    """Model for a profile."""

    __tablename__ = "user_profile"

    id = db_instance.Column(
        db_instance.Integer, primary_key=True, autoincrement=True, name="profile_id"
    )
    user_id = db_instance.Column(
        db_instance.Integer,
        db_instance.ForeignKey("user.user_id"),
        unique=True,
        nullable=False,
    )
    bio = db_instance.Column(db_instance.Text, nullable=True)
    location = db_instance.Column(db_instance.String(255), nullable=True)
    birth_date = db_instance.Column(db_instance.Date, nullable=True)
    avatar_url = db_instance.Column(db_instance.String(255), nullable=True)

    user = db_instance.relationship("User", back_populates="profile")

    def __repr__(self):
        """Return a string representation of the profile."""
        return f"<Profile of {self.user.email}>"


class Role(db_instance.Model):
    """Model for a role."""

    __tablename__ = "roles"

    id = db_instance.Column(
        db_instance.Integer, primary_key=True, autoincrement=True, name="role_id"
    )
    name = db_instance.Column(
        db_instance.String(255), unique=True, nullable=False, name="role_name"
    )

    users = db_instance.relationship("User", secondary=user_roles, back_populates="roles")

    def __repr__(self):
        """Return a string representation of the role."""
        return f"<Role {self.name}>"


class User(UserMixin, db_instance.Model):
    """Model for a user."""

    __tablename__ = "user"

    # the actual field name is user_id
    id = db_instance.Column(
        db_instance.Integer, primary_key=True, autoincrement=True, name="user_id"
    )
    email = db_instance.Column(db_instance.String(255), unique=True, nullable=False)
    user_name = db_instance.Column(db_instance.String(255), nullable=True)
    full_name = db_instance.Column(db_instance.String(255), nullable=True)
    google_id = db_instance.Column(db_instance.String(255), unique=True, nullable=True)
    org_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("organisation.id"), nullable=True
    )
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)

    profile = db_instance.relationship("Profile", back_populates="user", uselist=False)
    roles = db_instance.relationship("Role", secondary=user_roles, back_populates="users")
    # api_tokens = db_instance.relationship("APIToken", backref="owner", lazy=True)
    user_plans = db_instance.relationship("UserPlan", backref="user", lazy=True)
    logins = db_instance.relationship("UserLogin", backref="user", lazy=True)

    def __repr__(self):
        """Return a string representation of the user."""
        return f"<User {self.email}>"

    def has_role(self, role_name):
        """Check if the user has a role."""
        return any(role.name == role_name for role in self.roles)


class UserLogin(db_instance.Model):
    """Model for a user login."""

    __tablename__ = "user_logins"

    id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    user_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("user.user_id"), nullable=False
    )
    login_time = db_instance.Column(db_instance.DateTime, nullable=False)
    login_type = db_instance.Column(db_instance.String(255), nullable=False)


class UserPlan(db_instance.Model):
    """Model for a user plan."""

    __tablename__ = "user_plans"

    user_plan_id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    user_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("user.user_id"), nullable=False
    )
    plan_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("plans.plan_id"), nullable=False
    )
    start_date = db_instance.Column(db_instance.Date, nullable=False)
    end_date = db_instance.Column(db_instance.Date, nullable=False)
    is_active = db_instance.Column(db_instance.Boolean, default=True)
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    updated_at = db_instance.Column(
        db_instance.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Notification(db_instance.Model):
    """Model for a notification."""

    __tablename__ = "notifications"

    id = db_instance.Column(db_instance.Integer, primary_key=True, autoincrement=True)
    user_id = db_instance.Column(
        db_instance.Integer, db_instance.ForeignKey("user.user_id"), nullable=False
    )
    type = db_instance.Column(db_instance.String(255), nullable=False)
    title = db_instance.Column(db_instance.String(255), nullable=False)
    message = db_instance.Column(db_instance.Text, nullable=False)
    data = db_instance.Column(db_instance.Text, nullable=True)
    url = db_instance.Column(db_instance.String(255), nullable=True)
    read = db_instance.Column(db_instance.Boolean, default=False)
    read_at = db_instance.Column(db_instance.DateTime, nullable=True)
    dismissed = db_instance.Column(db_instance.Boolean, default=False)
    dismissed_at = db_instance.Column(db_instance.DateTime, nullable=True)
    created_at = db_instance.Column(db_instance.DateTime, default=datetime.utcnow)
    updated_at = db_instance.Column(
        db_instance.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
