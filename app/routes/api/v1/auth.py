"""Auth routes for the Lorelai API."""

from flask import request
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import create_access_token, jwt_required
import bleach
import logging
import re
import secrets

from app.models import User


auth_ns = Namespace("auth", description="Authentication operations")

# Define request/response models for Swagger documentation
login_model = auth_ns.model(
    "Login",
    {
        "email": fields.String(required=True, description="User email address"),
        "apikey": fields.String(required=True, description="API Key"),
    },
)

token_model = auth_ns.model(
    "Token",
    {
        "access_token": fields.String(description="JWT access token"),
        "message": fields.String(description="Success message"),
    },
)

error_model = auth_ns.model("Error", {"message": fields.String(description="Error message")})


def validate_email(raw_email: str) -> str:
    """Validate and sanitize email input.

    Args:
        raw_email: User provided email

    Returns
    -------
        Cleaned email string

    Raises
    ------
        ValueError: If email is invalid
    """
    if not raw_email:
        raise ValueError("Email is required")

    # Sanitize input
    clean_email = bleach.clean(raw_email.lower(), tags=[], strip=True)

    # Basic email format validation
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, clean_email):
        raise ValueError("Invalid email format")

    return clean_email


def validate_api_key(raw_key: str) -> str:
    """Validate and sanitize API key input.

    Args:
        raw_key: User provided API key

    Returns
    -------
        Cleaned API key string

    Raises
    ------
        ValueError: If API key is invalid
    """
    if not raw_key:
        raise ValueError("API key is required")

    # Sanitize input
    clean_key = bleach.clean(raw_key, tags=[], strip=True)

    # Validate key format (adjust pattern based on your API key format)
    if not re.match(r"^[a-zA-Z0-9_-]{32,}$", clean_key):
        raise ValueError("Invalid API key format")

    return clean_key


@auth_ns.route("/login")
class LoginResource(Resource):
    """Resource for user login."""

    @auth_ns.expect(login_model)
    @auth_ns.response(200, "Success", token_model)
    @auth_ns.response(401, "Authentication failed", error_model)
    def post(self) -> tuple[dict[str, str], int]:
        """Login a user and return JWT token.

        Returns
        -------
            tuple: Contains response dictionary and HTTP status code
            - On success: {'access_token': 'token', 'message': 'success'}, 200
            - On failure: {'message': 'error details'}, 401

        Raises
        ------
            AuthenticationError: If login credentials are invalid
        """
        try:
            data = request.get_json()

            try:
                email = validate_email(data.get("email"))
                api_key = validate_api_key(data.get("apikey"))
            except ValueError as e:
                logging.warning(f"Login validation failed: {str(e)}")
                return {"message": str(e)}, 401

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
            access_token = create_access_token(identity=user.id)
            logging.info(f"Successful login for user: {email}")

            return {"access_token": access_token, "message": "Login successful"}, 200

        except PermissionError as e:
            return {"message": str(e)}, 401
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            return {"message": "An unexpected error occurred"}, 500


@auth_ns.route("/logout")
class LogoutResource(Resource):
    """Resource for user logout."""

    @jwt_required()
    @auth_ns.response(200, "Success")
    @auth_ns.response(401, "Invalid token")
    def post(self) -> tuple[dict[str, str], int]:
        """Logout a user.

        Requires a valid JWT token in the Authorization header.

        Returns
        -------
            tuple: Contains response dictionary and HTTP status code
            - On success: {'message': 'success'}, 200
            - On failure: {'message': 'error details'}, 401
        """
        try:
            # Note: You might want to add token to a blacklist here
            # if you implement token invalidation
            return {"message": "Logout successful"}, 200

        except Exception as e:
            return {"message": f"An unexpected error occurred: {e}"}, 500
