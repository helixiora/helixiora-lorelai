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
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
    make_response,
)
from google.auth import exceptions
from google.auth.transport import requests
from google.oauth2 import id_token
from flask_login import login_required, login_user, logout_user, current_user
import time

import requests as lib_requests

from flask import current_app

from app.models import User, UserLogin, UserAuth, db, GoogleDriveItem, Organisation, Datasource
from app.helpers.slack import SlackHelper
from app.helpers.datasources import DATASOURCE_SLACK, DATASOURCE_GOOGLE_DRIVE
from app.helpers.users import (
    is_admin,
    validate_form,
    register_user_to_org,
    update_user_profile,
    get_user_profile,
)
from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema

from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
)

auth_bp = Blueprint("auth", __name__)


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
            user_id=current_user.id, auth_key="refresh_token", datasource_id=datasource_id
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
                user_id=current_user.id, auth_key="refresh_token", datasource_id=datasource_id
            ).delete()
            UserAuth.query.filter_by(
                user_id=current_user.id, auth_key="access_token", datasource_id=datasource_id
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
            user_id=current_user.id, auth_key="refresh_token", datasource_id=datasource_id
        ).update({"auth_value": new_tokens["refresh_token"]})

    db.session.commit()
    return new_access_token


@auth_bp.route("/profile", methods=["POST"])
@login_required
def user_profile():
    """Manage the current user's profile."""
    if request.method == "POST":
        bio = request.form.get("bio")
        location = request.form.get("location")
        birth_date = request.form.get("birth_date")
        avatar_url = request.form.get("avatar_url")

        update_user_profile(current_user.id, bio, location, birth_date, avatar_url)
        flash("Profile updated successfully", "success")
        return redirect(url_for("auth.profile"))


def get_google_drive_access_token() -> str:
    """Get the user's Google access token from the database if it's not in the session."""
    google_drive_access_token = ""
    datasource_id = Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first().datasource_id

    if session.get("google_drive.access_token") is None:
        result = UserAuth.query.filter_by(
            user_id=current_user.id, auth_key="access_token", datasource_id=datasource_id
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

        profile = get_user_profile(current_user.id)

        if int(current_app.config["FEATURE_GOOGLE_DRIVE"]) == 1:
            google_drive_access_token = get_google_drive_access_token()
            google_docs_to_index = GoogleDriveItem.query.filter_by(user_id=current_user.id).all()
            logging.info(
                "Google Drive feature is enabled. Found %s items to index.",
                len(google_docs_to_index),
            )
        else:
            logging.warning("Google Drive feature is disabled.")
            google_docs_to_index = None
            google_drive_access_token = None

        slack_channels = None
        if int(current_app.config["FEATURE_SLACK"]) == 1:
            logging.info("Slack feature is enabled.")
            # Get the Slack datasource ID
            slack_datasource = Datasource.query.filter_by(name=DATASOURCE_SLACK).first()
            if not slack_datasource:
                logging.error("Slack datasource not found in database")
                slack_channels = None
            else:
                slack_auth = UserAuth.query.filter_by(
                    user_id=current_user.id,
                    auth_key="access_token",
                    datasource_id=slack_datasource.datasource_id,
                ).first()

                if slack_auth and slack_auth.auth_value:
                    # Get all Slack auth records for the user
                    user_auths = UserAuth.query.filter_by(
                        user_id=current_user.id, datasource_id=slack_datasource.datasource_id
                    ).all()

                    try:
                        slack = SlackHelper(
                            user=UserSchema.from_orm(current_user),
                            organisation=OrganisationSchema.from_orm(current_user.organisation),
                            user_auths=[UserAuthSchema.from_orm(auth) for auth in user_auths],
                        )
                        if SlackHelper.test_slack_token(slack_auth.auth_value):
                            slack_channels = slack.get_accessible_channels(only_joined=True)
                            # convert from channelid = channelname to a list of #channelnames
                            slack_channels = [f"#{name}" for name in slack_channels.values()]
                        else:
                            logging.warning("Slack token is invalid")
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

        return render_template(
            "profile.html",
            user=user,
            is_admin=is_admin_status,
            google_docs_to_index=google_docs_to_index,
            google_drive_access_token=google_drive_access_token,
            slack_channels=slack_channels,
            profile=profile,
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
    email = request.form.get("email")
    full_name = request.form.get("full_name")
    organisation = request.form.get("organisation")
    google_id = request.form.get("google_id")

    logging.info("Registering user: %s with google_id: %s", email, google_id)

    org = Organisation.query.filter_by(name=organisation).first()
    if not org:
        flash("Organisation does not exist. Please contact admin.", "danger")
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
    success, message, user_id, org_id = register_user_to_org(
        email, full_name, organisation, google_id
    )

    if success:
        login_user(
            user_id=user_id,
            user_email=email,
            google_id=google_id,
            username=full_name,
            full_name=full_name,
            org_id=org_id,
            org_name=organisation,
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
    id_token_received = request.form.get("credential")
    # even thouugh we use csrf_token for our own token, we still need to use g_csrf_token
    # because google expects it
    csrf_token = request.form.get("g_csrf_token")

    try:
        idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())

        if not idinfo:
            raise exceptions.GoogleAuthError("Invalid token")

        validate_id_token(idinfo, csrf_token=csrf_token)

    except (ValueError, exceptions.GoogleAuthError) as e:
        logging.error("Authentication error: %s", str(e))
        flash("Authentication failed: " + str(e), "error")
        return redirect(url_for("chat.index"))
    except Exception as e:
        logging.exception("An unexpected error occurred: %s", e)
        flash("An unexpected error occurred. Please try again later.", "error")
        return redirect(url_for("chat.index"))

    # get some values from the info we got from google
    logging.info("Info from token: %s", idinfo)
    user_email = idinfo["email"]
    username = idinfo["name"]
    user_full_name = idinfo["name"]
    google_id = idinfo["sub"]

    # check if the user is already registered
    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        # if we can't find the user, it means they are not registered
        # redirect them to the registration page
        return redirect(
            url_for("auth.register_get", email=user_email, full_name=username, google_id=google_id)
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
        response = make_response(redirect(url_for("auth.profile")))
        response.set_cookie(
            key="access_token_cookie",
            value=session["lorelai_jwt.access_token"],
            httponly=True,
            secure=True,
            samesite="Strict",
        )
        response.set_cookie(
            key="refresh_token_cookie",
            value=session["lorelai_jwt.refresh_token"],
            httponly=True,
            secure=True,
            samesite="Strict",
        )

        flash("Login successful!", "success")
        return response
    else:
        flash("Login failed. Please try again.", "error")
        return redirect(url_for("chat.index"))


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh the access token.

    Returns
    -------
        str: The new access token.
    """
    current_user = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user)
    response = make_response(jsonify(access_token=new_access_token), 200)
    response.set_cookie(
        key="access_token_cookie",
        value=new_access_token,
        httponly=True,
        secure=True,
        samesite="Strict",
    )
    return response


def login_user_function(
    user: User,
    user_email: str,
    google_id: str,
    username: str,
    full_name: str,
):
    """
    Create a session for the user, update the user's Google ID in the database.

    also create access and refresh tokens.

    Parameters
    ----------
    user : User
        The user.
    user_email : str
        The user email.
    google_id : str
        The Google ID, uniquely identifies the user with Google.
    username : str
        The username.
    full_name : str
        The full name.

    Returns
    -------
    bool
        True if login was successful, False otherwise.
    """
    # Ensure all details are provided
    if not all(
        [
            user,
            user_email,
            google_id,
            username,
            full_name,
            user.organisation.id,
            user.organisation.name,
        ]
    ):
        logging.error("Missing user or organisation details")
        return False

    try:
        user.google_id = google_id
        user.user_name = username
        user.full_name = full_name
        db.session.commit()

        # Create access and refresh tokens
        # duration is determined by the JWT_ACCESS_TOKEN_EXPIRES and JWT_REFRESH_TOKEN_EXPIRES
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)

        # login_type, it is not necessary now but in future when we add multiple login method
        user_login = UserLogin(user_id=user.id, login_type="google-oauth")
        db.session.add(user_login)
        db.session.commit()

        # login_user is a Flask-Login function that sets the current user to the user object
        login_user(user)

        # store the user's roles in the session
        session["user.user_roles"] = [role.name for role in user.roles]
        session["user.org_name"] = user.organisation.name
        # store the access and refresh tokens in the session
        session["lorelai_jwt.access_token"] = access_token
        session["lorelai_jwt.refresh_token"] = refresh_token
        user_schema = UserSchema.model_validate(user).model_dump()

        for key, value in user_schema.items():
            logging.debug(f"user.{key} : {value}")
            session[f"user.{key}"] = value

        return True

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error during login: {str(e)}")
        return False


def is_username_available(username: str) -> bool:
    """
    Check if the username is available.

    Parameters
    ----------
    username : str
        The username to check.

    Returns
    -------
    bool
        True if the username is available, False otherwise.
    """
    # check if the username is already taken
    user = User.query.filter_by(user_name=username).first()
    if user:
        return False
    return True


def validate_id_token(idinfo: dict, csrf_token: str):
    """
    Validate the ID token.

    Parameters
    ----------
    idinfo : dict
        The ID token information.
    csrf_token : str
        The CSRF token from the body of the POST request.

    Raises
    ------
    ValueError
        If the issuer is wrong or the email is not verified.
    """
    # TODO: Add more checks here, see
    # https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

    if not csrf_token:
        raise exceptions.GoogleAuthError("No CSRF token in post body.")

    csrf_token_cookie = request.cookies.get("g_csrf_token")
    if not csrf_token_cookie:
        raise exceptions.GoogleAuthError("No CSRF token in cookie.")

    if csrf_token != csrf_token_cookie:
        raise exceptions.GoogleAuthError("CSRF token mismatch.")

    if idinfo["aud"] not in current_app.config["GOOGLE_CLIENT_ID"]:
        raise exceptions.GoogleAuthError("Wrong client ID.")

    if idinfo["exp"] < time.time():
        raise exceptions.GoogleAuthError("Token expired.")

    if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise exceptions.GoogleAuthError("Wrong issuer.")
    if not idinfo.get("email_verified"):
        raise exceptions.GoogleAuthError("Email not verified")


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
