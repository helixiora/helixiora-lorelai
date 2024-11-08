"""API routes for conversation operations."""

from flask import jsonify
from flask_restx import Namespace, Resource

from app.helpers.chat import delete_conversation, get_all_conversation_messages

conversation_ns = Namespace("conversation", description="Conversation operations")


# route to delete a conversation and all its messages
@conversation_ns.route("/<conversation_id>/delete")
class DeleteConversationResource(Resource):
    """Resource to delete a conversation and all its messages."""

    def delete(self, conversation_id):
        """Delete a conversation and all its messages."""
        delete_conversation(conversation_id)
        return jsonify({"status": "success"}), 200


# get all messages for a given conversation
@conversation_ns.route("/<conversation_id>")
class GetConversationResource(Resource):
    """Resource to get all messages for a given conversation."""

    def get(self, conversation_id):
        """Get all messages for a given conversation."""
        messages = get_all_conversation_messages(conversation_id)
        return jsonify(messages), 200
