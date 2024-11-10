"""Application factory for the Flask app."""

import logging
import os
import sys
from flask import Flask, jsonify, render_template
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from flask_restx import Api
from flask_migrate import Migrate

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy_utils import database_exists, create_database
from werkzeug.middleware.proxy_fix import ProxyFix

from app.cli import init_db_command, seed_db_command

import sentry_sdk

from app.models import db, User
from app.routes.api.chat import chat_ns
from app.routes.api.conversation import conversation_ns
from app.routes.api.notifications import notifications_ns
from app.routes.admin import admin_bp
from app.routes.authentication import auth_bp
from app.routes.chat import chat_bp
from app.routes.integrations.googledrive import googledrive_bp
from app.routes.integrations.slack import slack_bp

from config import config


def prepare_database(app: Flask, migrate: Migrate, db: SQLAlchemy):
    """Prepare the database."""
    with app.app_context():
        # Create the database if it doesn't exist
        if not database_exists(app.config["SQLALCHEMY_DATABASE_URI"]):
            create_database(app.config["SQLALCHEMY_DATABASE_URI"])

        # Create the tables if they don't exist
        inspector = db.inspect(db.engine)
        if "user" not in inspector.get_table_names():
            db.create_all()

        # Run migrations if they haven't been run yet
        # upgrade()


def create_app(config_name: str = "default") -> Flask:
    """Create and configure the Flask application."""
    # set the SCARF_NO_ANALYTICS environment variable to true to disable analytics
    # (among possible others the unstructured library uses to track usage)
    os.environ["SCARF_NO_ANALYTICS"] = "true"

    # this is a print on purpose (not a logger statement) to show that the app is loading
    # get the git commit hash, branch name and first line of the commit message and print it out
    print("Loading the app...")
    logging.debug("Loading the app...")

    git_details = os.popen("git log --pretty=format:'%H %d %s' -n 1").read()
    print(f"Git details: {git_details}")
    logging.info(f"Git details: {git_details}")

    app = Flask(__name__)
    app.name = "lorelai"

    # Load configuration
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    # Initialize db
    db.init_app(app)

    # Initialize Flask-Migrate
    migrate = Migrate(app, db)
    migrate.init_app(app, db)

    prepare_database(app, migrate, db)

    # Initialize LoginManager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "chat.index"

    # Initialize JWT
    jwt = JWTManager(app)

    # Set up Sentry
    if app.config["SENTRY_DSN"]:
        sentry_sdk.init(
            dsn=app.config["SENTRY_DSN"],
            environment=app.config["SENTRY_ENVIRONMENT"],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
        logging.info("Sentry initialized in environment %s", app.config["SENTRY_ENVIRONMENT"])

    # Apply ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

    # Initialize Flask-RestX
    api = Api(
        app,
        version="1.0",
        title="Lorelai API",
        description="API documentation for Lorelai",
        doc="/swagger",
        prefix="/api",
    )

    # Register namespaces
    api.add_namespace(chat_ns)
    api.add_namespace(conversation_ns)
    api.add_namespace(notifications_ns)

    # Register blueprints
    app.register_blueprint(googledrive_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(slack_bp)

    # Set up user loader
    @login_manager.user_loader
    def load_user(user_id: str) -> User:
        return User.query.get(int(user_id))

    # Set up error handlers and other app-wide functions
    setup_error_handlers(app)
    setup_after_request(app)
    setup_jwt_handlers(jwt)

    setup_cli(app)

    return app


def setup_cli(app: Flask) -> None:
    """Set up the CLI for the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)


def setup_error_handlers(app: Flask) -> None:
    """Set up error handlers for the Flask app."""

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


def setup_after_request(app: Flask) -> None:
    """Set up after request handlers for the Flask app."""

    # Implement your after request handlers here
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
            "https://drive-thirdparty.googleusercontent.com/",
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

        # logging.info("Setting CSRF token")
        # response.set_cookie("csrf_token", value=generate_csrf(), secure=True, samesite="Strict")

        return response


def setup_jwt_handlers(jwt: JWTManager) -> None:
    """Set up JWT handlers for the Flask app."""

    @jwt.unauthorized_loader
    def custom_unauthorized_response(_err):
        """Handle unauthorized access."""
        logging.error("Unauthorized access: %s", _err)
        return jsonify({"msg": f"Unauthorized access: {_err}"}), 401

    @jwt.invalid_token_loader
    def custom_invalid_token_response(error_string):
        """Handle invalid token."""
        logging.error("Invalid token: %s", error_string)
        return jsonify({"msg": f"Invalid token: {error_string}"}), 401

    @jwt.expired_token_loader
    def custom_expired_token_response(jwt_header, jwt_payload):
        """Handle expired token."""
        logging.error("Expired token: %s", jwt_payload)
        return jsonify({"msg": f"Expired token: {jwt_payload}"}), 401

    @jwt.needs_fresh_token_loader
    def custom_needs_fresh_token_response(error_string):
        """Handle needs fresh token."""
        logging.error("Needs fresh token: %s", error_string)
        return jsonify({"msg": f"Needs fresh token: {error_string}"}), 401

    @jwt.revoked_token_loader
    def custom_revoked_token_response(error_string):
        """Handle revoked token."""
        logging.error("Revoked token: %s", error_string)
        return jsonify({"msg": f"Revoked token: {error_string}"}), 401
