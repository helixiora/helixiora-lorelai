"""Authentication module for the app."""

from flask import redirect, url_for, flash, request, jsonify
from flask_login import LoginManager, login_user, logout_user
from flask_dance.contrib.google import make_google_blueprint, google
from app.models import User, db
from functools import wraps
from app.helpers.users import validate_api_token

login_manager = LoginManager()
google_blueprint = make_google_blueprint(
    client_id="YOUR_GOOGLE_CLIENT_ID",
    client_secret="YOUR_GOOGLE_CLIENT_SECRET",
    scope=["profile", "email"],
)


@login_manager.user_loader
def load_user(user_id):
    """Load a user by their ID."""
    return User.query.get(int(user_id))


def init_auth(app):
    """Initialize authentication for the app."""
    login_manager.init_app(app)
    app.register_blueprint(google_blueprint, url_prefix="/login")

    @app.route("/login")
    def login():
        """Login with Google."""
        if not google.authorized:
            return redirect(url_for("google.login"))
        resp = google.get("/oauth2/v2/userinfo")
        if resp.ok:
            email = resp.json()["email"]
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(email=email)
                db.session.add(user)
                db.session.commit()
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))
        flash("Failed to log in.", "error")
        return redirect(url_for("index"))

    @app.route("/logout")
    def logout():
        """Logout the current user."""
        logout_user()
        flash("Logged out successfully.", "success")
        return redirect(url_for("index"))


def api_token_required(f):
    """Require an API token for access."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if token and token.startswith("Bearer "):
            token = token.split("Bearer ")[1]
            user = validate_api_token(token)
            if user:
                return f(user, *args, **kwargs)
        return jsonify({"error": "Invalid or missing API token"}), 401

    return decorated_function
