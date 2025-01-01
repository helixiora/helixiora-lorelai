"""Schemas for the app."""

from datetime import date, datetime
from pydantic import BaseModel, EmailStr


class ProfileSchema(BaseModel):
    """Schema for a user's profile."""

    id: int
    user_id: int
    bio: str | None
    location: str | None
    birth_date: date | None
    avatar_url: str | None

    class Config:
        """Config for the profile schema."""

        from_attributes = True


class RoleSchema(BaseModel):
    """Schema for a role."""

    id: int
    name: str  # Change from role_name to name

    class Config:
        """Config for the role schema."""

        from_attributes = True


class UserSchema(BaseModel):
    """Schema for a user."""

    id: int
    email: EmailStr
    user_name: str | None
    full_name: str | None
    google_id: str | None
    org_id: int | None
    created_at: datetime
    roles: list[RoleSchema]

    class Config:
        """Config for the user schema."""

        from_attributes = True


class APITokenSchema(BaseModel):
    """Schema for an API token."""

    id: int
    user_id: int
    token: str
    name: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None

    class Config:
        """Config for the API token schema."""

        from_attributes = True


class PlanSchema(BaseModel):
    """Schema for a plan."""

    plan_id: int
    plan_name: str
    description: str | None
    message_limit_daily: int | None
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the plan schema."""

        from_attributes = True


class UserPlanSchema(BaseModel):
    """Schema for a user plan."""

    user_plan_id: int
    user_id: int
    plan_id: int
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        """Config for the user plan schema."""

        from_attributes = True


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


class ChatMessageSchema(BaseModel):
    """Schema for a chat message."""

    message_id: int
    conversation_id: str
    sender: str
    message_content: str
    created_at: datetime
    sources: dict | None

    class Config:
        """Config for the chat message schema."""

        from_attributes = True


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


class ChatConversationSchema(BaseModel):
    """Schema for a chat conversation."""

    conversation_id: str
    user_id: int
    created_at: datetime
    conversation_name: str | None
    marked_deleted: bool
    messages: list[ChatMessageSchema] = []

    class Config:
        """Config for the chat conversation schema."""

        from_attributes = True


class OrganisationSchema(BaseModel):
    """Schema for an organisation."""

    id: int
    name: str

    class Config:
        """Config for the organisation schema."""

        from_attributes = True


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


class DatasourceSchema(BaseModel):
    """Schema for a datasource."""

    datasource_id: int
    datasource_name: str
    datasource_type: str
    description: str | None = None

    class Config:
        """Config for the datasource schema."""

        from_attributes = True


class UserLoginSchema(BaseModel):
    """Schema for a user login."""

    id: int
    user_id: int
    login_time: datetime
    login_type: str

    class Config:
        """Config for the user login schema."""

        from_attributes = True


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
