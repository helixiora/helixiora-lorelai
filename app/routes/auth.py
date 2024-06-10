"""Routes for user authentication."""

import logging

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport import requests
from google.oauth2 import id_token

from app.utils import get_db_connection, get_query_result, is_admin

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
            "username": session["username"],
            "full_name": session["user_full_name"],
            "organisation": session.get("organisation", "N/A"),
        }
        return render_template(
            "profile.html", user=user, is_admin=is_admin_status, features=g.features
        )
    return "You are not logged in!", 403


@auth_bp.route("/register")
def register():
    """The registration page."""
    return render_template("register.html")


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
        validate_id_token(idinfo)

        logging.info("Info from token: %s", idinfo)
        user_email = idinfo["email"]
        username = idinfo["name"]
        user_full_name = idinfo["name"]

        user_id = get_user_id_by_email(user_email)

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
        return jsonify({"message": "An error occurred: " + str(e)}), 500


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
        raise ValueError("Wrong issuer.")
    if not idinfo.get("email_verified"):
        raise ValueError("Email not verified")


def get_user_id_by_email(email: str) -> int:
    """
    Get the user ID by email.

    Parameters
    ----------
    email : str
        The email of the user.

    Returns
    -------
    int
        The user ID.
    """
    result = get_query_result("SELECT user_id FROM user WHERE email = %s", (email,), fetch_one=True)
    return result["user_id"] if result else None


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
        cursor = db_conn.cursor()
        cursor.execute("DELETE FROM user_auth WHERE user_id = %s", (session["user_id"],))
        db_conn.commit()
        cursor.close()
    finally:
        session.clear()

    return redirect(url_for("index"))
