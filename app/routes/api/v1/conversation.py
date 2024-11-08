"""API routes for conversation operations."""

from flask import jsonify
from flask_restx import Namespace, Resource

from app.helpers.chat import delete_thread, get_all_thread_messages

conversation_ns = Namespace("conversation", description="Conversation operations")


# route to delete a thread and all its messages
@conversation_ns.route("/<thread_id>/delete")
class DeleteConversationResource(Resource):
    """Resource to delete a thread and all its messages."""

    def delete(self, thread_id):
        """Delete a thread and all its messages."""
        delete_thread(thread_id)
        return jsonify({"status": "success"}), 200


# get all messages for a given thread
@conversation_ns.route("/<thread_id>")
class GetConversationResource(Resource):
    """Resource to get all messages for a given thread."""

    def get(self, thread_id):
        """Get all messages for a given thread."""
        messages = get_all_thread_messages(thread_id)
        return jsonify(messages), 200
