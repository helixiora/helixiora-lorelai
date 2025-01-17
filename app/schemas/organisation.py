"""Organisation schema."""

from pydantic import BaseModel


class OrganisationSchema(BaseModel):
    """Schema for an organisation."""

    id: int
    name: str

    class Config:
        """Config for the organisation schema."""

        from_attributes = True
