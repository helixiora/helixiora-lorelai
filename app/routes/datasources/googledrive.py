"""Google Drive authorization routes.

Google now recommends the Google Identity Services library for scope authorization.


References
----------
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/scopes
- https://developers.google.com/identity/oauth2/web/guides/use-code-model

"""

import logging

from flask import Blueprint, request, session, jsonify, redirect, url_for, flash

from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from app.helpers.googledrive import (
    initialize_oauth_flow,
    fetch_oauth_tokens,
    save_tokens_to_db,
    jsonify_error,
)
from app.models import db, UserAuth, Datasource, GoogleDriveItem
from sqlalchemy.exc import SQLAlchemyError


googledrive_bp = Blueprint("googledrive", __name__)


@googledrive_bp.route("/google/drive/codeclientcallback", methods=["GET"])
def google_auth_redirect():
    """Handle callback for Google CodeClient."""
    authorization_code = request.args.get("code")

    error = request.args.get("error")
    error_description = request.args.get("error_description")
    error_uri = request.args.get("error_uri")

    if error:
        return jsonify_error(f"{error}: {error_description} ({error_uri})", 400)

    state = request.args.get("state")
    logging.debug(f"State: {state}")

    if not authorization_code:
        logging.error("Authorization code is missing")
        flash("Authorization code is missing", "error")
        return redirect(url_for("auth.profile"))

    flow = initialize_oauth_flow()

    try:
        fetch_oauth_tokens(flow, authorization_code)
        logging.info(
            "Authorization code exchanged for access_token, refresh_token, and expiry for user id"
        )
    except OAuth2Error as e:
        flash(f"Error exchanging authorization code: {e}", "error")
        return redirect(url_for("auth.profile"))

    user_id = session.get("user.id")
    if not user_id:
        flash("User not logged in or session expired", "error")
        return redirect(url_for("auth.profile"))

    save_tokens_to_db(flow, user_id)

    return redirect(url_for("auth.profile"))


@googledrive_bp.route("/google/drive/revoke", methods=["POST"])
def deauthorize():
    """Deauthorize the user by removing the tokens from the database."""
    user_id = session.get("user.id")
    if not user_id:
        return jsonify_error("User not logged in or session expired", 401)

    try:
        datasource = Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first()
        if not datasource:
            raise ValueError(f"{DATASOURCE_GOOGLE_DRIVE} is missing from datasource table in db")

        # Remove the tokens from the database
        UserAuth.query.filter_by(user_id=user_id, datasource_id=datasource.datasource_id).delete()

        # Remove the Google Drive items from the database
        GoogleDriveItem.query.filter_by(user_id=user_id).delete()

        db.session.commit()
        logging.info(f"User deauthorized from Google Drive for user id: {user_id}")
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Database error: {e}")
        return jsonify_error(f"Database error: {str(e)}", 500)

    return jsonify({"status": "success", "message": "User deauthorized from Google Drive"}), 200


@googledrive_bp.route("/google/drive/processfilepicker", methods=["POST"])
def process_file_picker():
    """Process the list of google docs ids returned by the file picker."""
    user_id = session["user.id"]
    documents = request.get_json()

    if not documents:
        logging.error("No documents selected")
        return "No documents selected"

    try:
        for doc in documents:
            new_item = GoogleDriveItem(
                user_id=user_id,
                google_drive_id=doc["id"],
                item_name=doc["name"],
                mime_type=doc["mimeType"],
                item_type=doc["type"],
            )
            db.session.add(new_item)
            logging.info(f"Inserted google doc id: {doc['id']} for user id: {user_id}")
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Error inserting google doc: {e}")
        return f"Error inserting google doc: {str(e)}"

    return "Success"


# /google/drive/removefile
@googledrive_bp.route("/google/drive/removefile", methods=["POST"])
def remove_file():
    """Remove a google drive item from the database."""
    user_id = session["user.id"]
    data = request.get_json()
    google_drive_id = data["google_drive_id"]

    try:
        GoogleDriveItem.query.filter_by(user_id=user_id, google_drive_id=google_drive_id).delete()
        db.session.commit()
        logging.info(f"Deleted google doc id: {google_drive_id} for user id: {user_id}")
    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Error deleting google doc id: {google_drive_id}: {e}")
        return f"Error deleting google doc id: {google_drive_id}"

    return "OK"
