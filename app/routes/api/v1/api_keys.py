"""API endpoints for API keys."""

from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required
from app.models import db
from app.models.user_api_key import UserAPIKey
import logging

api_keys_ns = Namespace("api_keys", description="API keys operations")


@api_keys_ns.route("/<int:api_key_id>")
class APIKeys(Resource):
    """API endpoints for API keys."""

    @api_keys_ns.doc(security="Bearer Auth")
    @api_keys_ns.response(200, "API key deleted successfully")
    @api_keys_ns.response(404, "API key not found")
    @api_keys_ns.response(500, "Error deleting API key")
    @jwt_required(locations=["headers"])
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
