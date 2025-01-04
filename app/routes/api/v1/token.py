"""API routes for token operations."""

import logging
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token,
    create_refresh_token,
)
from flask_restx import Namespace, Resource
from flask import session

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
            dict: New access and refresh tokens.
        """
        try:
            current_user = get_jwt_identity()
            logging.info("[Token Refresh] Refreshing tokens for user %s", current_user)

            new_access_token = create_access_token(identity=str(current_user))
            new_refresh_token = create_refresh_token(identity=str(current_user))

            if new_access_token and new_refresh_token:
                # Update session tokens
                session["lorelai_jwt.access_token"] = new_access_token
                session["lorelai_jwt.refresh_token"] = new_refresh_token
                logging.info(
                    "[Token Refresh] New tokens created and session updated for user %s",
                    current_user,
                )
                return {"access_token": new_access_token, "refresh_token": new_refresh_token}, 200
            else:
                logging.error(
                    "[Token Refresh] Failed to create new tokens for user %s", current_user
                )
                return {"msg": "Failed to create new tokens"}, 500
        except Exception as e:
            logging.error(
                "[Token Refresh] Error refreshing tokens for user %s: %s", current_user, str(e)
            )
            return {"msg": "Error refreshing tokens"}, 500
