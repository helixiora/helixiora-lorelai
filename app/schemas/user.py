"""User schema."""

from datetime import datetime
from pydantic import BaseModel, EmailStr
from .role import RoleSchema


class UserSchema(BaseModel):
    """Schema for a user."""

    id: int
    email: EmailStr
    user_name: str | None
    full_name: str | None
    google_id: str | None
    org_id: int | None
    created_at: datetime
    roles: list[RoleSchema]

    class Config:
        """Config for the user schema."""

        from_attributes = True
