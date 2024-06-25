"""Routes for user authentication."""

import logging

import mysql.connector
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
            "username": session["user_name"],
            "full_name": session["user_fullname"],
            "organisation": session.get("org_name", "N/A"),
        }
        return render_template(
            "profile.html",
            user=user,
            is_admin=is_admin_status,
            features=g.features,
            google_auth_url=google_auth_url(),
        )
    return "You are not logged in!", 403


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Return the registration page.

    If the request method is POST, the user data is validated and inserted into the database.
    If the user is already registered, they are redirected to the index page.

    If the request method is GET, the registration page is rendered with the user's email and
    full name.

    Returns
    -------
        str: The registration page.
    """
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

        # update the user in the database
        cursor.execute(
            "UPDATE user SET google_id = %s WHERE user_id = %s",
            (google_id, user_id),
        )
        # update user_auth
        cursor.execute(
            "INSERT INTO user_auth (user_id, datasource_id, auth_key, auth_value, auth_type) \
                VALUES (%s, %s, %s, %s, %s)",
            (user_id, 1, "google_id", google_id, "oauth"),
        )
        conn.commit()

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
    except exceptions.GoogleAuthError as e:
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
    session.clear()
    flash("You have been logged out.")

    return redirect(url_for("index"))
