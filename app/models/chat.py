"""Chat models."""

from datetime import datetime
from . import db


class ChatMessage(db.Model):
    """Model for the chat_messages table."""

    __tablename__ = "chat_messages"

    message_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conversation_id = db.Column(
        db.String(50),
        db.ForeignKey("chat_conversations.conversation_id"),
        nullable=False,
    )
    sender = db.Column(db.Enum("bot", "user"), nullable=False)
    message_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    sources = db.Column(db.JSON, nullable=True)
    marked_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    conversation = db.relationship(
        "ChatConversation", back_populates="messages", foreign_keys=[conversation_id]
    )


class ChatConversation(db.Model):
    """Model for the chat_conversations table."""

    __tablename__ = "chat_conversations"

    conversation_id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    conversation_name = db.Column(db.String(255), nullable=True)
    marked_deleted = db.Column(db.Boolean, default=False)

    # Relationships
    messages = db.relationship(
        "ChatMessage",
        back_populates="conversation",
        lazy=True,
        foreign_keys=[ChatMessage.conversation_id],
    )
