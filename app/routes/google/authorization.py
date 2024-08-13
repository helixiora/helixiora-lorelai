"""Google Drive authorization routes.

Google now recommends the Google Identity Services library for scope authorization.


References
----------
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/scopes
- https://developers.google.com/identity/oauth2/web/guides/use-code-model

"""

import logging
import os

from flask import Blueprint, request, session, jsonify, redirect, url_for
from google_auth_oauthlib.flow import Flow

from oauthlib.oauth2.rfc6749.errors import (
    OAuth2Error,
    FatalClientError,
    InvalidGrantError,
    InvalidScopeError,
    InvalidRequestError,
    InvalidRedirectURIError,
)

from app.utils import get_db_connection, load_config, get_datasource_id_by_name

googledrive_bp = Blueprint("googledrive", __name__)


@googledrive_bp.route("/google/drive/codeclientcallback", methods=["GET"])
def google_auth_redirect():
    """Handle callback for Google CodeClient."""
    googlecreds, lorelai_config = load_configurations()
    authorization_code = request.args.get("code")

    error = request.args.get("error")
    error_description = request.args.get("error_description")
    error_uri = request.args.get("error_uri")

    if error:
        return jsonify_error(f"{error}: {error_description} ({error_uri})", 400)

    state = request.args.get("state")
    logging.debug(f"State: {state}")

    if not authorization_code:
        return jsonify_error("Authorization code is missing", 400)

    flow = initialize_oauth_flow(googlecreds, lorelai_config)

    try:
        fetch_oauth_tokens(flow, authorization_code)
    except OAuth2Error as e:
        return handle_oauth_error(e)

    user_id = session.get("user_id")
    if not user_id:
        return jsonify_error("User not logged in or session expired", 401)

    save_tokens_to_db(flow, user_id)

    return redirect(url_for("auth.profile"))


def load_configurations():
    """Load necessary configurations for OAuth and return them."""
    googlecreds = load_config("google")
    lorelai_config = load_config("lorelai")
    return googlecreds, lorelai_config


def initialize_oauth_flow(googlecreds, lorelai_config):
    """Initialize the OAuth2 flow using the provided credentials."""
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": googlecreds["client_id"],
                "project_id": googlecreds["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": googlecreds["client_secret"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.file",
        ],
        redirect_uri=lorelai_config["redirect_uri"],
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

    session["access_token"] = access_token
    session["expires_at"] = expires_at

    logging.debug(f"Access token: {access_token}")
    logging.debug(f"Refresh token: {refresh_token}")
    logging.debug(f"Expires at: {expires_at}")

    try:
        data_source_name = "Google Drive"
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        datasource_id = get_datasource_id_by_name(data_source_name)
        if datasource_id is None:
            raise ValueError(f"{data_source_name} is missing from datasource table in db")

        insert_or_update_token(cursor, user_id, datasource_id, "access_token", access_token)
        insert_or_update_token(cursor, user_id, datasource_id, "refresh_token", refresh_token)
        insert_or_update_token(cursor, user_id, datasource_id, "expires_at", expires_at)

        conn.commit()
    except Exception as e:
        logging.error(f"Database error: {e}")
        return jsonify_error(f"Database error: {str(e)}", 500)
    finally:
        cursor.close()
        conn.close()

    return jsonify_success(access_token, refresh_token, expires_at)


def insert_or_update_token(cursor, user_id, datasource_id, key, value):
    """Insert or update a single token in the database."""
    cursor.execute(
        """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE auth_value = VALUES(auth_value)""",
        (user_id, datasource_id, key, value, "oauth"),
    )


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


@googledrive_bp.route("/google/drive/processfilepicker", methods=["POST"])
def process_file_picker():
    """Process the list of google docs ids returned by the file picker."""
    # retrieve the user_id from the session
    user_id = session["user_id"]

    # request.data is a json list of selected google docs
    documents = request.get_json()

    # validate the content of documents
    if not documents:
        logging.error("No documents selected")
        return "No documents selected"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        for doc in documents:
            logging.debug(f"Processing google doc id: {doc}")
            cursor.execute(
                """INSERT INTO google_drive_items( \
                       user_id, google_drive_id, item_name, mime_type, item_type)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, doc["id"], doc["name"], doc["mimeType"], doc["type"]),
            )
        conn.commit()
    except Exception:
        logging.error(f"Error inserting google doc id: {doc}")
        return "Error inserting google doc id: {doc}"
    finally:
        cursor.close()
        conn.close()

    return "Success"


# /google/drive/removefile
@googledrive_bp.route("/google/drive/removefile", methods=["POST"])
def remove_file():
    """Remove a google drive item from the database."""
    # retrieve the user_id from the session
    user_id = session["user_id"]

    data = request.get_json()
    google_drive_id = data["google_drive_id"]

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """DELETE FROM google_drive_items
               WHERE user_id = %s AND google_drive_id = %s""",
            (user_id, google_drive_id),
        )
        conn.commit()
    except Exception:
        logging.error(f"Error deleting google doc id: {google_drive_id}")
        return "Error deleting google doc id: {google_drive_id}"
    finally:
        cursor.close()
        conn.close()

    return "OK"
