"""Authentication helper functions."""

import bleach
import logging
from datetime import datetime
from flask import session
from flask_login import login_user
from google.auth import exceptions
import re
from pydantic import BaseModel, ConfigDict

from app.models import db
from app.models.user import User
from app.models.user_login import UserLogin
from app.schemas import UserSchema
from flask_jwt_extended import create_access_token, create_refresh_token
from app.helpers.users import assign_free_plan_if_no_active


class LoginInput(BaseModel):
    """Input model for login function."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user: User
    user_email: str
    google_id: str
    username: str
    full_name: str


class LoginResponse(BaseModel):
    """Response model for login function."""

    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    error_message: str | None = None


def login_user_function(
    user: User,
    user_email: str,
    google_id: str,
    username: str,
    full_name: str,
) -> LoginResponse:
    """
    Create a session for the user, update the user's Google ID in the database.

    Also create access and refresh tokens.

    Parameters
    ----------
    user : User
        The user.
    user_email : str
        The user email.
    google_id : str
        The Google ID, uniquely identifies the user with Google.
    username : str
        The username.
    full_name : str
        The full name.

    Returns
    -------
    LoginResponse
        A Pydantic model containing:
        - success: True if login was successful, False otherwise
        - access_token: The access token if successful, None otherwise
        - refresh_token: The refresh token if successful, None otherwise
        - error_message: Error message if login failed, None otherwise
    """
    try:
        # Validate input using Pydantic
        login_input = LoginInput(
            user=user,
            user_email=user_email,
            google_id=google_id,
            username=username,
            full_name=full_name,
        )

        # Ensure all details are provided
        if not all(
            [
                login_input.user,
                login_input.user_email,
                login_input.google_id,
                login_input.username,
                login_input.full_name,
                login_input.user.organisation.id,
                login_input.user.organisation.name,
            ]
        ):
            logging.error("Missing user or organisation details")
            return LoginResponse(
                success=False, error_message="Missing user or organisation details"
            )

        try:
            user.google_id = login_input.google_id
            user.user_name = login_input.username
            user.full_name = login_input.full_name
            db.session.commit()

            # Create access and refresh tokens
            # duration is determined by the JWT_ACCESS_TOKEN_EXPIRES and JWT_REFRESH_TOKEN_EXPIRES
            access_token = create_access_token(identity=str(user.id))
            refresh_token = create_refresh_token(identity=str(user.id))

            # login_type, it is not necessary now but in future when we add multiple login method
            user_login = UserLogin(
                user_id=user.id, login_type="google-oauth", login_time=datetime.utcnow()
            )
            db.session.add(user_login)
            db.session.commit()

            # login_user is a Flask-Login function that sets the current user to the user object
            login_user(user)

            # store the user's roles in the session
            session["user.user_roles"] = [role.name for role in user.roles]
            session["user.org_name"] = user.organisation.name
            user_schema = UserSchema.model_validate(user).model_dump()

            # assign a free plan if the user has no active plan
            assign_free_plan_if_no_active(user_id=user.id)

            for key, value in user_schema.items():
                logging.debug(f"user.{key} : {value}")
                session[f"user.{key}"] = value

            return LoginResponse(
                success=True, access_token=access_token, refresh_token=refresh_token
            )

        except Exception as e:
            logging.error(f"Error during login: {e}")
            return LoginResponse(success=False, error_message=str(e))

    except Exception as e:
        logging.error(f"Error validating login input: {e}")
        return LoginResponse(success=False, error_message=f"Invalid login input: {str(e)}")


def is_username_available(username: str) -> bool:
    """
    Check if the username is available.

    Parameters
    ----------
    username : str
        The username to check.

    Returns
    -------
    bool
        True if the username is available, False otherwise.
    """
    # reserved names
    reserved_names = [
        "admin",
        "administrator",
        "support",
        "service",
        "api",
        "lorelai",
        "system",
        "bot",
        "user",
        "guest",
        "guestuser",
        "test",
    ]
    if username in reserved_names:
        return False

    # check if the username is already taken
    user = User.query.filter_by(user_name=username).first()

    if user:
        return False
    return True


def validate_id_token(idinfo: dict):
    """
    Validate the ID token.

    Parameters
    ----------
    idinfo : dict
        The ID token information.

    Raises
    ------
    ValueError
        If the issuer is wrong or the email is not verified.
    """
    # TODO: Add more checks here, see
    # https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

    if not idinfo.get("email_verified"):
        raise exceptions.GoogleAuthError("Email not verified")


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
