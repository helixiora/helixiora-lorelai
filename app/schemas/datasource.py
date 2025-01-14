"""Datasource schema."""

from pydantic import BaseModel


class DatasourceSchema(BaseModel):
    """Schema for a datasource."""

    datasource_id: int
    datasource_name: str
    datasource_type: str
    description: str | None = None

    class Config:
        """Config for the datasource schema."""

        from_attributes = True
