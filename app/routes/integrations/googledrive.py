"""Google Drive authorization routes.

Google now recommends the Google Identity Services library for scope authorization.


References
----------
- https://developers.google.com/identity/protocols/oauth2/web-server
- https://developers.google.com/identity/protocols/oauth2/scopes
- https://developers.google.com/identity/oauth2/web/guides/use-code-model

"""

import logging


from flask import Blueprint, request, session, redirect, url_for, flash
from flask_login import login_required


from oauthlib.oauth2.rfc6749.errors import (
    OAuth2Error,
)

from app.helpers.googledrive import (
    initialize_oauth_flow,
    fetch_oauth_tokens,
    save_tokens_to_db,
    jsonify_error,
)


googledrive_bp = Blueprint("googledrive", __name__)


@googledrive_bp.route("/google/drive/codeclientcallback", methods=["GET"])
@login_required
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

    flash("Google Drive authorization successful! You can now select files to index.", "success")
    return redirect(url_for("auth.profile"))
