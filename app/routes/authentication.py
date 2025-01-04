"""Routes for user authentication.

The flow for authentication is:

1. The user opens /, handled by the index route.
2. The index route checks if the user is logged in.
3. If the user is not logged in, the index route displays the logged out page
4. From that page, if the user logs in with Google, the /login route is called by google at the end
    of the OAuth flow
5. The /login route verifies the token and logs the user and redirects to the logged in index page
6. If the user is not registered, they are redirected to the /register page

NOTE: Google has separated authentication and authorization. Authentication is verifying the user's
identity, while authorization is verifying the user's permissions to access a resource. This file
handles authentication, while the google/authorization.py file handles authorization.

References
----------
- https://developers.google.com/identity/gsi/web/guides/verify-google-id-token
- https://stackoverflow.com/questions/72766506/relationship-between-google-identity-services-sign-in-with-google-and-user-aut
"""

import logging

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
    make_response,
)
from datetime import datetime
from google.auth import exceptions
from google.auth.transport import requests
from google.oauth2 import id_token
from flask_login import login_required, logout_user, current_user

from app.helpers import email_validator, url_validator
from app.helpers.auth import login_user_function, validate_id_token
from app.helpers.googledrive import get_token_details

from flask import current_app

from app.models import (
    User,
    UserAuth,
    GoogleDriveItem,
    Organisation,
    Datasource,
    Profile,
)
from app.helpers.slack import SlackHelper
from app.helpers.datasources import DATASOURCE_SLACK
from app.helpers.users import is_admin, validate_form, register_user_to_org, update_user_profile
from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema


import bleach
from pydantic import ValidationError

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/profile", methods=["POST"])
@login_required
def user_profile():
    """Manage the current user's profile."""
    if request.method == "POST":
        # Sanitize and validate text inputs
        bio = bleach.clean(request.form.get("bio", ""), strip=True)
        location = bleach.clean(request.form.get("location", ""), strip=True)

        # Validate date format
        birth_date = request.form.get("birth_date", "")
        try:
            if birth_date:
                datetime.strptime(birth_date, "%Y-%m-%d")
        except ValueError:
            birth_date = None

        # Validate URL format
        avatar_url = request.form.get("avatar_url", "")
        if avatar_url and not url_validator(avatar_url):
            avatar_url = None

        update_user_profile(
            user_id=current_user.id,
            bio=bio,
            location=location,
            birth_date=birth_date,
            avatar_url=avatar_url,
        )
        flash("Profile updated successfully", "success")
        return redirect(url_for("auth.profile"))


@auth_bp.route("/profile", methods=["GET"])
@login_required
def profile():
    """Return the profile page.

    Returns
    -------
        str: The profile page.
    """
    # only proceed if the user is logged in
    if current_user.is_authenticated:
        is_admin_status = is_admin(current_user.id)
        user = {
            "user_id": current_user.id,
            "email": current_user.email,
            "username": current_user.user_name,
            "full_name": current_user.full_name,
            "organisation": current_user.organisation.name,
            "roles": current_user.roles,
        }

        profile = Profile.query.filter_by(user_id=current_user.id).first()

        if int(current_app.config["FEATURE_GOOGLE_DRIVE"]) == 1:
            try:
                google_drive_tokens = get_token_details(current_user.id)
                google_drive_access_token = google_drive_tokens.access_token
                google_docs_to_index = GoogleDriveItem.query.filter_by(
                    user_id=current_user.id
                ).all()
                logging.info(
                    "Google Drive feature is enabled. Found %s items to index.",
                    len(google_docs_to_index),
                )
            except ValueError:
                logging.info("User %s has not connected Google Drive yet", current_user.id)
                google_docs_to_index = None
                google_drive_tokens = None
                google_drive_access_token = None
        else:
            logging.warning("Google Drive feature is disabled.")
            google_docs_to_index = None
            google_drive_tokens = None
            google_drive_access_token = None
        slack_channels = None
        if int(current_app.config["FEATURE_SLACK"]) == 1:
            logging.info("Slack feature is enabled.")
            # Get the Slack datasource
            slack_datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()
            if not slack_datasource:
                logging.error("Slack datasource not found in database")
                slack_channels = None
                slack_auth = None
            else:
                slack_auth = UserAuth.query.filter_by(
                    user_id=current_user.id,
                    auth_key="access_token",
                    datasource_id=slack_datasource.datasource_id,
                ).first()

                if slack_auth and slack_auth.auth_value:
                    # Test the token validity
                    is_valid = SlackHelper.test_slack_token(slack_auth.auth_value)
                    if not is_valid:
                        logging.warning("Slack token is invalid")
                        slack_channels = None
                        # Keep slack_auth so template knows to show revoke button
                    else:
                        # Get all Slack auth records for the user
                        user_auths = UserAuth.query.filter_by(
                            user_id=current_user.id,
                            datasource_id=slack_datasource.datasource_id,
                        ).all()

                        try:
                            slack = SlackHelper(
                                user=UserSchema.from_orm(current_user),
                                organisation=OrganisationSchema.from_orm(current_user.organisation),
                                user_auths=[UserAuthSchema.from_orm(auth) for auth in user_auths],
                            )
                            try:
                                channels = slack.get_accessible_channels(only_joined=True)
                                if channels:
                                    slack_channels = [f"#{name}" for name in channels.values()]
                                else:
                                    logging.warning("No accessible Slack channels found")
                                    slack_channels = None
                            except AttributeError:
                                logging.warning(
                                    "Error accessing Slack channels - possible permissions issue"
                                )
                                slack_channels = None
                        except Exception as e:
                            logging.error(f"Error initializing SlackHelper: {e}")
                            slack_channels = None
                else:
                    logging.info("No Slack access token found")
                    slack_channels = None
                    slack_auth = None
        else:
            logging.warning("Slack feature is disabled.")
            slack_channels = None
            slack_auth = None

        return render_template(
            "profile.html",
            user=user,
            is_admin=is_admin_status,
            google_docs_to_index=google_docs_to_index,
            google_drive_access_token=google_drive_access_token,
            slack_channels=slack_channels,
            slack_auth=slack_auth,
            profile=profile,
            api_keys=current_user.api_keys,
        )
    return "You are not logged in!", 403


@auth_bp.route("/register", methods=["GET"])
def register_get():
    """Return the registration page.

    If the request method is GET, the registration page is rendered with the user's email and
    full name.

    This means we are in the signup flow and the user

    Returns
    -------
        str: The registration page.
    """
    email = request.args.get("email", "")
    full_name = request.args.get("full_name", "")
    google_id = request.args.get("google_id", "")

    return render_template(
        "register.html",
        email=email,
        full_name=full_name,
        google_id=google_id,
    )


@auth_bp.route("/register", methods=["POST"])
def register_post():
    """Handle the registration form submission.

    If the request method is POST, the user data is validated and inserted into the database.
    If the user is already registered, they are redirected to the index page.

    Returns
    -------
        str: The registration page or a redirect to the index page.
    """
    # Sanitize and validate email
    email = bleach.clean(request.form.get("email", ""), strip=True).lower()
    if not email_validator(email):
        raise ValidationError("Invalid email format")

    # Sanitize name and organization
    full_name = bleach.clean(request.form.get("full_name", ""), strip=True)
    organisation = bleach.clean(request.form.get("organisation", ""), strip=True)

    # Validate Google ID format (assuming it's a string of numbers)
    google_id = request.form.get("google_id", "")
    if google_id and not google_id.isdigit():
        raise ValidationError("Invalid Google ID format")

    logging.info("Registering user: %s with google_id: %s", email, google_id)

    org = Organisation.query.filter_by(name=organisation).first()
    if org:
        flash("Organisation already exist. Please contact admin.", "danger")
        return redirect(url_for("org_exists"))

    missing = validate_form(email=email, name=full_name, organisation=organisation)

    if missing:
        flash("All fields are required. Missing: " + missing, "danger")
        return render_template(
            "register.html",
            email=email,
            full_name=full_name,
            organisation=organisation,
            google_id=google_id,
        )

    # register the user
    success, message, user = register_user_to_org(email, full_name, organisation, google_id)

    if success:
        login_user_function(
            user=user,
            user_email=email,
            google_id=google_id,
            username=full_name,
            full_name=full_name,
        )

    flash("Registration successful!", "success")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login route.

    This route is used to authenticate a user using Google's Identity Verification API.
    The user sends a POST request with the ID token received from Google.
    The ID token is verified using Google's Identity Verification API and the user is authenticated.
    If the user is not registered, they are redirected to the registration page.
    If authentication is successful, the user is redirected to the profile page.
    If authentication fails, the user is redirected to the index page with an error message.

    Returns
    -------
        redirect: Redirects to the appropriate page based on the authentication result.
    """
    # Get and validate ID token
    id_token_received = request.form.get("credential", "").strip()
    if not id_token_received or not isinstance(id_token_received, str):
        raise ValidationError("Invalid or missing ID token")

    # Get Google's CSRF token
    g_csrf_token = request.form.get("g_csrf_token", "").strip()

    # Validate Google's CSRF token
    if not g_csrf_token:
        raise exceptions.GoogleAuthError("No CSRF token in post body.")

    g_csrf_token_cookie = request.cookies.get("g_csrf_token")
    if not g_csrf_token_cookie:
        raise exceptions.GoogleAuthError("No CSRF token in cookie.")

    if g_csrf_token != g_csrf_token_cookie:
        raise exceptions.GoogleAuthError("CSRF token mismatch.")

    try:
        idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())

        if not idinfo:
            raise exceptions.GoogleAuthError("Invalid token")

        validate_id_token(idinfo)

    except (ValueError, exceptions.GoogleAuthError) as e:
        logging.error("Authentication error: %s", str(e))
        flash("Authentication failed: " + str(e), "error")
        return redirect(url_for("chat.index"))
    except Exception as e:
        logging.exception("An unexpected error occurred: %s", e)
        flash("An unexpected error occurred. Please try again later.", "error")
        return redirect(url_for("chat.index"))

    # get some values from the info we got from google
    logging.debug("Info from token: %s", idinfo)
    user_email = idinfo["email"]
    username = idinfo["name"]
    user_full_name = idinfo["name"]
    google_id = idinfo["sub"]

    # check if the user is already registered
    user = User.query.filter_by(email=user_email).first()

    if not user:
        # if we can't find the user, it means they are not registered
        # redirect them to the registration page
        return redirect(
            url_for(
                "auth.register_get",
                email=user_email,
                full_name=username,
                google_id=google_id,
            )
        )

    logging.info("User logging in: %s", user_email)
    login_success = login_user_function(
        user=user,
        user_email=user_email,
        google_id=google_id,
        username=username,
        full_name=user_full_name,
    )

    if login_success:
        # Create response with redirect
        response = make_response(redirect(url_for("auth.profile")))
        return response

    flash("Login failed", "error")
    return redirect(url_for("chat.index"))


@auth_bp.route("/logout", methods=["GET"])
@login_required
def logout():
    """
    Logout route.

    Clears the session and access tokens, then redirects to the index page.

    Returns
    -------
    str
        Redirects to the index page.
    """
    session.clear()
    logout_user()
    flash("You have been logged out.")

    return redirect(url_for("chat.index"))
