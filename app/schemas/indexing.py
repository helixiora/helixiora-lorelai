"""Indexing schemas."""

from datetime import datetime
from pydantic import BaseModel
from .user import UserSchema
from .organisation import OrganisationSchema
from .datasource import DatasourceSchema


class IndexingRunItemSchema(BaseModel):
    """Schema for an indexing run item."""

    id: int
    indexing_run_id: int
    item_id: str
    item_type: str
    item_name: str
    item_url: str
    item_status: str
    item_error: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the indexing run item schema."""

        from_attributes = True


class IndexingRunSchema(BaseModel):
    """Schema for an indexing run."""

    id: int
    rq_job_id: str
    created_at: datetime
    updated_at: datetime
    status: str
    user_id: int
    organisation_id: int
    datasource_id: int
    error: str | None = None
    items: list[IndexingRunItemSchema] = []
    user: UserSchema
    organisation: OrganisationSchema
    datasource: DatasourceSchema

    class Config:
        """Config for the indexing run schema."""

        from_attributes = True
