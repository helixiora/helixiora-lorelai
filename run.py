#!/usr/bin/env python3
"""Main application file for the Flask app."""

from app.factory import create_app
import sys
from app.helpers.database import perform_health_checks
from flask.templating import render_template_string
from flask import request, url_for

app = create_app()


# Move the health check inside a function that will be called after the app is fully initialized
def run_health_checks():
    """Run the health checks."""
    with app.app_context():
        errors = perform_health_checks()
        if errors:
            sys.exit(f"Startup checks failed: {errors}")


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
    Display an alert indicating that the organisation name already exists and return the user to the previous page.

    This route is typically used to notify the user that the organisation name they are attempting to use already exists
    in the database. After showing the alert, the user is redirected back to the page they were on before attempting to
    create the organisation with the duplicate name.

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
    app.run(ssl_context=("cert.pem", "key.pem"))
