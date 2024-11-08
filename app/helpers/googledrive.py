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
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from sqlalchemy.exc import SQLAlchemyError


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
