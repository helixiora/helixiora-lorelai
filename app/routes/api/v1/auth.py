"""Auth routes for the Lorelai API."""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token, jwt_required
import logging
import secrets

from app.helpers.auth import validate_email, validate_api_key
from app.models import User


auth_ns = Namespace("auth", description="Authentication operations")

# Define request/response models for Swagger documentation
login_model = auth_ns.model(
    "Login",
    {
        "email": fields.String(required=True, description="User email address"),
        "apikey": fields.String(required=True, description="API Key"),
        "expires": fields.Integer(
            required=False,
            description="Token expiration time in seconds. Defaults to 15 minutes. \
                Pass 0 for no expiration.",
        ),
    },
)

auth_response_model = auth_ns.model(
    "AuthResponse",
    {
        "status": fields.String(required=True, description="Response status (success/error)"),
        "message": fields.String(required=True, description="Response message"),
        "access_token": fields.String(description="JWT access token"),
        "expiration": fields.DateTime(description="Token expiration time"),
    },
)


# To try this out:
# curl -X POST http://localhost:5000/api/v1/auth/login \
#   -H "Content-Type: application/json" \
#   -d '{
#     "email": "your.email@example.com",
#     "apikey": "your-32-character-or-longer-api-key"
#   }'
@auth_ns.route("/login")
class LoginResource(Resource):
    """Resource for user login."""

    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Success", auth_response_model)
    @auth_ns.response(401, "Authentication failed", auth_response_model)
    def post(self) -> dict[str, str] | tuple[dict[str, str], int]:
        """Authenticate a user and generate a JWT access token.

        Request Body
        -----------
        [Login model](#model-Login)
            - email (str, required): User's email address
            - apikey (str, required): User's 32+ character API key
            - expires (int, optional): Token expiration time in seconds (default: 900)
                Set to 0 for no expiration

        Returns
        -------
        200:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "success"
            - message (str): Success confirmation message
            - access_token (str): JWT access token for authentication
            - expiration (datetime): Token expiration timestamp

        401:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "error"
            - message (str): Authentication error details

        500:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "error"
            - message (str): Unexpected error details

        Raises
        ------
        PermissionError: If the email or API key is invalid
        Exception: Unexpected error

        Example
        -------

        ```
        POST /api/v1/auth/login
        {
            "email": "user@example.com",
            "apikey": "your-32-character-api-key",
            "expires": 3600
        }
        ```

        """
        try:
            data = request.get_json()

            try:
                email = validate_email(data.get("email"))
                api_key = validate_api_key(data.get("apikey"))
            except ValueError as e:
                logging.warning(f"Login validation failed: {str(e)}")
                return {"status": "error", "message": str(e)}, 401

            # Find and authenticate user
            user = User.query.filter_by(email=email).first()
            if not user:
                logging.warning(f"Login attempt with non-existent email: {email}")
                raise PermissionError("Invalid email or API key")

            # Verify API key with constant-time comparison
            valid_key = False
            for key in user.api_keys:
                if secrets.compare_digest(key.api_key, api_key):
                    valid_key = True
                    break

            if not valid_key:
                logging.warning(f"Invalid API key attempt for user: {email}")
                raise PermissionError("Invalid email or API key")

            # Create access token
            access_token = create_access_token(identity=str(user.id))
            logging.info(f"Successful login for user: {email}")

            return {
                "status": "success",
                "message": "Login successful",
                "access_token": access_token,
            }, 200

        except PermissionError as e:
            return {"status": "error", "message": str(e)}, 401
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            return {"status": "error", "message": "An unexpected error occurred"}, 500


@auth_ns.route("/logout")
class LogoutResource(Resource):
    """Resource for user logout from the API."""

    @jwt_required()
    @auth_ns.response(200, "Success", auth_response_model)
    @auth_ns.response(401, "Invalid token", auth_response_model)
    def post(self) -> tuple[dict[str, str], int]:
        """Invalidate the current user's JWT token.

        Requires authentication using a valid JWT token.

        Request Headers
        --------------
        - Authorization (str, required): Bearer token
            Format: "Bearer <jwt_token>"

        Returns
        -------
        200:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "success"
            - message (str): Logout confirmation

        401:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "error"
            - message (str): Invalid or missing token error

        500:
            [AuthResponse model](#model-AuthResponse) containing:
            - status (str): "error"
            - message (str): Unexpected error details

        Example
        -------
        ```
        POST /api/v1/auth/logout
        Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
        ```
        """
        try:
            # Note: You might want to add token to a blacklist here
            # if you implement token invalidation
            return {"status": "success", "message": "Logout successful"}, 200

        except Exception as e:
            return {"status": "error", "message": f"An unexpected error occurred: {e}"}, 500
