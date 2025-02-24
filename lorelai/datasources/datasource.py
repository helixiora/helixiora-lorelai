"""Base class for all datasources."""

from abc import ABC, abstractmethod
from datetime import datetime
from langchain_core.documents import Document
from pydantic import BaseModel, Field


class BaseMetadata(BaseModel):
    """Base metadata that all datasources must provide."""

    source: str = Field(description="URL or unique identifier for the source", exclude=False)
    title: str = Field(description="Title or name of the document", exclude=False)
    created_at: datetime = Field(description="When the document was created", exclude=False)
    updated_at: datetime = Field(description="When the document was last updated", exclude=False)
    author: str = Field(description="Author of the document", exclude=False)
    type: str = Field(
        description="Type of document (e.g., 'github_issue', 'slack_message')", exclude=False
    )

    # Make extra field store any additional fields not in the base schema
    model_config = {"extra": "allow"}


class DatasourceBase(ABC):
    """A base class for all datasources."""

    @abstractmethod
    def fetch_data(self) -> list[Document]:
        """Fetch data from the datasource and return as Langchain documents."""
        pass
