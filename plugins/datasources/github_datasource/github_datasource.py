"""
A plugin to fetch issues from a GitHub repository.

It uses the GitHub API to fetch the issues and return them as Langchain documents.


"""

import requests
from datetime import datetime
from langchain_core.documents import Document
from pydantic import Field, BaseModel
from lorelai.datasources.datasource import DatasourceBase, BaseMetadata


class GitHubConfig(BaseModel):
    """Configuration for GitHub datasource."""

    repository: str = Field(description="The GitHub repository in owner/repo format")
    access_token: str | None = Field(
        default=None, description="GitHub access token for private repositories"
    )


class GitHubMetadata(BaseMetadata):
    """GitHub-specific metadata model."""

    # GitHub-specific fields
    number: int = Field(description="Issue number", exclude=False)
    state: str = Field(description="State of the issue (open/closed)", exclude=False)
    labels: list[str] = Field(description="List of issue labels", exclude=False)
    repository: str = Field(description="Repository name in owner/repo format", exclude=False)

    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "examples": [
                {
                    "source": "https://github.com/owner/repo/issues/1",
                    "title": "Example Issue",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z",
                    "author": "username",
                    "type": "github_issue",
                    "number": 1,
                    "state": "open",
                    "labels": ["bug", "help wanted"],
                    "repository": "owner/repo",
                }
            ]
        },
    }


class GitHubDatasource(DatasourceBase):
    """Datasource for GitHub repositories."""

    def __init__(self, config: dict):
        self.config = GitHubConfig(**config)

    def fetch_data(self) -> list[Document]:
        """Fetch issues from the GitHub repository and return as Langchain documents."""
        headers = {}
        if self.config.access_token:
            headers["Authorization"] = f"token {self.config.access_token}"
        url = f"https://api.github.com/repos/{self.config.repository}/issues"
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            issues = response.json()
            return [
                Document(
                    page_content=issue["body"] or "",
                    metadata=GitHubMetadata(
                        source=issue["html_url"],
                        title=issue["title"],
                        created_at=datetime.fromisoformat(
                            issue["created_at"].replace("Z", "+00:00")
                        ),
                        updated_at=datetime.fromisoformat(
                            issue["updated_at"].replace("Z", "+00:00")
                        ),
                        author=issue["user"]["login"],
                        type="github_issue",
                        number=issue["number"],
                        state=issue["state"],
                        labels=[label["name"] for label in issue["labels"]],
                        repository=self.config.repository,
                    ).model_dump(),
                )
                for issue in issues
            ]
        else:
            response.raise_for_status()

    @classmethod
    def get_metadata_fields(cls) -> dict:
        """Return a dictionary of GitHub-specific metadata fields."""
        return {
            "number": {"type": "integer", "description": "Issue number"},
            "state": {"type": "string", "description": "State of the issue (open/closed)"},
            "labels": {"type": "array", "description": "List of issue labels"},
            "repository": {"type": "string", "description": "Repository name in owner/repo format"},
        }
