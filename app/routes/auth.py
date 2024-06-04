"""Routes for user authentication."""

import logging

from google.auth.transport import requests

from flask import blueprints, redirect, render_template, request, session, url_for, jsonify
from google.oauth2 import id_token

from app.utils import get_db_connection, is_admin

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


# @auth_bp.route("/register", methods=["GET", "POST"])
# def register():
#     """Register a new user."""
#     if request.method == "GET":
#         email = session.get("oauth_data", {}).get("email")
#         name = session.get("oauth_data", {}).get("name")

#         return render_template("register.html", email=email, name=name)

#     # Process the registration form submission
#     registration_info = request.form

#     # Combine OAuth data with registration form data
#     oauth_data = session.pop("oauth_data", {})

#     logging.debug(f"Registration info: {registration_info}")
#     logging.debug(f"OAuth data: {oauth_data}")

#     username = registration_info["name"]
#     user_email = registration_info["email"]
#     organisation = registration_info["organisation"]
#     access_token = session.pop("access_token", None)
#     refresh_token = session.pop("refresh_token", None)
#     expiry = session.pop("expiry", None)
#     token_type = session.pop("token_type", None)
#     scope = session.pop("scope", None)

#     user_info = process_user(
#         organisation,
#         username,
#         user_email,
#         access_token,
#         refresh_token,
#         expiry,
#         token_type,
#         scope,
#     )

#     # logging.info(f"Creating user: {registration_info} / {oauth_data}")

#     # Log the user in (pseudo code)
#     login_user(
#         user_info["name"],
#         user_info["email"],
#         user_info["org_id"],
#         user_info["organisation"],
#     )
#     return redirect(url_for("index"))


@auth_bp.route("/login", methods=["POST"])
def login():
    try:
        # Logging request details
        log_request_details(request)

        # Ensure content type is JSON
        if request.content_type != "application/json":
            return jsonify({"error": "Invalid content type"}), 400

        data = request.get_json()  # Access JSON data from request

        # Log received JSON data
        logging.info("Received JSON data: %s", data)

        id_token_received = data.get("credential")

        # Verify the ID token using Google's Identity Verification API
        idinfo = id_token.verify_oauth2_token(id_token_received, requests.Request())
        validate_id_token(idinfo)

        logging.info("Info from token: %s", idinfo)
        user_email = idinfo["email"]

        # Get a database connection
        db_conn = get_db_connection()

        # Check if the user already exists in the database
        user_id = get_user_id_by_email(db_conn, user_email)

        if not user_id:
            # If the user does not exist, create a new user and save it to the database
            logging.info("Creating a new user in the database")
            create_user_in_database(db_conn, user_email)
        else:
            logging.info("User already exists in the database")

        session["user_email"] = user_email
        session["user_id"] = user_id

        # Respond with a success message
        return jsonify({"message": "User authenticated successfully"}), 200

    except ValueError as e:
        # Invalid token
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        # Other errors
        logging.exception("An error occurred: %s", str(e))
        return jsonify({"error": "An error occurred"}), 500


def log_request_details(request):
    # Log the raw request, content type, and headers
    logging.info("Request: %s", request)
    logging.info("Request content type: %s", request.content_type)
    logging.info("Request headers: %s", request.headers)


def validate_id_token(idinfo):
    # Verify the issuer
    if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
        raise ValueError("Wrong issuer.")

    # Check if the user's email is verified
    if not idinfo.get("email_verified"):
        raise ValueError("Email not verified")


def get_user_id_by_email(db_conn, email):
    # Check if the user already exists in the database
    cursor = db_conn.cursor()
    cursor.execute("SELECT user_id FROM user WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    return user


def create_user_in_database(db_conn, email, access_token, refresh_token):
    # Create a new user and save it to the database
    cursor = db_conn.cursor()
    cursor.execute(
        "INSERT INTO user (email, access_token, refresh_token) VALUES (%s, %s, %s)",
        (email, access_token, refresh_token),
    )
    db_conn.commit()
    cursor.close()


# Logout route
@auth_bp.route("/logout", methods=["POST"])
def logout():
    # Clear session
    session.clear()

    # Clear access_token and refresh_token in the database

    # Get a database connection
    db_conn = get_db_connection()

    # Update access_token and refresh_token to NULL for the user in the database
    cursor = db_conn.cursor()
    cursor
    cursor.execute(
        "UPDATE user SET access_token = NULL, refresh_token = NULL WHERE email = %s",
        (session.get("user_email"),),
    )
    db_conn.commit()
    cursor.close()

    # Redirect to index or any other appropriate page
    return redirect(url_for("index"))


# @auth_bp.route("/oauth2callback")
# def oauth_callback():
#     """OAuth2 callback route."""
#     logging.info("oauth_callback invoked")

#     secrets = load_config("google")
#     lorelaicreds = load_config("lorelai")

#     client_config = {
#         "web": {
#             "client_id": secrets["client_id"],
#             "project_id": secrets["project_id"],
#             "auth_uri": "https://accounts.google.com/o/oauth2/auth",
#             "token_uri": "https://oauth2.googleapis.com/token",
#             "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
#             "client_secret": secrets["client_secret"],
#             "redirect_uris": secrets["redirect_uris"],
#         }
#     }

#     flow = Flow.from_client_config(
#         client_config=client_config,
#         scopes=[
#             "https://www.googleapis.com/auth/userinfo.profile",
#             "https://www.googleapis.com/auth/userinfo.email",
#             "https://www.googleapis.com/auth/drive.readonly",
#             "openid",
#         ],
#         redirect_uri=lorelaicreds["redirect_uri"],
#     )

#     # Ensure state parameter is correct
#     if 'state' not in session:
#         logging.error("State not found in session")
#         return "State not found in session", 400

#     if 'state' not in request.args:
#         logging.error(f"State not found in request args: {request.args}")
#         return f"State not found in request args: {request.args}", 400

#     if session['state'] != request.args['state']:
#         logging.error("State does not match!")
#         return "State does not match!", 400

#     try:
#         flow.fetch_token(authorization_response=request.url)
#     except Exception as e:
#         logging.error(f"Error fetching token: {e}")
#         return f"Error fetching token: {e}", 400

#     credentials = flow.credentials
#     request_session = google.auth.transport.requests.Request()

#     try:
#         id_info = id_token.verify_oauth2_token(
#             id_token=credentials.id_token,
#             request=request_session,
#             audience=client_config["web"]["client_id"],
#         )
#     except ValueError as e:
#         logging.error(f"Invalid token: {e}")
#         return f"Invalid token: {e}", 400

#     logging.debug(f"id_info: {id_info}")
#     logging.debug(f"credentials: {credentials}")

#     # Use context manager for handling the database connection
#     email = id_info["email"]

#     with get_db_connection() as db:
#         cursor = db.cursor()
#         query = """
#             SELECT users.user_id, users.name, org_id, organisations.name
#             FROM users
#             LEFT JOIN organisations ON users.org_id = organisations.id
#             WHERE email = %s
#         """
#         cursor.execute(query, (email,))
#         user = cursor.fetchone()

#         # Directly unpack values with defaults for None if user is None
#         # Very pythonic :)
#         user_id, name, org_id, organisation = user if user else (None, None, None, None)

#     userid, name, orgid, organisation = check_user_in_database()
#     email = id_info["email"]

#     if not userid:
#         session["access_token"] = credentials.token
#         session["refresh_token"] = credentials.refresh_token
#         session["expiry"] = credentials.expiry
#         session["token_type"] = "Bearer"
#         session["scope"] = credentials.scopes
#         session["oauth_data"] = id_info

#         return redirect(url_for("auth.register"))

#     session["google_id"] = email
#     session["name"] = name
#     session["email"] = email
#     session["org_id"] = org_id
#     session["organisation"] = organisation

#     return redirect(url_for("index"))


# def process_user(
#     organisation: str,
#     username: str,
#     user_email: str,
#     access_token: str,
#     refresh_token: str,
#     expiry: int,
#     token_type: str,
#     scope: list,
# ) -> dict:
#     """Process the user information obtained from Google."""

#     with get_db_connection() as conn:
#         cursor = conn.cursor()
#         # Get the organisation ID or create one if it doesn't exist
#         # Do this while so I don't repeat the select querry upon creation
#         org_id = ""
#         while not org_id:
#             cursor.execute("select id from organisations where name = %s", (organisation,))
#             res = cursor.fetchone()
#             if not res:
#                 cursor.execute("insert into organisations (name) values (%s)", (organisation,))
#                 conn.commit()
#             else:
#                 org_id = res[0]

#         if isinstance(scope, Iterable):
#             scope_str = " ".join(scope)
#         else:
#             raise ValueError(f"Scope must be an iterable, is {type(scope)}: {scope}")

#         logging.debug(f"Expires in: {expiry}, type: {type(expiry)}")

#         # Insert/Update User
#         cursor.execute("SELECT user_id FROM users WHERE email = %s;", (user_email,))
#         user = cursor.fetchone()
#         if user:
#             cursor.execute(
#                 """
#                 UPDATE users
#                 SET org_id = %s, name = %s, access_token = %s,
#                 refresh_token = %s, expiry = %s, token_type = %s,
#                 scope = %s WHERE email = %s;
#                 """,
#                 (
#                     org_id,
#                     username,
#                     access_token,
#                     refresh_token,
#                     expiry,
#                     token_type,
#                     scope_str,
#                     user_email,
#                 ),
#             )
#         else:
#             cursor.execute(
#                 """
#                 INSERT INTO users (org_id, name, email, access_token, refresh_token, expiry,
#                            token_type, scope)
#                 VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
#             """,
#                 (
#                     org_id,
#                     username,
#                     user_email,
#                     access_token,
#                     refresh_token,
#                     expiry,
#                     token_type,
#                     scope_str,
#                 ),
#             )
#         conn.commit()

#     return {
#         "name": username,
#         "email": user_email,
#         "organisation": organisation,
#         "org_id": org_id,
#     }
