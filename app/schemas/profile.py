"""Profile schema."""

from datetime import date
from pydantic import BaseModel


class ProfileSchema(BaseModel):
    """Schema for a user's profile."""

    id: int
    user_id: int
    bio: str | None
    location: str | None
    birth_date: date | None
    avatar_url: str | None

    class Config:
        """Config for the profile schema."""

        from_attributes = True


class PluginConfigSchema(BaseModel):
    """Schema for a plugin's configuration."""

    name: str
    config: list[dict]
