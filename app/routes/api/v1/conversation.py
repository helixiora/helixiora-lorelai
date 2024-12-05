"""API routes for conversation operations."""

from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
from flask import abort

from app.helpers.chat import delete_conversation, get_all_conversation_messages

conversation_ns = Namespace(
    "conversation", description="Operations related to chat conversations and their messages"
)

# Define response models
message_model = conversation_ns.model(
    "Message",
    {
        "sender": fields.String(required=True, description="Message sender (user or assistant)"),
        "message_content": fields.String(required=True, description="Content of the message"),
        "created_at": fields.DateTime(required=True, description="Timestamp of message creation"),
        "sources": fields.Raw(description="Reference sources used in the message"),
    },
)


# route to delete a conversation and all its messages
@conversation_ns.route("/<conversation_id>/delete")
@conversation_ns.param("conversation_id", "The conversation identifier")
class DeleteConversationResource(Resource):
    """Resource to delete a conversation and all its messages."""

    @conversation_ns.doc(
        security="Bearer Auth",
        responses={
            200: "Conversation successfully deleted",
            404: "Conversation not found",
            401: "Unauthorized access",
        },
    )
    @jwt_required(locations=["headers"])
    def delete(self, conversation_id):
        """Delete a conversation and all its messages."""
        try:
            delete_conversation(conversation_id)
            return {"status": "success", "message": "Conversation deleted"}, 200
        except ValueError as e:
            abort(404, str(e))


# get all messages for a given conversation
@conversation_ns.route("/<conversation_id>")
@conversation_ns.param("conversation_id", "The conversation identifier")
class GetConversationResource(Resource):
    """Resource to get all messages for a given conversation."""

    @conversation_ns.doc(
        security="Bearer Auth",
        responses={
            200: "Messages retrieved successfully",
            404: "Conversation not found",
            401: "Unauthorized access",
        },
    )
    @conversation_ns.marshal_with(message_model, as_list=True)
    @jwt_required(locations=["headers"])
    def get(self, conversation_id):
        """Get all messages for a given conversation."""
        try:
            messages = get_all_conversation_messages(conversation_id)
            return messages, 200
        except ValueError as e:
            abort(404, str(e))
