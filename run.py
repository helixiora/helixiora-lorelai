#!/usr/bin/env python3

"""Main application file for the OAuth2 flow flask app."""

import logging
import os
import sys


import sentry_sdk

import app.helpers.notifications
from app.helpers.database import (
    perform_health_checks,
)

from flask import (
    Flask,
    g,
    render_template,
    render_template_string,
    request,
    url_for,
)
from flask_login import LoginManager

from authlib.integrations.flask_client import OAuth

from flask_wtf.csrf import generate_csrf

from app.routes.admin import admin_bp
from app.routes.authentication import auth_bp
from app.routes.chat import chat_bp
from app.routes.slack.authorization import slack_bp
from app.routes.google.authorization import googledrive_bp

from app.models import db, User
from lorelai.utils import load_config

from werkzeug.middleware.proxy_fix import ProxyFix

# this is a print on purpose (not a logger statement) to show that the app is loading
# get the git commit hash, branch name and first line of the commit message and print it out
print("Loading the app...")
logging.debug("Loading the app...")

git_details = os.popen("git log --pretty=format:'%H %d %s' -n 1").read()
print(f"Git details: {git_details}")
logging.info(f"Git details: {git_details}")

sentry = load_config("sentry")
sentry_sdk.init(
    dsn=sentry["dsn"],
    environment=sentry.get("environment", "unknown environment"),
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
)

app = Flask(__name__)

# adjust the app name to be lorelai
app.name = "lorelai"

# adjust the location of the templates to be in the app folder
app.template_folder = "app/templates"

# adjust the location of the static folder to be in the app folder
app.static_folder = "app/static"


# Initialize SQLAlchemy with the app
db_settings = load_config("db")

SQLALCHEMY_DATABASE_URI = f"mysql+mysqlconnector://{db_settings['user']}:{db_settings['password']}@{db_settings['host']}/{db_settings['database']}"
app.config["SQLALCHEMY_DATABASE_URI"] = SQLALCHEMY_DATABASE_URI

db.init_app(app)

# Apply ProxyFix to handle X-Forwarded-* headers
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

# Get the log level from the environment variable
log_level = os.getenv("LOG_LEVEL", "INFO").upper()  # Ensure it's in uppercase to match constants

# set up login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "chat.index"

oauth = OAuth(app)

# Set the log level using the mapping, defaulting to logging.INFO if not found
app.logger.setLevel(logging.getLevelName(log_level))
logging_format = os.getenv(
    "LOG_FORMAT",
    "%(levelname)s - %(asctime)s: %(message)s : (Line: %(lineno)d [%(filename)s])",
)
logging.basicConfig(format=logging_format)

lorelai_settings = load_config("lorelai")
app.secret_key = lorelai_settings["secret_key"]
app.config["SECRET_KEY"] = lorelai_settings["secret_key"]

app.register_blueprint(googledrive_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(slack_bp)

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


# Move the health check inside a function that will be called after the app is fully initialized
def run_health_checks():
    """Run the health checks."""
    with app.app_context():
        errors = perform_health_checks()
        if errors:
            sys.exit(f"Startup checks failed: {errors}")


@login_manager.user_loader
def load_user(user_id):
    """Load the user from the database."""
    return User.query.get(int(user_id))


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
    g.features = load_config("features")


@app.after_request
def set_security_headers(response):
    """Set the security headers for the response."""
    cross_origin_opener_policy = "same-origin"

    connect_src = [
        "'self'",
        "https://accounts.google.com/gsi/",
        "https://oauth2.googleapis.com/",
        "https://o4507884621791232.ingest.de.sentry.io/api/",
    ]

    worker_src = [
        "'self'",
        "https://o4507884621791232.ingest.de.sentry.io/api/",
        "blob:",  # Add this line to allow blob URLs for workers
    ]

    frame_src = [
        "'self'",
        "https://accounts.google.com/gsi/",
        "https://accounts.google.com/",
        "https://content.googleapis.com/",
        "https://docs.google.com/",
    ]

    img_src = [
        "'self'",
        "'unsafe-inline'",
        "data:",
        "https://accounts.google.com/gsi/",
        "https://csi.gstatic.com/csi",
        "https://cdn.datatables.net/",
        "https://platform.slack-edge.com/",
    ]

    script_src_elem = [
        "'self'",
        "'unsafe-inline'",
        "https://js-de.sentry-cdn.com/",
        "https://browser.sentry-cdn.com/",
        "https://accounts.google.com/gsi/client",
        "https://apis.google.com/",
        "https://cdn.datatables.net/",
        "https://cdn.jsdelivr.net/",
        "https://code.jquery.com/",
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/",
        "https://unpkg.com/@popperjs/",
    ]

    font_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/",
        "https://fonts.gstatic.com/s/",
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/",
    ]

    script_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/",
        "https://apis.google.com/js/api.js",
        "https://apis.google.com/",
    ]

    style_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/style",
        "https://cdn.datatables.net/",
        "https://cdn.jsdelivr.net/npm/@popperjs/",
        "https://cdn.jsdelivr.net/npm/intro.js@8.0.0-beta.1/",
        "https://fonts.googleapis.com/css",
        "https://fonts.googleapis.com/css2",
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/",
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/",
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
        f"worker-src {' '.join(worker_src)}; "
        f"default-src {' '.join(default_src)};"
    )

    response.headers["Cross-Origin-Opener-Policy"] = cross_origin_opener_policy
    response.headers["Content-Security-Policy"] = content_security_policy

    response.set_cookie("csrf_token", value=generate_csrf(), secure=True, samesite="Strict")

    return response


@app.route("/unauthorized")
def unauthorized():
    """
    Handle unauthorized access by showing a pop-up alert and redirecting to the previous page.

    This route is triggered when a user attempts to access a protected page without the
    required roles. It shows a JavaScript alert informing the user that they are not authorized,
    and then redirects them to the page they came from (if available), or to the home page.

    Query Parameters:
        next (str): The URL to redirect to after displaying the alert. Defaults to the home page.

    Returns
    -------
        A rendered HTML string containing a JavaScript alert and redirection script.
    """
    next_url = request.args.get("next") or url_for("chat.index")
    return render_template_string(
        """
        <script>
            alert("You are not authorized to access this page.");
            window.location.href = "{{ next_url }}";
        </script>
    """,
        next_url=next_url,
    )


@app.route("/org_exists")
def org_exists():
    """
    Display an alert indicating that the organization name already exists and return the user to the previous page.

    This route is typically used to notify the user that the organization name they are attempting to use already exists
    in the database. After showing the alert, the user is redirected back to the page they were on before attempting to
    create the organization with the duplicate name.

    Returns
    -------
        str: A rendered template containing a script to show an alert and navigate back to the previous page.
    """  # noqa: E501
    return render_template_string(
        """
        <script>
            alert("Organisation name already exists, please create different organisation name. If you want to be part of existing organisation please contact organisation admin for invite");
            window.history.back();
        </script>
    """  # noqa: E501
    )


if __name__ == "__main__":
    run_health_checks()  # Run health checks before starting the app
    app.run(ssl_context=("cert.pem", "key.pem"))
