#!/usr/bin/env python3

"""Main application file for the OAuth2 flow flask app."""

import logging
import os
import sys

import mysql.connector
from flask import Flask, g, redirect, render_template, request, session, url_for

from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.chat import chat_bp
from app.routes.google.auth import googledrive_bp
from app.utils import (
    get_db_connection,
    is_admin,
    perform_health_checks,
    user_is_logged_in,
)
from lorelai.utils import load_config

# this is a print on purpose (not a logger statement) to show that the app is loading
print("Loading the app...")
logging.debug("Loading the app...")

app = Flask(__name__)
# Get the log level from the environment variable
log_level = os.getenv("LOG_LEVEL", "INFO").upper()  # Ensure it's in uppercase to match constants

# Set the log level using the mapping, defaulting to logging.INFO if not found
app.logger.setLevel(logging.getLevelName(log_level))
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
logging.basicConfig(format=logging_format)

lorelai_settings = load_config("lorelai")
app.secret_key = lorelai_settings["secret_key"]

app.register_blueprint(googledrive_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)

db_settings = load_config("db")
dbname = db_settings["database"]
# check if the database can be connected to
db_exists = False
try:
    db = get_db_connection()
    db_exists = True
except mysql.connector.Error as e:
    if e.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
        print(f"Database does not exist: {e}")
        app.config["LORELAI_SETUP"] = True
    else:
        raise

if db_exists:
    # run startup health checks. If there is a dependent service that is not running, we want to
    # know it asap and stop the app from running
    logging.debug("Running startup checks...")
    errors = perform_health_checks()
    if errors:
        sys.exit(f"Startup checks failed: {errors}")

# Allow OAuthlib to use HTTP for local testing only
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

# Flagging success by displaying the app's address
logging.debug("URL Map: %s", app.url_map)
logging.debug("App config: %s", app.config)
logging.info(
    "Application loaded successfully. Running at %s",
    app.config.get(
        "BASE_URL", "http://" + os.getenv("HOST", "localhost") + ":" + os.getenv("PORT", "5000")
    ),
)


# Improved index route using render_template
@app.route("/")
def index():
    """Return the index page.

    Returns
    -------
        string: the index page
    """
    logging.info("Index route")

    if app.config.get("LORELAI_SETUP"):
        # redirect to /admin/setup if the app is not set up
        logging.info("App is not set up. Redirecting to /admin/setup")
        return redirect(url_for("admin.setup"))

    # if the user_id is in the session, the user is logged in
    # render the index_logged_in page
    if user_is_logged_in(session):
        is_admin_status = is_admin(session["user_id"])
        data_sources_list = lorelai_settings["data_sources"]
        # session["role"] = get_user_role(session["email"])
        return render_template(
            "index_logged_in.html",
            user_email=session["user_email"],
            is_admin=is_admin_status,
            datasource_list=data_sources_list,
        )

    # if we're still here, there was no user_id in the session meaning we are not logged in
    # render the front page with the google client id
    # if the user clicks login from that page, the javascript function `onGoogleCredentialResponse`
    # will handle the login using the /login route in auth.py.
    # Depending on the output of that route, it's redirecting to /register if need be
    secrets = load_config("google")
    return render_template("index.html", google_client_id=secrets["client_id"])


@app.route("/js/<script_name>.js")
def serve_js(script_name):
    """Return the javascript file dynamically.

    Parameters
    ----------
    script_name : str
        The name of the script to serve

    Returns
    -------
        tuple: the javascript file, the status code, and the content type
    """
    return (
        render_template(f"js/{script_name}.js"),
        200,
        {"Content-Type": "application/javascript"},
    )


# health check route
@app.route("/health")
def health():
    """Serve the health check route.

    Returns
    -------
        string: the health check status
    """
    checks = perform_health_checks()
    if checks:
        return checks, 500
    return "OK", 200


# Error handler for 404
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return render_template("404.html", e=e), 404


# Error handler for 500
@app.errorhandler(500)
def internal_server_error(e):
    """Handle 500 errors."""
    error_info = sys.exc_info()
    if error_info:
        error_message = str(error_info[1])  # Get the exception message
    else:
        error_message = f"An unknown error occurred. {e}"

    # Pass the error message to the template
    return render_template("500.html", error_message=error_message), 500


@app.before_request
def before_request():
    """Load the features before every request."""
    logging.debug("Before request: " + request.url)
    g.features = load_config("features")


@app.after_request
def set_security_headers(response):
    """Set the security headers for the response."""
    cross_origin_opener_policy = "unsafe-none"

    connect_src = ["'self'", "https://accounts.google.com/gsi/"]

    frame_src = ["'self'", "https://accounts.google.com/gsi/", "https://accounts.google.com/"]

    img_src = [
        "'self'",
        "'unsafe-inline'",
        "data:",
        "https://accounts.google.com/gsi/",
        "https://csi.gstatic.com/csi",
    ]

    script_src_elem = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/client",
        "https://code.jquery.com/jquery-3.5.1.min.js",
        "https://apis.google.com/js/api.js",
        "https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js",
        "https://apis.google.com/_/scs/abc-static/_/js/k=gapi.lb.en.6jI6mC1Equ4.O/m=auth/rt=j/sv=1/d=1/ed=1/am=AAAQ/rs=AHpOoo-79kMK-M6Si-J0E_6fI_9RBHBrwQ/cb=gapi.loaded_0",
        "https://apis.google.com/_/scs/abc-static/_/js/k=gapi.lb.en.6jI6mC1Equ4.O/m=picker/exm=auth/rt=j/sv=1/d=1/ed=1/am=AAAQ/rs=AHpOoo-79kMK-M6Si-J0E_6fI_9RBHBrwQ/cb=gapi.loaded_1",
        "https://cdn.tailwindcss.com/",
        "https://code.jquery.com/jquery-3.5.1.slim.min.js",
        "https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js",
        "https://cdn.datatables.net/1.11.3/js/jquery.dataTables.min.js",
        "https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js",
    ]

    font_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/webfonts/",
        "https://fonts.gstatic.com/s/",
    ]

    script_src = ["'self'", "'unsafe-inline'", "https://accounts.google.com/gsi/"]

    style_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/style",
        "https://cdn.datatables.net/1.11.3/css/jquery.dataTables.min.css",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
        "https://cdn.jsdelivr.net/npm/@popperjs/core@2.5.4/dist/umd/popper.min.js",
        "https://fonts.googleapis.com/css",
        "https://fonts.googleapis.com/css2",
        "https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css",
    ]

    default_src = ["'self'", "https://accounts.google.com/gsi/"]

    content_security_policy = (
        f"connect-src {' '.join(connect_src)}; "
        f"frame-src {' '.join(frame_src)}; "
        f"img-src {' '.join(img_src)}; "
        f"script-src-elem {' '.join(script_src_elem)}; "
        f"font-src {' '.join(font_src)}; "
        f"script-src {' '.join(script_src)}; "
        f"style-src {' '.join(style_src)}; "
        f"default-src {' '.join(default_src)};"
    )

    response.headers["Cross-Origin-Opener-Policy"] = cross_origin_opener_policy
    response.headers["Content-Security-Policy"] = content_security_policy

    return response


if __name__ == "__main__":
    logging.debug("Starting the app...")
    app.run(ssl_context=("cert.pem", "key.pem"))
