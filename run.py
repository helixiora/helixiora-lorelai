#!/usr/bin/env python3

"""Main application file for the OAuth2 flow flask app."""

import logging
import os
import sys

import mysql.connector
from flask import (
    Flask,
    g,
    redirect,
    render_template,
    render_template_string,
    request,
    session,
    url_for,
)
from ulid import ULID

from app.routes.admin import admin_bp
from app.routes.auth import auth_bp
from app.routes.chat import chat_bp
from app.routes.google.auth import googledrive_bp
from app.utils import (
    check_flyway,
    get_datasources_name,
    get_db_connection,
    is_admin,
    is_super_admin,
    perform_health_checks,
    run_flyway_migrations,
    user_is_logged_in,
)
from lorelai.utils import load_config

# this is a print on purpose (not a logger statement) to show that the app is loading
# get the git commit hash, branch name and first line of the commit message and print it out
print("Loading the app...")
logging.debug("Loading the app...")

git_details = os.popen("git log --pretty=format:'%H %d %s' -n 1").read()
print(f"Git details: {git_details}")
logging.info(f"Git details: {git_details}")

# if we're running the app in a container, gather information about the container
if os.path.exists("/proc/self/cgroup"):
    container_id = os.popen(
        "cat /proc/self/cgroup | grep 'docker' | sed 's/^.*\///' | tail -n1"
    ).read()
else:
    container_id = None
container_id = container_id.strip() if container_id else "Not in a container"
print(f"Container ID: {container_id}")
logging.info(f"Container ID: {container_id}")

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
    logging.info("Database connection successful, checking flyway version...")
    flyway_ok, error = check_flyway()
    # if the flyway is not ok, and the error contains 'not up to date with last migration'
    # we will run the migrations
    if not flyway_ok and "not up to date with" in error:
        logging.info(f"Flyway not OK ({error}). Running flyway migrations...")
        success, log = run_flyway_migrations(
            host=db_settings["host"],
            database=db_settings["database"],
            user=db_settings["user"],
            password=db_settings["password"],
        )

        if not success:
            logging.error(f"Flyway migrations failed: {log}")
            sys.exit("Flyway migrations failed, exiting")
        else:
            logging.info("Flyway migrations successful")
    else:
        logging.info(f"Flyway is ok ({flyway_ok}) and up to date ({error})")

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


def super_admin_panel_content() -> list:
    """Return the content for the super admin panel.

    Returns
    -------
        list: the content for the super admin panel
    """
    session_variables = ["Session variables:"]
    for key, value in session.items():
        session_variables.append(f"- {key}: {value}")

    return session_variables


# Improved index route using render_template
@app.route("/")
def index():
    """Return the index page.

    Returns
    -------
        string: the index page
    """
    logging.debug("Index route")

    if app.config.get("LORELAI_SETUP"):
        # redirect to /admin/setup if the app is not set up
        logging.info("App is not set up. Redirecting to /admin/setup")
        return redirect(url_for("admin.setup"))

    # if the user_id is in the session, the user is logged in
    # render the index_logged_in page
    if user_is_logged_in(session):
        # have to setup thread_id for the chat history feature. in UI we have to create button for
        # new
        # thread which replace current session "thread_id"
        if "thread_id" not in session:
            # ULID creates chronological string, which make inserting faster as they are sequential
            session["thread_id"] = str(ULID().to_uuid())
        datasources = get_datasources_name()

        lorelai_settings = load_config("lorelai")

        is_admin_status = is_admin(session["user_id"])

        if is_super_admin(session["user_id"]):
            super_admin_content = super_admin_panel_content()
        else:
            super_admin_content = []

        return render_template(
            "index_logged_in.html",
            user_email=session["user_email"],
            is_admin=is_admin_status,
            datasource_list=datasources,
            super_admin_content=super_admin_content,
            support_portal=lorelai_settings["support_portal"],
            support_email=lorelai_settings["support_email"],
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
    # cross_origin_opener_policy = "same-origin"
    cross_origin_opener_policy = "same-origin-allow-popups"

    connect_src = [
        "'self'",
        "https://accounts.google.com/gsi/",
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
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
    ]

    script_src_elem = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/client",
        "https://apis.google.com/",
        "https://cdn.datatables.net/",
        "https://cdn.jsdelivr.net/",
        "https://cdn.tailwindcss.com/",
        "https://code.jquery.com/",
        "https://stackpath.bootstrapcdn.com/bootstrap/",
    ]

    font_src = [
        "'self'",
        "'unsafe-inline'",
        "https://accounts.google.com/gsi/",
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/webfonts/",
        "https://fonts.gstatic.com/s/",
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
    next_url = request.args.get("next") or url_for("index")
    return render_template_string(
        """
        <script>
            alert("You are not authorized to access this page.");
            window.location.href = "{{ next_url }}";
        </script>
    """,
        next_url=next_url,
    )


if __name__ == "__main__":
    logging.debug("Starting the app...")
    app.run(ssl_context=("cert.pem", "key.pem"))
