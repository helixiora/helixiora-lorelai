"""User auth schema."""

from pydantic import BaseModel


class UserAuthSchema(BaseModel):
    """Schema for a user auth."""

    id: int
    user_id: int
    datasource_id: int
    auth_key: str
    auth_value: str
    auth_type: str

    class Config:
        """Config for the user auth schema."""

        from_attributes = True
