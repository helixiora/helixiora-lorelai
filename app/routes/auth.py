"""Routes for user authentication."""

import logging
from collections import namedtuple
from collections.abc import Iterable

import google.auth.transport.requests
from flask import blueprints, redirect, render_template, request, session, url_for
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow

from lorelai.slack_oauth import SlackOAuth

from app.utils import get_db_connection, is_admin, load_config

auth_bp = blueprints.Blueprint("auth", __name__)


@auth_bp.route("/profile")
def profile():
    """the profile page"""
    if "google_id" in session:
        # Example: Fetch user details from the database
        user = {
            "name": session["name"],
            "email": session["email"],
            "org_name": session["organisation"],
        }
        return render_template("profile.html", user=user, is_admin=is_admin(session["google_id"]))
    return "You are not logged in!"


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Register a new user."""
    if request.method == "GET":
        email = session.get("oauth_data", {}).get("email")
        name = session.get("oauth_data", {}).get("name")

        return render_template("register.html", email=email, name=name)

    # Process the registration form submission
    registration_info = request.form

    # Combine OAuth data with registration form data
    oauth_data = session.pop("oauth_data", {})

    logging.debug(f"Registration info: {registration_info}")
    logging.debug(f"OAuth data: {oauth_data}")

    username = registration_info["name"]
    user_email = registration_info["email"]
    organisation = registration_info["organisation"]
    access_token = session.pop("access_token", None)
    refresh_token = session.pop("refresh_token", None)
    expiry = session.pop("expiry", None)
    token_type = session.pop("token_type", None)
    scope = session.pop("scope", None)

    user_info = process_user(
        organisation,
        username,
        user_email,
        access_token,
        refresh_token,
        expiry,
        token_type,
        scope,
    )

    # logging.info(f"Creating user: {registration_info} / {oauth_data}")

    # Log the user in (pseudo code)
    login_user(
        user_info["name"],
        user_info["email"],
        user_info["org_id"],
        user_info["organisation"],
    )
    return redirect(url_for("index"))


@auth_bp.route("/oauth2callback")
def oauth_callback():
    """OAuth2 callback route."""
    # Load the Google OAuth2 secrets
    secrets = load_config("google")
    lorelaicreds = load_config("lorelai")

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

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.readonly",
            "openid",
        ],
        redirect_uri=lorelaicreds["redirect_uri"],
    )

    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        return "State does not match!", 400

    credentials = flow.credentials
    request_session = google.auth.transport.requests.Request()
    id_info = id_token.verify_oauth2_token(
        id_token=credentials.id_token,  # pyright: ignore reportAttributeAccessIssue=false
        request=request_session,
        audience=flow.client_config["client_id"],
    )

    logging.debug(f"id_info: {id_info}")
    logging.debug(f"credentials: {credentials}")

    # Check if user exists in your database
    userid, name, orgid, organisation = check_user_in_database(id_info["email"])
    email = id_info["email"]

    if not userid:
        # Save the necessary OAuth data in the session to complete registration later

        session["access_token"] = credentials.token
        session["refresh_token"] = credentials.refresh_token
        session["expiry"] = credentials.expiry
        session["token_type"] = "Bearer"
        session["scope"] = credentials.scopes

        session["oauth_data"] = id_info
        # Redirect to the registration page
        return redirect(url_for("auth.register"))

    # Log the user in
    login_user(name, email, orgid, organisation)
    return redirect(url_for("index"))


def login_user(name: str, email: str, org_id: int, organisation: str) -> None:
    """
    Log the user in by setting the session variables.
    """

    session["google_id"] = email
    session["name"] = name
    session["email"] = email
    session["org_id"] = org_id
    session["organisation"] = organisation


# Define a named tuple structure for the user information
UserInfo = namedtuple("UserInfo", "user_id name org_id organisation")


def check_user_in_database(email: str) -> UserInfo:
    """Check if the user exists in the database."" """
    # Use context manager for handling the database connection
    with get_db_connection() as db:
        cursor = db.cursor()
        query = """
            SELECT users.user_id, users.name, org_id, organisations.name
            FROM users
            LEFT JOIN organisations ON users.org_id = organisations.id
            WHERE email = %s
        """
        cursor.execute(query, (email,))
        user = cursor.fetchone()

        # Directly unpack values with defaults for None if user is None
        # Very pythonic :)
        user_id, name, org_id, organisation = user if user else (None, None, None, None)

        return UserInfo(user_id=user_id, name=name, org_id=org_id, organisation=organisation)


def process_user(
    organisation: str,
    username: str,
    user_email: str,
    access_token: str,
    refresh_token: str,
    expiry: int,
    token_type: str,
    scope: list,
) -> dict:
    """Process the user information obtained from Google."""

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Get the organisation ID or create one if it doesn't exist
        # Do this while so I don't repeat the select querry upon creation
        org_id = ""
        while not org_id:
            cursor.execute("select id from organisations where name = %s", (organisation,))
            res = cursor.fetchone()
            if not res:
                cursor.execute("insert into organisations (name) values (%s)", (organisation,))
                conn.commit()
            else:
                org_id = res[0]

        if isinstance(scope, Iterable):
            scope_str = " ".join(scope)
        else:
            raise ValueError(f"Scope must be an iterable, is {type(scope)}: {scope}")

        logging.debug(f"Expires in: {expiry}, type: {type(expiry)}")

        # Insert/Update User
        cursor.execute("SELECT user_id FROM users WHERE email = %s;", (user_email,))
        user = cursor.fetchone()
        if user:
            cursor.execute(
                """
                UPDATE users
                SET org_id = %s, name = %s, access_token = %s,
                refresh_token = %s, expiry = %s, token_type = %s,
                scope = %s WHERE email = %s;
                """,
                (
                    org_id,
                    username,
                    access_token,
                    refresh_token,
                    expiry,
                    token_type,
                    scope_str,
                    user_email,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO users (org_id, name, email, access_token, refresh_token, expiry,
                           token_type, scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
                (
                    org_id,
                    username,
                    user_email,
                    access_token,
                    refresh_token,
                    expiry,
                    token_type,
                    scope_str,
                ),
            )
        conn.commit()

    return {"name": username, "email": user_email, "organisation": organisation, "org_id": org_id}

slack_oauth = SlackOAuth()

@auth_bp.route('/auth/slack')
def slack_auth():
    return redirect(slack_oauth.get_auth_url())

@auth_bp.route('/auth/slack/callback')
def slack_callback():
    return slack_oauth.auth_callback()
