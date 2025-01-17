"""Notification schema."""

from datetime import datetime
from pydantic import BaseModel


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
