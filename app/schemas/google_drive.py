"""Google Drive item schema."""

from datetime import datetime
from pydantic import BaseModel


class GoogleDriveItemSchema(BaseModel):
    """Schema for a Google Drive item."""

    id: int
    user_id: int
    google_drive_id: str
    item_name: str
    item_type: str
    mime_type: str
    item_url: str
    icon_url: str
    created_at: datetime
    last_indexed_at: datetime | None

    class Config:
        """Config for the Google Drive item schema."""

        from_attributes = True
