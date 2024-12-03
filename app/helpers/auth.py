"""Authentication helper functions."""

import bleach
import logging
from datetime import datetime
from flask import session
from flask_login import login_user
from google.auth import exceptions
import re

from app.models import User, UserLogin
from app.schemas import UserSchema
from app.extensions import db
from app.utils import create_access_token, create_refresh_token
from app.helpers.users import assign_free_plan_if_no_active


def login_user_function(
    user: User,
    user_email: str,
    google_id: str,
    username: str,
    full_name: str,
):
    """
    Create a session for the user, update the user's Google ID in the database.

    also create access and refresh tokens.

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
    bool
        True if login was successful, False otherwise.
    """
    # Ensure all details are provided
    if not all(
        [
            user,
            user_email,
            google_id,
            username,
            full_name,
            user.organisation.id,
            user.organisation.name,
        ]
    ):
        logging.error("Missing user or organisation details")
        return False

    try:
        user.google_id = google_id
        user.user_name = username
        user.full_name = full_name
        db.session.commit()

        # Create access and refresh tokens
        # duration is determined by the JWT_ACCESS_TOKEN_EXPIRES and JWT_REFRESH_TOKEN_EXPIRES
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

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
        # store the access and refresh tokens in the session
        session["lorelai_jwt.access_token"] = access_token
        session["lorelai_jwt.refresh_token"] = refresh_token
        user_schema = UserSchema.model_validate(user).model_dump()
        assign_free_plan_if_no_active(user_id=user.id)
        for key, value in user_schema.items():
            logging.debug(f"user.{key} : {value}")
            session[f"user.{key}"] = value

        return True

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during login: {str(e)}")
        return False


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
