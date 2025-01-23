"""API endpoints for API keys."""

from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_current_user
from app.models import db
from app.models.user_api_key import UserAPIKey
import logging
from datetime import datetime
import secrets

api_keys_ns = Namespace("api_keys", description="API keys operations")

# Request/Response Models
api_key_create_request = api_keys_ns.model(
    "APIKeyCreateRequest",
    {
        "expires_at": fields.Date(
            required=False, description="Expiry date for the API key (optional)"
        )
    },
)

api_key_response = api_keys_ns.model(
    "APIKeyResponse",
    {
        "id": fields.Integer(description="API key ID"),
        "api_key": fields.String(description="The API key"),
        "expires_at": fields.Date(description="Expiry date for the API key"),
    },
)


def generate_api_key() -> str:
    """Generate a random API key."""
    return secrets.token_hex(16)


@api_keys_ns.route("")
class APIKeysList(Resource):
    """API endpoints for API keys list operations."""

    @api_keys_ns.doc(security="Bearer Auth")
    @api_keys_ns.expect(api_key_create_request)
    @api_keys_ns.response(201, "API key created successfully", api_key_response)
    @api_keys_ns.response(400, "Invalid request")
    @api_keys_ns.response(500, "Error creating API key")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Create a new API key.

        Returns
        -------
            dict: The created API key details
        """
        try:
            current_user = get_current_user()
            if not current_user:
                return {"message": "User not found"}, 404

            data = api_keys_ns.payload or {}
            expires_at = data.get("expires_at")

            # Validate expiry date if provided
            if expires_at:
                if isinstance(expires_at, str):
                    try:
                        expires_at = datetime.strptime(expires_at, "%Y-%m-%d").date()
                    except ValueError:
                        return {"message": "Invalid expiry date format. Please use YYYY-MM-DD"}, 400

                if expires_at <= datetime.now().date():
                    return {"message": "Expiry date must be in the future"}, 400

            # Create new API key
            api_key = UserAPIKey(
                expires_at=expires_at,
                user_id=current_user.id,
                api_key=generate_api_key(),
            )

            db.session.add(api_key)
            db.session.commit()

            logging.info(f"API key created successfully for user {current_user.id}")
            return {
                "id": api_key.id,
                "api_key": api_key.api_key,
                "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None,
            }, 201

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating API key: {str(e)}")
            return {"message": "Error creating API key"}, 500


@api_keys_ns.route("/<int:api_key_id>")
class APIKeys(Resource):
    """API endpoints for API keys."""

    @api_keys_ns.doc(security="Bearer Auth")
    @api_keys_ns.response(200, "API key deleted successfully")
    @api_keys_ns.response(404, "API key not found")
    @api_keys_ns.response(500, "Error deleting API key")
    @jwt_required(locations=["headers", "cookies"])
    def delete(self, api_key_id):
        """Delete an API key by ID.

        Args
        ----
            api_key_id (int): The ID of the API key to delete

        Returns
        -------
            dict: Response message and status
        """
        try:
            api_key = UserAPIKey.query.get(api_key_id)
            if not api_key:
                logging.warning(f"Attempted to delete non-existent API key: {api_key_id}")
                return {"message": "API key not found"}, 404

            db.session.delete(api_key)
            db.session.commit()

            logging.info(f"API key {api_key_id} deleted successfully")
            return {"message": "API key deleted successfully"}, 200

        except Exception as e:
            db.session.rollback()
            logging.error(f"Error deleting API key {api_key_id}: {str(e)}")
            return {"message": "Error deleting API key"}, 500
