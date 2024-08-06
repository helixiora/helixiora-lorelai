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

from flask import Blueprint, request, session
from google_auth_oauthlib.flow import Flow

from oauthlib.oauth2.rfc6749.errors import (
    OAuth2Error,
    FatalClientError,
    InvalidRequestFatalError,
    InvalidRequestError,
)

from app.utils import get_db_connection, load_config, get_datasource_id_by_name

googledrive_bp = Blueprint("googledrive", __name__)


@googledrive_bp.route("/store_token", methods=["POST"])
def store_token():
    """Handle callback for Google OAuth2 authentication.

    This route is called by Google after the user has authenticated.
    The route verifies the state and exchanges the authorization code for an access token.

    Returns
    -------
        string: The index page.

    """
    googlecreds = load_config("google")

    data = request.json
    logging.debug(f"Data: {data}")
    authorization_code = data["code"]

    # set the environment variable to relax the token scope, Google has a habot of changing the
    # order of the scopes, raising a Warning
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": googlecreds["client_id"],
                "project_id": googlecreds["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": googlecreds["client_secret"],
                # "redirect_uris": googlecreds["redirect_uris"],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/drive.file"  # noqa
        ],
        redirect_uri="https://127.0.0.1:5000",
    )

    # this can fail in many ways: token expired, fatal client error, invalid request fatal error,
    # invalid request error
    # see an article here:
    # https://blog.timekit.io/google-oauth-invalid-grant-nightmare-and-how-to-fix-it-9f4efaf1da35
    # https://stackoverflow.com/questions/10576386/invalid-grant-trying-to-get-oauth-token-from-google # noqa
    # also see oauthlib.oauth2.rfc6749.errors
    try:
        flow.fetch_token(code=authorization_code)
    except InvalidRequestError as e:
        logging.error(f"Invalid request error: {e}")
        return "Invalid request error: {e}"
    except FatalClientError as e:
        logging.error(f"Fatal client error: {e}")
        return "Fatal client error: {e}"
    except InvalidRequestFatalError as e:
        logging.error(f"Invalid request fatal error: {e}")
        return "Invalid request fatal error: {e}"
    except OAuth2Error as e:
        logging.error(f"Generic OAuth2 error: {e}")
        return "Generic OAuth2 error: {e}"
    except Warning as e:
        logging.warning(f"Warning: {e}")

    # retrieve the user_id from the session
    user_id = session["user_id"]

    # save the access token, refresh token, and expiry in the database
    access_token = flow.credentials.token
    refresh_token = flow.credentials.refresh_token
    expires_at = flow.credentials.expiry

    logging.debug(f"Access token: {access_token}")
    logging.debug(f"Refresh token: {refresh_token}")
    logging.debug(f"Expires at: {expires_at}")
    # store them as records in user_auth
    data_source_name = "Google Drive"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        datasource_id = get_datasource_id_by_name(data_source_name)
        if datasource_id is None:
            logging.error(f"{data_source_name} is missing from datasource table in db")
            raise ValueError(f"{data_source_name} is missing from datasource table in db")
        cursor.execute(
            """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE auth_value = VALUES(auth_value)""",
            (user_id, datasource_id, "access_token", access_token, "oauth"),
        )
        cursor.execute(
            """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE auth_value = VALUES(auth_value)""",
            (user_id, datasource_id, "refresh_token", refresh_token, "oauth"),
        )
        cursor.execute(
            """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE auth_value = VALUES(auth_value)""",
            (user_id, datasource_id, "expires_at", expires_at, "oauth"),
        )

        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {
        "status": "success",
        "message": "Authorization code exchanged for access_token, refresh_token, and expiry",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
    }


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
