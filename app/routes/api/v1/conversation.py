"""API routes for conversation operations."""

from flask_restx import Namespace, Resource
from datetime import datetime

from app.helpers.chat import delete_conversation, get_all_conversation_messages

conversation_ns = Namespace("conversation", description="Conversation operations")


# route to delete a conversation and all its messages
@conversation_ns.route("/<conversation_id>/delete")
class DeleteConversationResource(Resource):
    """Resource to delete a conversation and all its messages."""

    def delete(self, conversation_id):
        """Delete a conversation and all its messages."""
        delete_conversation(conversation_id)
        return {"status": "success"}, 200


# get all messages for a given conversation
@conversation_ns.route("/<conversation_id>")
class GetConversationResource(Resource):
    """Resource to get all messages for a given conversation."""

    def get(self, conversation_id):
        """Get all messages for a given conversation."""
        messages = get_all_conversation_messages(conversation_id)

        # Convert datetime objects to ISO format strings
        serialized_messages = []
        for message in messages:
            serialized_message = {
                "sender": message["sender"],
                "message_content": message["message_content"],
                "created_at": message["created_at"].isoformat()
                if isinstance(message["created_at"], datetime)
                else message["created_at"],
                "sources": message["sources"],
            }
            serialized_messages.append(serialized_message)

        return serialized_messages, 200
