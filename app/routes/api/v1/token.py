"""API routes for token operations."""

from flask import jsonify, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from flask_restx import Namespace, Resource

token_ns = Namespace("token", description="Token operations")


@token_ns.route("/refresh")
class TokenRefresh(Resource):
    """Resource for token refresh operations."""

    @jwt_required(refresh=True)
    def post(self):
        """
        Refresh the access token.

        Returns
        -------
            str: The new access token.
        """
        current_user = get_jwt_identity()
        new_access_token = create_access_token(identity=current_user)
        response = make_response(jsonify(access_token=new_access_token), 200)
        response.set_cookie(
            key="access_token_cookie",
            value=new_access_token,
            httponly=True,
            secure=True,
            samesite="Strict",
        )
        return response
