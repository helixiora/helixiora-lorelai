"""API routes for token operations."""

import logging
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_restx import Namespace, Resource

token_ns = Namespace("token", description="Token operations")


@token_ns.route("/refresh")
class TokenRefresh(Resource):
    """Resource for token refresh operations."""

    @token_ns.doc(security="Bearer Auth")
    @token_ns.response(200, "Token refreshed successfully")
    @token_ns.response(401, "Unauthorized")
    @token_ns.response(500, "Internal server error")
    @jwt_required(refresh=True)
    def post(self):
        """
        Refresh the access token.

        Returns
        -------
            str: The new access token.
        """
        try:
            current_user = get_jwt_identity()
            new_access_token = create_access_token(identity=str(current_user))
            if new_access_token:
                logging.info(f"New access token created for user {current_user}")
                return {"access_token": new_access_token}, 200
            else:
                logging.error("Failed to create new access token")
                return {"msg": "Failed to create new access token"}, 500
        except Exception as e:
            logging.error(f"Error refreshing token: {str(e)}")
            return {"msg": "Error refreshing token"}, 500
