"""Routes for user authentication."""

import logging

import mysql.connector
from flask import Blueprint, flash, g, jsonify, redirect, render_template, request, session, url_for
from google.auth import exceptions
from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from app.utils import (
    get_db_connection,
    get_org_id_by_organisation,
    get_org_id_by_userid,
    get_organisation_by_org_id,
    get_query_result,
    get_user_id_by_email,
    is_admin,
)
from lorelai.utils import load_config

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/profile")
def profile():
    """The profile page."""

    # only proceed if the user is logged in
    if "user_id" in session:
        is_admin_status = is_admin(session["user_id"])
        user = {
            "user_id": session["user_id"],
            "email": session["user_email"],
            "username": session["user_name"],
            "full_name": session["user_fullname"],
            "organisation": session.get("organisation", "N/A"),
        }
        return render_template(
            "profile.html", user=user, is_admin=is_admin_status, features=g.features
        )
    return "You are not logged in!", 403


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """The registration page."""
    if request.method == "POST":
        email = request.form.get("email")
        full_name = request.form.get("full_name")
        organisation = request.form.get("organisation")

        if not validate_form(email, full_name, organisation):
            flash("All fields are required.", "danger")
            return render_template("register.html", email=email, full_name=full_name)

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            org_id = get_org_id_by_organisation(cursor, organisation, True)
            user_id = insert_user(cursor, org_id, full_name, email)
            insert_user_auth(cursor, user_id)

            conn.commit()

            flash("Registration successful!", "success")
            return redirect(url_for("index"))

        except mysql.connector.Error as err:
            flash(f"Error: {err}", "danger")
            return render_template("register.html", email=email, full_name=full_name)

        finally:
            cursor.close()
            conn.close()

    email = request.args.get("email", "")
    full_name = request.args.get("full_name", "")
    return render_template("register.html", email=email, full_name=full_name)


def insert_user(cursor, org_id: int, name: str, email: str, full_name: str):
    """Insert a new user and return the user ID."""
    cursor.execute(
        "INSERT INTO user (org_id, user_name, email, full_name) VALUES (%s, %s, %s, %s)",
        (org_id, name, email, name),
    )
    return cursor.lastrowid


def insert_user_auth(cursor, user_id):
    """Insert user authentication data."""
    datasource_id = 1  # Assuming a default datasource_id for demonstration
    auth_key = "default_key"
    auth_value = "default_value"
    auth_type = "default_type"
    cursor.execute(
        """INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type)
           VALUES (%s, %s, %s, %s, %s)""",
        (user_id, datasource_id, auth_key, auth_value, auth_type),
    )


def validate_form(email, name, organisation):
    """Validate form data."""
    return email and name and organisation


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    Login route.

    This route is used to authenticate a user using Google's Identity Verification API.
    The user sends a POST request with a JSON object containing the ID token received from Google.
    The ID token is verified using Google's Identity Verification API and the user is authenticated.
    If the user is not registered, they are redirected to the registration page.

    Returns:
        JSON: A JSON object with a message indicating whether the user was authenticated successfully.
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
        user_id = get_user_id_by_email(user_email)

        org_id = get_org_id_by_userid(cursor, user_id)
        organisation = get_organisation_by_org_id(cursor, org_id)

        if not user_id:
            return jsonify(
                {
                    "message": "Invalid login",
                    "email": user_email,
                    "full_name": user_full_name,
                    "redirect_url": url_for("auth.register"),
                }
            ), 200

        logging.info("User logging in: %s", user_email)

        session["user_id"] = user_id
        session["user_email"] = user_email
        session["user_name"] = username
        session["user_fullname"] = user_full_name
        session["org_id"] = org_id
        session["org_name"] = organisation

        logging.debug("Session: %s", session)

        return jsonify({"message": "User authenticated successfully", "redirect_url": "/"}), 200

    except ValueError as e:
        logging.error("Invalid token: %s", e)
        return jsonify({"message": "Error: " + str(e)}), 401
    except Exception as e:
        logging.exception("An error occurred: %s", e)
        return jsonify({"message": "An error occurred: " + str(e)}), 401
    except google_auth.exceptions.GoogleAuthError as e:
        logging.error("Google Auth Error: %s", e)
        return jsonify({"message": "Google Auth Error: " + str(e)}), 401
    finally:
        cursor.close()
        conn.close()


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
    try:
        db_conn = get_db_connection()
        cursor = db_conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM user_auth WHERE user_id = %s", (session["user_id"],))
        db_conn.commit()
        cursor.close()
    finally:
        session.clear()

    return redirect(url_for("index"))


@auth_bp.route("/google/auth", methods=["POST"])
def google_auth():
    """Handle Google authentication."""
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

    if "user_id" in session:
        user_data = {
            "user_organization": session["organisation"],
            "user_email": session["email"],
            "is_admin": is_admin(session["user_id"]),
        }

        return render_template("index_logged_in.html", **user_data)

    try:
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        session["state"] = state

    except RuntimeError as e:
        logging.debug(f"Error generating authorization URL: {e}")
        return render_template("error.html", error_message="Failed to generate login URL.")


@auth_bp.route("/google/auth/callback", methods=["GET"])
def auth_callback():
    """Callback route for Google OAuth2 authentication.
    This route is called by Google after the user has authenticated.
    The route verifies the state and exchanges the authorization code for an access token.
    Returns:
        string: The index page.
    """
    lorelaicreds = load_config("lorelai")

    state = request.args.get("state")
    if state != session["state"]:
        return render_template("error.html", error_message="Invalid state parameter.")

    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": lorelaicreds["client_id"],
                "project_id": lorelaicreds["project_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": lorelaicreds["client_secret"],
                "redirect_uris": lorelaicreds["redirect_uris"],
            }
        },
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        redirect_uri=lorelaicreds["redirect_uri"],
    )

    flow.fetch_token(authorization_response=request.url)

    session["credentials"] = flow.credentials.to_json()

    return redirect(url_for("index"))
