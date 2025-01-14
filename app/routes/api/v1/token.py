"""API routes for token operations."""

import logging
from flask_jwt_extended import (
    jwt_required,
    get_jwt_identity,
    create_access_token,
    create_refresh_token,
    set_access_cookies,
    set_refresh_cookies,
)
from flask_restx import Namespace, Resource, fields
from pydantic import BaseModel
from typing import Literal
from flask import make_response, request

token_ns = Namespace("token", description="Token operations")


class BaseResponse(BaseModel):
    """Base response model for all API responses."""

    status: Literal["success", "error"]
    message: str


class TokenResponse(BaseResponse):
    """Response model for token operations that include tokens."""

    access_token: str | None = None
    refresh_token: str | None = None


# API models for swagger documentation
base_response = token_ns.model(
    "BaseResponse",
    {
        "status": fields.String(
            required=True, description="Status of the operation", enum=["success", "error"]
        ),
        "message": fields.String(required=True, description="Response message"),
    },
)

token_response = token_ns.inherit(
    "TokenResponse",
    base_response,
    {
        "access_token": fields.String(required=False, description="Access token"),
        "refresh_token": fields.String(required=False, description="Refresh token"),
    },
)


@token_ns.route("/check")
@token_ns.doc("check_token", security="Bearer Auth")
class TokenCheck(Resource):
    """Check if the current token is valid."""

    @token_ns.response(200, "Token is valid", base_response)
    @token_ns.response(401, "Token is invalid or expired", base_response)
    @jwt_required(locations=["headers", "cookies"])
    def get(self):
        """Check if the current token is valid."""
        # If we get here, the token is valid (jwt_required would have returned 401 otherwise)
        return BaseResponse(status="success", message="Token is valid").model_dump(), 200


@token_ns.route("/refresh")
@token_ns.doc("refresh_token", security="Bearer Auth")
class TokenRefresh(Resource):
    """Token refresh endpoint."""

    @token_ns.response(200, "Token refresh successful", token_response)
    @token_ns.response(401, "Token refresh failed", base_response)
    @jwt_required(refresh=True, locations=["headers", "cookies"])
    def post(self):
        """Refresh access token."""
        try:
            # Create new access token
            current_user_id = get_jwt_identity()
            new_access_token = create_access_token(identity=current_user_id)
            new_refresh_token = create_refresh_token(identity=current_user_id)

            # Check if the request came from a browser (has cookie) or API client (has Bearer token)
            auth_header = request.headers.get("Authorization", "").startswith("Bearer ")

            if auth_header:
                # API client - return tokens in JSON response
                return TokenResponse(
                    status="success",
                    message="Token refresh successful",
                    access_token=new_access_token,
                    refresh_token=new_refresh_token,
                ).model_dump(), 200
            else:
                # Browser client - set tokens in cookies
                response = make_response(
                    BaseResponse(status="success", message="Token refresh successful").model_dump()
                )
                # Use Flask-JWT-Extended's built-in cookie setters
                set_access_cookies(response, new_access_token)
                set_refresh_cookies(response, new_refresh_token)
                return response

        except Exception as e:
            logging.error(f"Failed to refresh token: {e}")
            return BaseResponse(status="error", message="Failed to refresh token").model_dump(), 401
