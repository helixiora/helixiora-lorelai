"""User login schema."""

from datetime import datetime
from pydantic import BaseModel


class UserLoginSchema(BaseModel):
    """Schema for a user login."""

    id: int
    user_id: int
    login_time: datetime
    login_type: str

    class Config:
        """Config for the user login schema."""

        from_attributes = True
