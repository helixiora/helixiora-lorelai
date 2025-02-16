"""Helper functions for Google Drive."""

import os

from flask import current_app, jsonify
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import (
    InvalidScopeError,
    InvalidRedirectURIError,
    InvalidRequestError,
    FatalClientError,
    InvalidGrantError,
    OAuth2Error,
)
import logging
import pydantic
from datetime import datetime

from app.database import db
from app.models.user import User
from app.models.user_auth import UserAuth
from app.models.datasource import Datasource
import requests as lib_requests
from flask import session
from flask_login import current_user
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from sqlalchemy.exc import SQLAlchemyError


class TokenDetailsResponse(pydantic.BaseModel):
    """The response from the get_token_details function."""

    access_token: str
    refresh_token: str
    expires_at: datetime


def get_token_details(user_id: int) -> TokenDetailsResponse:
    """Get the token details from the user auths.

    Parameters
    ----------
    user_auths: list[UserAuthSchema]
        The user auths to get the token details from.

    Returns
    -------
    tuple[str, str, str]
        The access token, refresh token, and expires at.
    """
    datasource_id = (
        Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first().datasource_id
    )

    access_token_auth = UserAuth.query.filter_by(
        user_id=user_id, datasource_id=datasource_id, auth_key="access_token"
    ).first()
    refresh_token_auth = UserAuth.query.filter_by(
        user_id=user_id, datasource_id=datasource_id, auth_key="refresh_token"
    ).first()
    expires_at_auth = UserAuth.query.filter_by(
        user_id=user_id, datasource_id=datasource_id, auth_key="expires_at"
    ).first()

    access_token = access_token_auth.auth_value if access_token_auth else None
    refresh_token = refresh_token_auth.auth_value if refresh_token_auth else None
    expires_at = expires_at_auth.auth_value if expires_at_auth else None

    if not access_token or not refresh_token:
        raise ValueError("Missing required Google Drive authentication tokens")

    return TokenDetailsResponse(
        access_token=access_token, refresh_token=refresh_token, expires_at=expires_at
    )


def refresh_google_token_if_needed(access_token):
    """
    Refresh the Google access token if needed.

    Parameters
    ----------
    access_token : str
        The Google access token.

    Returns
    -------
    str
        The refreshed access token or None if refresh failed.
    """
    try:
        datasource_id = (
            Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE)
            .first()
            .datasource_id
        )
        # Check if the token is still valid
        token_info_url = (
            f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
        )
        response = lib_requests.get(token_info_url)
        response_json = response.json()
        logging.info("Token validation response: %s", response_json)

        if response.status_code == 200 and "error" not in response_json:
            logging.info("Access token is still valid")
            return access_token  # Token is still valid
        else:
            logging.warning("Access token is invalid or expired: %s", response_json)

        # If we're still here, the token is invalid or expired, refresh it
        # First try to get refresh token from session
        refresh_token = session.get("google_drive.refresh_token")
        logging.info("Got refresh token from session: %s", bool(refresh_token))

        # If not in session, try to get from database
        if not refresh_token:
            refresh_auth = UserAuth.query.filter_by(
                user_id=current_user.id,
                auth_key="refresh_token",
                datasource_id=datasource_id,
            ).first()

            if not refresh_auth:
                logging.error("No refresh token found for user %s", current_user.id)
                return None
            refresh_token = refresh_auth.auth_value
            logging.info("Got refresh token from database")
            # Store in session for future use
            session["google_drive.refresh_token"] = refresh_token

        logging.info("Attempting to refresh token for user %s", current_user.email)

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": current_app.config["GOOGLE_CLIENT_ID"],
            "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        token_response = lib_requests.post(token_url, data=payload)
        token_data = token_response.json()

        if token_response.status_code != 200:
            error_data = token_data
            error_msg = error_data.get("error", "unknown_error")
            error_description = error_data.get("error_description", "No description provided")
            logging.error("Token refresh failed: %s - %s", error_msg, error_description)

            if error_msg == "invalid_grant":
                logging.error("Invalid grant error. Refresh token may be expired or revoked.")
                # Clear the invalid tokens
                UserAuth.query.filter_by(
                    user_id=current_user.id, datasource_id=datasource_id
                ).delete()
                db.session.commit()
                # Clear session
                session.pop("google_drive.refresh_token", None)
                return None

            logging.error("Failed to refresh token: %s", token_response.text)
            return None

        logging.info("Successfully refreshed token")
        new_access_token = token_data["access_token"]

        # Update the access token in the database
        access_auth = UserAuth.query.filter_by(
            user_id=current_user.id,
            auth_key="access_token",
            datasource_id=datasource_id,
        ).first()

        if access_auth:
            access_auth.auth_value = new_access_token
        else:
            access_auth = UserAuth(
                user_id=current_user.id,
                auth_key="access_token",
                auth_value=new_access_token,
                datasource_id=datasource_id,
            )
            db.session.add(access_auth)

        # Update the refresh token if a new one was provided
        if "refresh_token" in token_data:
            refresh_auth = UserAuth.query.filter_by(
                user_id=current_user.id,
                auth_key="refresh_token",
                datasource_id=datasource_id,
            ).first()

            if refresh_auth:
                refresh_auth.auth_value = token_data["refresh_token"]
            else:
                refresh_auth = UserAuth(
                    user_id=current_user.id,
                    auth_key="refresh_token",
                    auth_value=token_data["refresh_token"],
                    datasource_id=datasource_id,
                )
                db.session.add(refresh_auth)

            # Update session
            session["google_drive.refresh_token"] = token_data["refresh_token"]

        db.session.commit()
        return new_access_token

    except Exception as e:
        logging.error("Error during token refresh: %s", str(e))
        db.session.rollback()
        return None


def initialize_oauth_flow():
    """Initialize the OAuth2 flow using the provided credentials."""
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": current_app.config["GOOGLE_CLIENT_ID"],
                "project_id": current_app.config["GOOGLE_PROJECT_ID"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.file",
        ],
        redirect_uri=current_app.config["LORELAI_REDIRECT_URI"],
    )


def fetch_oauth_tokens(flow, authorization_code):
    """Fetch OAuth tokens using the provided authorization code."""
    flow.fetch_token(code=authorization_code)


def handle_oauth_error(error):
    """Handle OAuth2 related errors and return appropriate responses."""
    error_map = {
        InvalidScopeError: ("Invalid scope error", 400),
        InvalidRedirectURIError: ("Invalid redirect URI error", 400),
        InvalidRequestError: ("Invalid request error", 400),
        FatalClientError: ("Fatal client error", 400),
        InvalidGrantError: ("Invalid grant error", 400),
        OAuth2Error: ("OAuth2 error", 400),
    }
    error_type = type(error)
    error_message, status_code = error_map.get(error_type, ("Generic OAuth2 error", 400))

    logging.error(f"{error_message}: {error}")
    return jsonify({"status": "error", "message": f"{error_message}: {str(error)}"}), status_code


def save_tokens_to_db(flow, user_id):
    """Save tokens in the database after successful OAuth authentication."""
    access_token = flow.credentials.token
    refresh_token = flow.credentials.refresh_token
    expires_at = flow.credentials.expiry

    logging.debug(f"Access token: {access_token}")
    logging.debug(f"Refresh token: {refresh_token}")
    logging.debug(f"Expires at: {expires_at}")

    try:
        datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first()
        if not datasource:
            raise ValueError(f"{DATASOURCE_GOOGLE_DRIVE} is missing from datasource table in db")

        user = User.query.get(user_id)
        if not user:
            raise ValueError(f"User with id {user_id} not found")

        insert_or_update_token(user, datasource, "access_token", access_token)
        insert_or_update_token(user, datasource, "refresh_token", refresh_token)
        insert_or_update_token(user, datasource, "expires_at", expires_at)

        db.session.commit()
        logging.info(f"Tokens saved to database for user id: {user_id}")
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error: {e}")
        return jsonify_error(f"Database error: {str(e)}", 500)

    return jsonify_success(access_token, refresh_token, expires_at)


def insert_or_update_token(user, datasource, key, value):
    """Insert or update a single token in the database."""
    user_auth = UserAuth.query.filter_by(
        user_id=user.id, datasource_id=datasource.datasource_id, auth_key=key
    ).first()

    if user_auth:
        logging.debug(f"Updating {key} for user id: {user.id}, value: {value}")
        user_auth.auth_value = value
    else:
        logging.debug(f"Inserting {key} for user id: {user.id}, value: {value}")
        new_auth = UserAuth(
            user_id=user.id,
            datasource_id=datasource.datasource_id,
            auth_key=key,
            auth_value=value,
            auth_type="oauth",
        )
        db.session.add(new_auth)


def jsonify_error(message, status_code):
    """Help function to return a JSON error response."""
    return jsonify({"status": "error", "message": message}), status_code


def jsonify_success(access_token, refresh_token, expires_at):
    """Help function to return a JSON success response."""
    return jsonify(
        {
            "status": "success",
            "message": "Authorization code exchanged for access_token, refresh_token, and expiry",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
        }
    ), 200
