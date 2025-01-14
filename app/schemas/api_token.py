"""API token schema."""

from datetime import datetime
from pydantic import BaseModel


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
