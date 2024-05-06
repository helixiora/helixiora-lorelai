#!/usr/bin/env python3

"""the main application file for the OAuth2 flow flask app"""

import logging
import os
import sys

from flask import Flask, flash, redirect, render_template, session, url_for
from google_auth_oauthlib.flow import Flow

# load blueprints
from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.chat import chat_bp
from app.utils import is_admin
from lorelai.utils import load_config

app = Flask(__name__)
# Get the log level from the environment variable
log_level = os.getenv("LOG_LEVEL", "INFO").upper()  # Ensure it's in uppercase to match constants

# Set the log level using the mapping, defaulting to logging.INFO if not found
app.logger.setLevel(logging.getLevelName(log_level))
logging_format = "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])"
logging.basicConfig(format=logging_format)

app.secret_key = "your_very_secret_and_long_random_string_here"

app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

# this is a print on purpose (not a logger statement) to show that the app is loading
print("Loading the app...")
logging.debug("Loading the app...")

# Allow OAuthlib to use HTTP for local testing only
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


# Improved index route using render_template
@app.route("/")
def index():
    """the index page

    Returns:
        string: the index page
    """
    # Load the Google OAuth2 secrets
    secrets = load_config("google")
    # check if all the required creds are present
    e_creds = [
        "client_id",
        "project_id",
        "client_secret",
        "redirect_uris",
    ]
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
        scopes=[
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/drive.readonly",
            "openid",
        ],
        redirect_uri=lorelaicreds["redirect_uri"],
    )

    if "google_id" in session:
        user_data = {
            # 'user_organization': session['organisation'],
            "user_email": session["email"],
            "is_admin": is_admin(session["google_id"]),
        }

        return render_template("index_logged_in.html", **user_data)

    try:
        authorization_url, state = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )
        session["state"] = state
        return render_template("index.html", auth_url=authorization_url)
    except RuntimeError as e:
        logging.debug(f"Error generating authorization URL: {e}")
        return render_template("error.html", error_message="Failed to generate login URL.")


@app.route("/js/<script_name>.js")
def serve_js(script_name):
    """the javascript endpoint"""
    return (
        render_template(f"js/{script_name}.js"),
        200,
        {"Content-Type": "application/javascript"},
    )


# Logout route
@app.route("/logout")
def logout():
    """the logout route"""
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("index"))


# Error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    """the error handler for 404 errors"""
    return render_template("404.html", e=e), 404


# Error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    """the error handler for 500 errors"""
    error_info = sys.exc_info()
    if error_info:
        error_message = str(error_info[1])  # Get the exception message
    else:
        error_message = f"An unknown error occurred. {e}"

    # Pass the error message to the template
    return render_template("500.html", error_message=error_message), 500


if __name__ == "__main__":
    print("Starting the app...")
    app.run(ssl_context=("cert.pem", "key.pem"))
