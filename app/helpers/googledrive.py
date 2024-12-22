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

from app.models import db, User, UserAuth, Datasource
import requests as lib_requests
from flask import session
from flask_login import current_user
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from sqlalchemy.exc import SQLAlchemyError


def get_google_drive_access_token() -> str:
    """Get the user's Google access token from the database if it's not in the session."""
    google_drive_access_token = ""
    datasource_id = Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first().datasource_id

    if session.get("google_drive.access_token") is None:
        result = UserAuth.query.filter_by(
            user_id=current_user.id,
            auth_key="access_token",
            datasource_id=datasource_id,
        ).first()

        # if there is no result, the user has not authenticated with Google (yet)
        if result:
            logging.info("Access token found in user_auth for user %s", current_user.id)
            google_drive_access_token = result.auth_value
        else:
            logging.info("No access token found in user_auth for user %s", current_user.id)
            google_drive_access_token = ""
    else:
        logging.info("Access token found in session for user %s", current_user.id)
        google_drive_access_token = session.get("google_drive.access_token")

    if google_drive_access_token:
        # Check if the token is still valid and refresh if necessary
        google_drive_access_token = refresh_google_token_if_needed(google_drive_access_token)

    return google_drive_access_token


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
    datasource_id = Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first().datasource_id
    # Check if the token is still valid
    token_info_url = f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
    response = lib_requests.get(token_info_url)
    if response.status_code == 200 and "error" not in response.json():
        return access_token  # Token is still valid

    # If we're still here, the token is invalid or expired, refresh it
    refresh_token = session.get("google_drive.refresh_token")
    if not refresh_token:
        result = UserAuth.query.filter_by(
            user_id=current_user.id,
            auth_key="refresh_token",
            datasource_id=datasource_id,
        ).first()
        if not result:
            logging.error("No refresh token found for user %s", current_user.id)
            return None
        refresh_token = result.auth_value

    logging.info("Refreshing token for user %s", current_user.email)

    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": current_app.config["GOOGLE_CLIENT_ID"],
        "client_secret": current_app.config["GOOGLE_CLIENT_SECRET"],
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    token_response = lib_requests.post(token_url, data=payload)
    if token_response.status_code != 200:
        error_data = token_response.json()
        if error_data.get("error") == "invalid_grant":
            logging.error("Invalid grant error. Refresh token may be expired or revoked.")
            # Clear the invalid refresh token
            UserAuth.query.filter_by(
                user_id=current_user.id,
                auth_key="refresh_token",
                datasource_id=datasource_id,
            ).delete()
            UserAuth.query.filter_by(
                user_id=current_user.id,
                auth_key="access_token",
                datasource_id=datasource_id,
            ).delete()
            db.session.commit()
            # You may want to redirect the user to re-authenticate here
            return None
        logging.error("Failed to refresh token: %s", token_response.text)
        return None

    new_tokens = token_response.json()
    new_access_token = new_tokens["access_token"]

    # Update the access token in the database
    UserAuth.query.filter_by(
        user_id=current_user.id, auth_key="access_token", datasource_id=datasource_id
    ).update({"auth_value": new_access_token})

    # Update the refresh token if a new one was provided
    if "refresh_token" in new_tokens:
        UserAuth.query.filter_by(
            user_id=current_user.id,
            auth_key="refresh_token",
            datasource_id=datasource_id,
        ).update({"auth_value": new_tokens["refresh_token"]})

    db.session.commit()
    return new_access_token


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
        datasource = Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first()
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
