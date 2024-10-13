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

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from google.auth import exceptions
from google.auth.transport import requests
from google.oauth2 import id_token
from flask_login import login_required, login_user, logout_user, current_user
import time

import requests as lib_requests

from app.models import User, UserLogin, UserAuth, db, GoogleDriveItem, Organisation

from app.helpers.users import (
    is_admin,
    validate_form,
    register_user_to_org,
)

from lorelai.utils import load_config

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
        The refreshed access token.
    """
    token_info_url = f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
    response = lib_requests.get(token_info_url)
    if response.status_code != 200 or "error" in response.json():
        # Token is invalid or expired, refresh it
        refresh_token = session.get("refresh_token")
        logging.debug("Refreshing token for user %s: %s", session["user_id"], refresh_token)
        if not refresh_token or refresh_token is None:
            result = UserAuth.query.filter_by(
                user_id=current_user.id, auth_key="refresh_token"
            ).first()
            if not result:
                logging.error("No refresh token found for user %s", session["user_id"])
                return None
            refresh_token = result["auth_value"]

        google_settings = load_config("google")

        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": google_settings["client_id"],
            "client_secret": google_settings["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        token_response = lib_requests.post(token_url, data=payload)
        if token_response.status_code == 200:
            new_tokens = token_response.json()
            if "refresh_token" not in new_tokens:
                # If the refresh token is not returned, use the existing one
                new_tokens["refresh_token"] = refresh_token

            user_auth = UserAuth.query.filter_by(
                user_id=current_user.id, auth_key="refresh_token"
            ).first()
            if user_auth:
                user_auth.auth_value = new_tokens["refresh_token"]
            else:
                user_auth = UserAuth(
                    user_id=current_user.id,
                    auth_key="refresh_token",
                    auth_value=new_tokens["refresh_token"],
                )
                db.session.add(user_auth)

            db.session.commit()

            return new_tokens["access_token"]
        else:
            store_access_token_query = "UPDATE user_auth SET auth_value = %s WHERE user_id = %s \
                AND auth_key = 'access_token'"
            store_refresh_token_query = "UPDATE user_auth SET auth_value = %s WHERE user_id = %s \
                AND auth_key = 'refresh_token'"
            try:
                db.session.execute(
                    store_access_token_query, (new_tokens["access_token"], session["user_id"])
                )
                db.session.execute(
                    store_refresh_token_query, (new_tokens["refresh_token"], session["user_id"])
                )
                db.session.commit()
            finally:
                db.close()

            return new_tokens["access_token"]
    return access_token


@auth_bp.route("/profile")
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
        googlesettings = load_config("google")
        google_client_id = googlesettings["client_id"]
        google_api_key = googlesettings["api_key"]

        # app id is everything before the first dash in the client id
        google_app_id = google_client_id.split("-")[0]

        # Get the user's Google access token from the database if it's not in the session
        if session.get("access_token") is None:
            result = UserAuth.query.filter_by(
                user_id=current_user.id, auth_key="access_token"
            ).first()

            # if there is no result, the user has not authenticated with Google (yet)
            if result:
                logging.info("Access token found in user_auth for user %s", current_user.id)
                access_token = result.auth_value
            else:
                logging.info("No access token found in user_auth for user %s", current_user.id)
                access_token = None
        else:
            logging.info("Access token found in session for user %s", current_user.id)
            access_token = session.get("access_token")

        if access_token:
            # Check if the token is still valid and refresh if necessary
            access_token = refresh_google_token_if_needed(access_token)

        if int(g.features["google_drive"]) == 1:
            google_docs_to_index = GoogleDriveItem.query.filter_by(user_id=current_user.id).all()

            logging.info(
                "Google Drive feature is enabled. Found %s items to index.",
                len(google_docs_to_index),
            )
        else:
            logging.warning("Google Drive feature is disabled.")
            google_docs_to_index = None

        logging.info(
            "Rendering profile page for user %s with access_token %s", user["email"], access_token
        )

        if int(g.features["slack"]) == 1:
            logging.info("Slack feature is enabled.")
        else:
            logging.warning("Slack feature is disabled.")
        return render_template(
            "profile.html",
            user=user,
            is_admin=is_admin_status,
            google_client_id=google_client_id,
            google_api_key=google_api_key,
            google_docs_to_index=google_docs_to_index,
            google_app_id=google_app_id,
            google_drive_access_token=access_token,
            features=g.features,
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
    The user sends a POST request with a JSON object containing the ID token received from Google.
    The ID token is verified using Google's Identity Verification API and the user is authenticated.
    If the user is not registered, they are redirected to the registration page.

    Returns
    -------
        JSON: A JSON object with a message indicating whether the user was authenticated
        successfully.
    """
    # get the received token from the JSON data that came from the web client
    id_token_received = request.form.get("credential")
    csrf_token = request.form.get("g_csrf_token")

    try:
        # use this token to verify the user's identity
        idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())

        if not idinfo:
            raise exceptions.GoogleAuthError("Invalid token")

        # this function will raise an exception if the token is invalid
        validate_id_token(idinfo, csrf_token=csrf_token)

    except ValueError as e:
        logging.error("Invalid token: %s", e)
        return jsonify({"message": "Error: " + str(e)}), 401
    except exceptions.GoogleAuthError as e:
        logging.error("Google Auth Error: %s", e)
        return jsonify({"message": "Google Auth Error: " + str(e)}), 401
    except Exception as e:
        logging.exception("An error occurred: %s", e)
        return jsonify({"message": "An error occurred: " + str(e)}), 401

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

    # if we're still here, it means we found the user, so we log them in
    logging.info("User logging in: %s", user_email)
    login_user_function(
        user=user,
        user_email=user_email,
        google_id=google_id,
        username=username,
        full_name=user_full_name,
    )

    logging.debug("Session: %s", session)

    return redirect(url_for("chat.index"))


def login_user_function(
    user: User,
    user_email: str,
    google_id: str,
    username: str,
    full_name: str,
):
    """
    Create a session for the user and update the user's Google ID in the database.

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
        raise ValueError("All user and organization details must be provided.")

    try:
        user.google_id = google_id
        user.user_name = username
        user.full_name = full_name
        db.session.commit()

        # login_type, it is not necessary now but in future when we add multiple login method
        user_login = UserLogin(user_id=user.id, login_type="google-oauth")

        db.session.add(user_login)
        db.session.commit()
        login_user(user)

    except Exception as e:
        db.session.rollback()
        raise e


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

    googlesettings = load_config("google")
    if idinfo["aud"] not in googlesettings["client_id"]:
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
