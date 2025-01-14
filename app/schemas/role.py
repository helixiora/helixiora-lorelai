"""Role schema."""

from pydantic import BaseModel


class RoleSchema(BaseModel):
    """Schema for a role."""

    id: int
    name: str

    class Config:
        """Config for the role schema."""

        from_attributes = True
