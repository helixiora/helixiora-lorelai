"""Routes for user authentication.

The flow for authentication is:

1. The user opens /, handled by the index route.
2. The index route checks if the user is logged in.
3. If the user is not logged in, the index route displays the logged out page
4. From that page, if the user logs in, we run javascript code to send a POST request to /login
5. The login route may return a redirect URL to the frontend, which will redirect the user to the
    registration page
6. The user registers and is redirected to the login page
7. The user logs in and is redirected to the logged in index page


"""

import logging

from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from google.auth import exceptions
from google.auth.transport import requests
from google.oauth2 import id_token

from app.routes.google.auth import google_auth_url
from app.utils import (
    get_db_connection,
    get_org_id_by_organisation,
    get_org_id_by_userid,
    get_organisation_by_org_id,
    get_query_result,
    get_user_id_by_email,
    is_admin,
    user_is_logged_in,
)
from lorelai.slack.slack_processor import SlackOAuth

auth_bp = Blueprint("auth", __name__)


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
        }
        return render_template(
            "profile.html",
            user=user,
            is_admin=is_admin_status,
            features=g.features,
            google_auth_url=google_auth_url(),
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
    google_token = request.args.get("google_token", "")
    google_id = request.args.get("google_id", "")

    logging.debug(
        "Received email: %s, full_name: %s, google_id: %s, token: %s",
        email,
        full_name,
        google_id,
        google_token,
    )

    return render_template(
        "register.html",
        email=email,
        full_name=full_name,
        google_id=google_id,
        google_token=google_token,
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
    google_token = request.form.get("google_token")

    missing = validate_form(email=email, name=full_name, organisation=organisation)

    if missing:
        flash("All fields are required. Missing: " + missing, "danger")
        return render_template(
            "register.html",
            email=email,
            full_name=full_name,
            organisation=organisation,
            google_id=google_id,
            google_token=google_token,
        )

    # register the user
    success, message, user_id = register_user_to_org(
        email, full_name, organisation, google_id, google_token
    )

    flash("Registration successful!", "success")
    return redirect(url_for("index"))


def register_user_to_org(
    email: str, full_name: str, organisation: str, google_id: str, google_token: str
) -> (bool, str, int):
    """
    Register a user to an organisation.

    Parameters
    ----------
    email : str
        The user's email.
    full_name : str
        The user's full name.
    organisation : str
        The organisation name.
    google_id : str
        The Google ID.
    google_token : str
        The Google Oauth token.

    Returns
    -------
    tuple
        A tuple containing a boolean indicating success, a message, and the user ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # check if the organisation exists
        org_id, created_new_org = get_org_id_by_organisation(
            conn=conn, organisation=organisation, create_if_not_exists=True
        )

        # insert the user
        user_id, user_created_success = insert_user(
            cursor, org_id, full_name, email, full_name, google_id
        )

        # if created = True, this is the first user of the org so make them an org_admin by
        # inserting a record in the user_roles table
        if user_created_success and created_new_org:
            # get the role_id of the org_admin role
            cursor.execute("SELECT role_id FROM roles WHERE role_name = 'org_admin'")
            role_id = cursor.fetchone()["role_id"]

            cursor.execute(
                "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                (session["user_id"], role_id),
            )

        conn.commit()

        return True, "Registration successful!", user_id

    except Exception as e:
        conn.rollback()
        return False, f"An error occurred: {e}", -1

    finally:
        cursor.close()
        conn.close()


def insert_user(
    cursor, org_id: int, name: str, email: str, full_name: str, google_id: str
) -> (int, bool):
    """Insert a new user and return the user ID."""
    cursor.execute(
        "INSERT INTO user (org_id, user_name, email, full_name, google_id) \
            VALUES (%s, %s, %s, %s, %s)",
        (org_id, name, email, full_name, google_id),
    )

    # return lastrowid if the insert was successful
    user_id = cursor.lastrowid
    if user_id:
        return user_id, True
    return -1, False


def validate_form(email: str, name: str, organisation: str):
    """Validate the registration form.

    Parameters
    ----------
    email : str
        The user's email.
    name : str
        The user's name.
    organisation : str
        The user's organisation.

    Returns
    -------
    list
        A list of missing fields.
    """
    missing_fields = []

    if not email:
        missing_fields.append("email")
    if not name:
        missing_fields.append("name")
    if not organisation:
        missing_fields.append("organisation")

    return missing_fields


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
    try:
        if request.content_type != "application/json":
            return jsonify({"message": "Invalid content type: " + request.content_type}), 400

        data = request.get_json()
        logging.info("Received JSON data: %s", data)

        id_token_received = data.get("credential")

        idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())

        if not idinfo:
            raise exceptions.GoogleAuthError("Invalid token")

        # this function will raise an exception if the token is invalid
        validate_id_token(idinfo)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        logging.info("Info from token: %s", idinfo)
        user_email = idinfo["email"]
        username = idinfo["name"]
        user_full_name = idinfo["name"]
        google_id = idinfo["sub"]
        user_id = get_user_id_by_email(user_email)

        org_id = get_org_id_by_userid(cursor, user_id)
        organisation = get_organisation_by_org_id(cursor, org_id)

        # if we can't find the user, it means they are not registered
        # we don't redirect directly, but send a message back to the frontend to redirect using JS
        if not user_id:
            return jsonify(
                {
                    "message": "Invalid login",
                    "email": user_email,
                    "full_name": user_full_name,
                    "google_id": google_id,
                    "google_token": id_token_received,
                    "redirect_url": url_for("auth.register_get"),
                }
            ), 200

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

        return jsonify({"message": "User authenticated successfully", "redirect_url": "/"}), 200

    except ValueError as e:
        logging.error("Invalid token: %s", e)
        return jsonify({"message": "Error: " + str(e)}), 401
    except Exception as e:
        logging.exception("An error occurred: %s", e)
        return jsonify({"message": "An error occurred: " + str(e)}), 401
    except exceptions.GoogleAuthError as e:
        logging.error("Google Auth Error: %s", e)
        return jsonify({"message": "Google Auth Error: " + str(e)}), 401
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

        # Update the user's Google ID in the database
        cursor.execute(
            "UPDATE user SET google_id = %s WHERE user_id = %s",
            (google_id, user_id),
        )

        # Check if user_auth entry exists
        cursor.execute(
            "SELECT 1 FROM user_auth WHERE user_id = %s AND datasource_id = %s",
            (user_id, 1),
        )
        user_auth_entry = cursor.fetchone()

        if user_auth_entry:
            # Update user_auth entry if it exists
            cursor.execute(
                """
                UPDATE user_auth SET auth_value = %s, auth_type = %s
                WHERE user_id = %s AND datasource_id = %s AND auth_key = %s
                """,
                (google_id, "oauth", user_id, 1, "google_id"),
            )
        else:
            # Insert a new user_auth entry if it does not exist
            cursor.execute(
                """
                INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, 1, "google_id", google_id, "oauth"),
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

    # Setup the session
    session["user_id"] = user_id
    session["user_email"] = user_email
    session["user_username"] = username
    session["user_fullname"] = full_name
    session["org_id"] = org_id
    session["org_name"] = org_name


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


def validate_id_token(idinfo: dict):
    """
    Validate the ID token.

    Parameters
    ----------
    idinfo : dict
        The ID token information.

    Raises
    ------
    ValueError
        If the issuer is wrong or the email is not verified.
    """
    if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise exceptions.GoogleAuthError("Wrong issuer.")
    if not idinfo.get("email_verified"):
        raise exceptions.GoogleAuthError("Email not verified")


@auth_bp.route("/slack/auth")
def slack_auth():
    """Slack OAuth route. Redirects to the Slack OAuth URL."""
    slack_oauth = SlackOAuth()
    return redirect(slack_oauth.get_auth_url())


@auth_bp.route("/slack/auth/callback")
def slack_callback():
    """Slack OAuth callback route. Handles the Slack OAuth callback."""
    slack_oauth = SlackOAuth()
    return slack_oauth.auth_callback()


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

    return redirect(url_for("index"))
