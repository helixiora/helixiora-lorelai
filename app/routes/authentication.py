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
import time

import requests as lib_requests

from app.helpers.users import (
    user_is_logged_in,
    is_admin,
    get_org_id_by_userid,
    get_organisation_by_org_id,
    get_user_id_by_email,
    get_user_role_by_id,
    org_exists_by_name,
    validate_form,
    register_user_to_org,
)
from app.helpers.database import get_db_connection, get_query_result

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
            result = get_query_result(
                "SELECT auth_value FROM user_auth WHERE user_id = %s AND \
                    auth_key = 'refresh_token'",
                (session["user_id"],),
                fetch_one=True,
            )
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
            session["access_token"] = new_tokens["access_token"]
            if "refresh_token" in new_tokens:
                session["refresh_token"] = new_tokens["refresh_token"]
            else:
                # If the refresh token is not returned, use the existing one
                new_tokens["refresh_token"] = refresh_token

            store_access_token_query = "UPDATE user_auth SET auth_value = %s WHERE user_id = %s \
                AND auth_key = 'access_token'"
            store_refresh_token_query = "UPDATE user_auth SET auth_value = %s WHERE user_id = %s \
                AND auth_key = 'refresh_token'"
            db = get_db_connection()
            cursor = db.cursor()
            try:
                cursor.execute(
                    store_access_token_query, (new_tokens["access_token"], session["user_id"])
                )
                cursor.execute(
                    store_refresh_token_query, (new_tokens["refresh_token"], session["user_id"])
                )
                db.commit()
            finally:
                cursor.close()
                db.close()

            return new_tokens["access_token"]
        else:
            return None
    return access_token


@auth_bp.route("/profile")
def profile():
    """Return the profile page.

    Returns
    -------
        str: The profile page.
    """
    # only proceed if the user is logged in
    if user_is_logged_in(session):
        is_admin_status = is_admin(session["user_id"])
        user = {
            "user_id": session["user_id"],
            "email": session["user_email"],
            "username": session["user_username"],
            "full_name": session["user_fullname"],
            "organisation": session.get("org_name"),
            "roles": session.get("user_roles"),
        }
        googlesettings = load_config("google")
        google_client_id = googlesettings["client_id"]
        google_api_key = googlesettings["api_key"]

        # app id is everything before the first dash in the client id
        google_app_id = google_client_id.split("-")[0]

        # Get the user's Google access token from the database if it's not in the session
        if session.get("access_token") is None:
            result = get_query_result(
                "SELECT auth_value FROM user_auth WHERE user_id = %s AND auth_key = 'access_token'",
                (session["user_id"],),
                fetch_one=True,
            )
            # if there is no result, the user has not authenticated with Google (yet)
            if result:
                logging.info("Access token found in user_auth for user %s", session["user_id"])
                access_token = result["auth_value"]
            else:
                logging.info("No access token found in user_auth for user %s", session["user_id"])
                access_token = None
        else:
            logging.info("Access token found in session for user %s", session["user_id"])
            access_token = session.get("access_token")

        if access_token:
            # Check if the token is still valid and refresh if necessary
            access_token = refresh_google_token_if_needed(access_token)
            session["access_token"] = access_token

        if int(g.features["google_drive"]) == 1:
            google_docs_to_index = get_query_result(
                query="SELECT google_drive_id, item_name, mime_type, item_type, last_indexed_at \
                    FROM google_drive_items WHERE user_id = %s",
                params=(session["user_id"],),
                fetch_one=False,
            )
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
        logging.info("Google docs to index: %s", google_docs_to_index)
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

    if org_exists_by_name(organisation):
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

    # use this token to verify the user's identity
    idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())

    if not idinfo:
        raise exceptions.GoogleAuthError("Invalid token")

    # this function will raise an exception if the token is invalid
    validate_id_token(idinfo, csrf_token=csrf_token)

    # get some values from the info we got from google
    logging.info("Info from token: %s", idinfo)
    user_email = idinfo["email"]
    username = idinfo["name"]
    user_full_name = idinfo["name"]
    google_id = idinfo["sub"]

    # check if the user is already registered
    user_id = get_user_id_by_email(user_email)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        org_id = get_org_id_by_userid(cursor, user_id)
        organisation = get_organisation_by_org_id(cursor, org_id)

        # if we can't find the user, it means they are not registered
        # redirect them to the registration page
        if not user_id:
            logging.info("User not registered: %s", user_email)
            return redirect(
                url_for(
                    "auth.register_get", email=user_email, full_name=username, google_id=google_id
                )
            )

        # if we're still here, it means we found the user, so we log them in
        logging.info("User logging in: %s", user_email)
        login_user(
            user_id=user_id,
            user_email=user_email,
            google_id=google_id,
            username=username,
            full_name=user_full_name,
            org_id=org_id,
            org_name=organisation,
        )

        logging.debug("Session: %s", session)

        return redirect(url_for("chat.index"))

    except ValueError as e:
        logging.error("Invalid token: %s", e)
        return jsonify({"message": "Error: " + str(e)}), 401
    except exceptions.GoogleAuthError as e:
        logging.error("Google Auth Error: %s", e)
        return jsonify({"message": "Google Auth Error: " + str(e)}), 401
    except Exception as e:
        logging.exception("An error occurred: %s", e)
        return jsonify({"message": "An error occurred: " + str(e)}), 401
    finally:
        cursor.close()
        conn.close()


def login_user(
    user_id: int,
    user_email: str,
    google_id: str,
    username: str,
    full_name: str,
    org_id: int,
    org_name: str,
):
    """
    Create a session for the user and update the user's Google ID in the database.

    Parameters
    ----------
    user_id : int
        The user ID.
    user_email : str
        The user email.
    google_id : str
        The Google ID, uniquely identifies the user with Google.
    username : str
        The username.
    full_name : str
        The full name.
    org_id : int
        The organisation ID.
    org_name : str
        The organisation name.
    """
    # Ensure all details are provided
    if not all([user_id, user_email, google_id, username, full_name, org_id, org_name]):
        raise ValueError("All user and organization details must be provided.")

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # We May need to change this logic, as we are setting same thing every time user logs in.
        # Update the user's Google ID in the database
        cursor.execute(
            "UPDATE user SET google_id = %s, user_name = %s, full_name = %s \
            WHERE user_id = %s",
            (google_id, username, full_name, user_id),
        )

        # login_type, it is not necessary now but in future when we add multiple login method
        cursor.execute(
            "INSERT INTO user_login (user_id, login_type) \
            VALUES (%s, %s)",
            (user_id, "google-oauth"),
        )
        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

    # get the user's access token and refresh token

    access_token_query = get_query_result(
        "SELECT auth_value FROM user_auth WHERE user_id = %s AND auth_key = 'access_token' AND datasource_id = 2",  # noqa: E501
        (user_id,),
        fetch_one=True,
    )

    if not access_token_query:
        logging.warning("No access token found for user %s", user_id)
        access_token = None
    else:
        access_token = access_token_query["auth_value"]

    refresh_token_query = get_query_result(
        "SELECT auth_value FROM user_auth WHERE user_id = %s AND auth_key = 'refresh_token' AND datasource_id = 2",  # noqa: E501
        (user_id,),
        fetch_one=True,
    )

    if not refresh_token_query:
        logging.warning("No refresh token found for user %s", user_id)
        refresh_token = None
    else:
        refresh_token = refresh_token_query["auth_value"]

    # Get the user's roles
    user_roles = get_user_role_by_id(user_id)
    # Setup the session
    session["user_id"] = user_id
    session["user_email"] = user_email
    session["user_username"] = username
    session["user_fullname"] = full_name
    session["org_id"] = org_id
    session["org_name"] = org_name
    session["user_roles"] = user_roles
    if access_token:
        session["access_token"] = access_token
    if refresh_token:
        session["refresh_token"] = refresh_token


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
    user = get_query_result("SELECT 1 FROM user WHERE username = %s", (username,), fetch_one=True)
    return not user


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
    flash("You have been logged out.")

    return redirect(url_for("chat.index"))
