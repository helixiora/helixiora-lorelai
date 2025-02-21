"""Flask application factory."""

import logging
import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from flask_restx import Api, fields
from flask_jwt_extended import JWTManager
from datetime import timedelta

from app.models import User, db
from app.routes.api.v1.auth import auth_ns
from app.routes.api.v1.chat import chat_ns
from app.routes.api.v1.token import token_ns
from app.routes.api.v1.notifications import notifications_ns
from app.routes.api.v1.admin import admin_ns
from app.routes.api.v1.api_keys import api_keys_ns
from app.routes.api.v1.slack import slack_ns
from app.routes.api.v1.googledrive import googledrive_ns
from app.routes.api.v1.conversation import conversation_ns
from app.routes.api.v1.indexing import indexing_ns

from app.routes.authentication import auth_bp
from app.routes.chat import chat_bp
from app.routes.indexing import bp as indexing_bp
from app.routes.integrations.googledrive import googledrive_bp
from app.routes.integrations.slack import slack_bp
from app.routes.admin import admin_bp
from app.routes.notifications import notifications_bp

# Get git details
try:
    git_hash = os.popen("git rev-parse HEAD").read().strip()
    git_branch = os.popen("git rev-parse --abbrev-ref HEAD").read().strip()
    git_details = f"{git_hash}  {git_branch}"
except Exception as e:
    git_details = f"Error getting git details: {e}"
logging.info("Git details: %s", git_details)


def create_app(config=None):
    """Create Flask application."""
    app = Flask(__name__)

    # Load configuration
    if config is None:
        app.config.from_object("config.Config")
    else:
        app.config.update(config)

    # Initialize extensions
    CORS(app)
    db.init_app(app)
    Migrate(app, db)

    # Register CLI commands
    from app.cli import init_db_command, seed_db_command

    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)

    # Security headers
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        cross_origin_opener_policy = "same-origin"

        connect_src = [
            "'self'",
            "https://accounts.google.com/gsi/",
            "https://accounts.google.com/.well-known/",
            "https://oauth2.googleapis.com/",
            "https://o4507884621791232.ingest.de.sentry.io/api/",
            "https://apis.google.com/",
            "https://www.google.com/",
            "https://docs.google.com/",
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
            "https://docs.google.com/picker/",
        ]

        img_src = [
            "'self'",
            "'unsafe-inline'",
            "data:",
            "blob:",  # Allow blob URLs for images
            "https://accounts.google.com/gsi/",
            "https://csi.gstatic.com/csi",
            "https://cdn.datatables.net/",
            "https://platform.slack-edge.com/",
            "https://drive-thirdparty.googleusercontent.com/",
            "https://www.google.com/",
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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = content_security_policy

        return response

    # Initialize JWT
    jwt = JWTManager(app)
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
    app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
    app.config["JWT_COOKIE_SECURE"] = True
    app.config["JWT_COOKIE_CSRF_PROTECT"] = True
    app.config["JWT_COOKIE_SAMESITE"] = "Strict"

    # Initialize Login Manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "chat.index"

    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID."""
        return User.query.get(int(user_id))

    # Add template context processor
    @app.context_processor
    def inject_is_admin():
        """Inject is_admin variable into all templates."""
        return {"is_admin": current_user.is_admin() if current_user.is_authenticated else False}

    # Register blueprints
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(googledrive_bp)
    app.register_blueprint(slack_bp)
    app.register_blueprint(indexing_bp)

    # Initialize API
    authorizations = {
        "Bearer Auth": {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Add a JWT with ** Bearer &lt;JWT&gt; ** to authorize",
        },
    }

    api = Api(
        app,
        version="1.0",
        title="Lorelai API",
        description="""
        The Lorelai API provides programmatic access to Lorelai's features and data.

        ## Authentication
        All API endpoints require authentication using either:
        - JWT tokens in the Authorization header
        - API keys for programmatic access

        ## Rate Limiting
        API calls are rate limited based on your subscription tier.

        ## Errors
        The API uses standard HTTP response codes:
        - 2xx: Success
        - 4xx: Client errors (invalid input, unauthorized)
        - 5xx: Server errors

        Error responses include a message field with details.
        """,
        doc="/swagger",
        authorizations=authorizations,
        security="Bearer Auth",
        prefix="/api/v1",
        validate=True,  # Enable request validation
        ordered=True,  # Keep the order of fields in models
        default_mediatype="application/json",
        default="Lorelai API",
        license="Proprietary",
        contact="contact@helixiora.com",
        contact_url="https://lorelai.app",
        terms_url="https://lorelai.app/terms-of-service-for-lorelai/",
    )

    # Add global response definitions
    api.response(
        400,
        "Validation Error",
        api.model(
            "Error",
            {
                "message": fields.String(description="Error message"),
                "errors": fields.Raw(description="Detailed validation errors"),
            },
        ),
    )
    api.response(
        401,
        "Unauthorized",
        api.model("Error", {"message": fields.String(description="Authentication required")}),
    )
    api.response(
        403,
        "Forbidden",
        api.model("Error", {"message": fields.String(description="Insufficient permissions")}),
    )
    api.response(
        404,
        "Not Found",
        api.model("Error", {"message": fields.String(description="Resource not found")}),
    )
    api.response(
        429,
        "Too Many Requests",
        api.model(
            "Error",
            {
                "message": fields.String(description="Rate limit exceeded"),
                "retry_after": fields.Integer(description="Retry after seconds"),
            },
        ),
    )
    api.response(
        500,
        "Server Error",
        api.model("Error", {"message": fields.String(description="Internal server error")}),
    )

    # Add global request parsers
    pagination_parser = api.parser()
    pagination_parser.add_argument("page", type=int, location="args", default=1, help="Page number")
    pagination_parser.add_argument(
        "per_page", type=int, location="args", default=20, help="Items per page"
    )
    pagination_parser.add_argument("sort", type=str, location="args", help="Sort field")
    pagination_parser.add_argument(
        "order", type=str, location="args", choices=("asc", "desc"), help="Sort order"
    )

    # Add namespaces
    api.add_namespace(admin_ns)
    api.add_namespace(api_keys_ns)
    api.add_namespace(auth_ns)
    api.add_namespace(chat_ns)
    api.add_namespace(conversation_ns)
    api.add_namespace(googledrive_ns)
    api.add_namespace(indexing_ns)
    api.add_namespace(notifications_ns)
    api.add_namespace(slack_ns)
    api.add_namespace(token_ns)

    # Error handlers
    @app.errorhandler(401)
    def unauthorized(error):
        """Handle unauthorized access."""
        logging.error("Unauthorized access attempt - %s", error)
        return jsonify({"message": "Unauthorized access"}), 401

    @app.errorhandler(403)
    def forbidden(error):
        """Handle forbidden access."""
        logging.error("Forbidden access attempt - %s", error)
        return jsonify({"message": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(error):
        """Handle not found error."""
        logging.error("Resource not found - %s", error)
        return jsonify({"message": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle internal server error."""
        logging.error("Internal server error - %s", error)
        return jsonify({"message": "Internal server error"}), 500

    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        """Handle unauthorized JWT access."""
        logging.error("Unauthorized access attempt - %s", callback)
        return jsonify({"message": "Unauthorized access"}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(callback):
        """Handle invalid JWT token."""
        logging.error("Invalid token - %s", callback)
        return jsonify({"message": "Invalid token"}), 401

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_data):
        """Handle expired JWT token."""
        logging.error("Token expired - %s", jwt_data)
        return jsonify({"message": "Token has expired"}), 401

    @jwt.needs_fresh_token_loader
    def token_not_fresh_callback(jwt_header, jwt_data):
        """Handle non-fresh JWT token."""
        logging.error("Token is not fresh - %s", jwt_data)
        return jsonify({"message": "Fresh token required"}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_data):
        """Handle revoked JWT token."""
        logging.error("Token has been revoked - %s", jwt_data)
        return jsonify({"message": "Token has been revoked"}), 401

    @jwt.user_lookup_error_loader
    def user_lookup_error_callback(jwt_header, jwt_data):
        """Handle JWT user lookup error."""
        logging.error("Error loading user - %s", jwt_data)
        return jsonify({"message": "Error loading user"}), 401

    @jwt.token_verification_failed_loader
    def token_verification_failed_callback(jwt_header, jwt_data):
        """Handle JWT token verification failure."""
        logging.error("Token verification failed - %s", jwt_data)
        return jsonify({"message": "Token verification failed"}), 401

    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_data):
        """Check if JWT token is in blocklist."""
        # TODO: Implement actual blocklist check if needed
        return False

    @jwt.additional_claims_loader
    def add_claims_to_access_token(identity):
        """Add claims to JWT access token."""
        user = User.query.get(identity)
        if user:
            return {
                "roles": [role.name for role in user.roles],
                "org_id": user.org_id,
                "org_name": user.organisation.name,
            }
        return {}

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        """Get user identity for JWT."""
        return user.id if isinstance(user, User) else user

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """Look up user from JWT data."""
        identity = jwt_data["sub"]
        return User.query.get(identity)

    return app
