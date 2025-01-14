"""Chat schemas."""

from datetime import datetime
from pydantic import BaseModel


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
