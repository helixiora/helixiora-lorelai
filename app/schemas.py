"""Schemas for the app."""

from datetime import date, datetime
from pydantic import BaseModel, EmailStr, model_validator


class ProfileSchema(BaseModel):
    """Schema for a user's profile."""

    bio: str | None
    location: str | None
    birth_date: date | None
    avatar_url: str | None

    class Config:
        """Config for the profile schema."""

        from_attributes = True


class RoleSchema(BaseModel):
    """Schema for a role."""

    id: int
    name: str

    class Config:
        """Config for the role schema."""

        from_attributes = True


class UserSchema(BaseModel):
    """Schema for a user."""

    id: int
    email: EmailStr
    user_name: str | None
    full_name: str | None
    google_id: str | None
    org_id: int | None
    is_admin: bool
    created_at: datetime
    roles: list[RoleSchema]

    @model_validator(mode="before")
    @classmethod
    def check_admin(cls, user: "UserSchema") -> "UserSchema":
        """Check if the user has admin role."""
        # Use dot notation to access the roles
        roles = user.roles if user.roles else []
        is_admin = any(role.name in ("org_admin", "super_admin") for role in roles)
        user.is_admin = is_admin
        return user

    class Config:
        """Config for the user schema."""

        from_attributes = True


class APITokenSchema(BaseModel):
    """Schema for an API token."""

    id: int
    user_id: int
    token: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None

    class Config:
        """Config for the API token schema."""

        from_attributes = True


class PlanSchema(BaseModel):
    """Schema for a plan."""

    plan_id: int
    plan_name: str
    description: str | None
    message_limit_daily: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the plan schema."""

        from_attributes = True


class UserPlanSchema(BaseModel):
    """Schema for a user plan."""

    user_plan_id: int
    user_id: int
    plan_id: int
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the user plan schema."""

        from_attributes = True


class NotificationSchema(BaseModel):
    """Schema for a notification."""

    id: int
    user_id: int
    type: str
    title: str
    message: str
    data: str | None
    url: str | None
    read: bool
    read_at: datetime | None
    dismissed: bool
    dismissed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the notification schema."""

        from_attributes = True


class ChatMessageSchema(BaseModel):
    """Schema for a chat message."""

    message_id: int
    thread_id: str
    sender: str
    message_content: str
    created_at: datetime
    sources: dict | None

    class Config:
        """Config for the chat message schema."""

        from_attributes = True


class ChatThreadSchema(BaseModel):
    """Schema for a chat thread."""

    thread_id: str
    user_id: int
    created_at: datetime
    thread_name: str | None
    marked_deleted: bool
    messages: list[ChatMessageSchema] = []

    class Config:
        """Config for the chat thread schema."""

        from_attributes = True
