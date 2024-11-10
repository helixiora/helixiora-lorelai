"""Routes for the chat page."""

import logging

from flask import (
    blueprints,
    session,
    redirect,
    url_for,
    current_app,
    render_template,
)
from flask_login import current_user

from app.helpers.chat import get_chat_template_requirements
import uuid

chat_bp = blueprints.Blueprint("chat", __name__)


@chat_bp.route("/conversation/<conversation_id>", methods=["GET"])
def conversation(conversation_id):

    """Return the conversation page.

    Returns
    -------
        string: the conversation page
    """
    session["conversation_id"] = conversation_id
    chat_template_requirements = get_chat_template_requirements(conversation_id, session["user.id"])
    return render_template(
        "index_logged_in.html",
        username=session["user.user_name"],
        user_email=session["user.email"],
        recent_conversations=chat_template_requirements["recent_conversations"],
        is_admin=chat_template_requirements["is_admin_status"],
        support_portal=current_app.config["LORELAI_SUPPORT_PORTAL"],
        support_email=current_app.config["LORELAI_SUPPORT_EMAIL"],
    )

# Improved index route using render_template
@chat_bp.route("/")
# don't require a login for the index page (it's the login page)
def index():
    """Return the index page.

    Returns
    -------
        string: the index page
    """
    logging.debug("Index route")

    if current_app.config.get("LORELAI_SETUP"):
        # redirect to /admin/setup if the app is not set up
        logging.info("App is not set up. Redirecting to /admin/setup")
        return redirect(url_for("admin.setup"))

    # check if the user is logged in
    if current_user.is_authenticated:
        # render the index_logged_in page
        conversation_id = str(uuid.uuid4())
        session["conversation_id"] = conversation_id
        chat_template_requirements = get_chat_template_requirements(
            conversation_id, current_user.id
        )

        return render_template(
            "index_logged_in.html",
            user_email=current_user.email,
            username=current_user.user_name,
            recent_conversations=chat_template_requirements["recent_conversations"],
            is_admin=chat_template_requirements["is_admin_status"],
            support_portal=current_app.config["LORELAI_SUPPORT_PORTAL"],
            support_email=current_app.config["LORELAI_SUPPORT_EMAIL"],
        )

    # if we're still here, there was no user_id in the session meaning we are not logged in
    # render the front page with the google client id
    # if the user clicks login from that page, the javascript function `onGoogleCredentialResponse`
    # will handle the login using the /login route in auth.py.
    # Depending on the output of that route, it's redirecting to /register if need be

    return render_template("index.html", google_client_id=current_app.config["GOOGLE_CLIENT_ID"])
