"""Google OAuth2 authentication routes."""

import logging

from flask import Blueprint, redirect, render_template, request, session, url_for
from google_auth_oauthlib.flow import Flow

from app.utils import get_db_connection, load_config, get_datasource_id_by_name

googledrive_bp = Blueprint("googledrive", __name__)


def google_auth_url():
    """Generate the Google OAuth2 authorization URL.

    Returns
    -------
        str: The Google OAuth2 authorization URL.

    """
    # Load the Google OAuth2 secrets
    secrets = load_config("google")
    e_creds = ["client_id", "project_id", "client_secret", "redirect_uris"]
    if not all(i in secrets for i in e_creds):
        missing_creds = ", ".join([ec for ec in e_creds if ec not in secrets])
        msg = "Missing required google credentials: "
        raise ValueError(msg, missing_creds)

    client_config = {
        "web": {
            "client_id": secrets["client_id"],
            "project_id": secrets["project_id"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": secrets["client_secret"],
            "redirect_uris": secrets["redirect_uris"],
        }
    }

    lorelaicreds = load_config("lorelai")

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=lorelaicreds["redirect_uri"],
    )

    try:
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        session["state"] = state
        return authorization_url

    except RuntimeError as e:
        logging.debug(f"Error generating authorization URL: {e}")
        return render_template("error.html", error_message="Failed to generate login URL.")


@googledrive_bp.route("/google/auth/callback", methods=["GET"])
def auth_callback():
    """Handle callback for Google OAuth2 authentication.

    This route is called by Google after the user has authenticated.
    The route verifies the state and exchanges the authorization code for an access token.

    Returns
    -------
        string: The index page.

    """
    lorelaicreds = load_config("lorelai")
    googlecreds = load_config("google")
    # state = request.args.get("state")
    state = session["state"]
    if state != session["state"]:
        return render_template("error.html", error_message="Invalid state parameter.")

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": googlecreds["client_id"],
                "project_id": googlecreds["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": googlecreds["client_secret"],
                "redirect_uris": googlecreds["redirect_uris"],
            }
        },
        # scopes=["https://www.googleapis.com/auth/drive.readonly"],
        scopes=None,
        redirect_uri=lorelaicreds["redirect_uri"],
    )
    flow.fetch_token(authorization_response=request.url)

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
    data_source_name = "Google"
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    datasource_id = get_datasource_id_by_name(cursor, data_source_name)
    if datasource_id is None:
        logging.error(f"{data_source_name} is missing from datasource table in db")
        raise ValueError(f"{data_source_name} is missing from datasource table in db")
    cursor.execute(
        """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, datasource_id, "access_token", access_token, "oauth"),
    )
    cursor.execute(
        """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, datasource_id, "refresh_token", refresh_token, "oauth"),
    )
    cursor.execute(
        """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, datasource_id, "expires_at", expires_at, "oauth"),
    )

    conn.commit()
    session["credentials"] = flow.credentials.to_json()

    return redirect(url_for("auth.profile"))
