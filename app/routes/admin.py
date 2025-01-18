"""Contains the routes for the admin page."""

import logging

from sqlalchemy.exc import SQLAlchemyError
import mysql

from flask import (
    Blueprint,
    jsonify,
    render_template,
    session,
    url_for,
    request,
    flash,
    redirect,
    current_app,
)
from flask_login import login_required, current_user
from app.models.user import User, VALID_ROLES
from app.models.role import Role
from app.schemas import UserSchema
from app.helpers.users import (
    role_required,
    create_invited_user_in_db,
    get_user_roles,
    add_user_role,
    remove_user_role,
)

from lorelai.pinecone import PineconeHelper
from lorelai.utils import send_invite_email, create_jwt_token_invite_user

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin", methods=["GET"])
@login_required
def admin_dashboard():
    """Return the admin page.

    This page is only accessible to users who are admins.
    """
    UserSchema.model_validate(current_user)  # it does modify the current_user object in place
    if not current_user.is_admin():
        return redirect(url_for("unauthorized"))

    try:
        if current_user.is_super_admin():
            users = User.query.all()
        elif current_user.is_org_admin():
            users = User.query.filter_by(org_id=current_user.org_id).all()
        else:
            users = []

        users_schema = [
            {
                **UserSchema.model_validate(user).model_dump(),
                "org_name": user.organisation.name,
                "user_id": user.id,
            }
            for user in users
        ]
        return render_template("admin.html", is_admin=current_user.is_admin(), users=users_schema)
    except SQLAlchemyError:
        flash("Failed to retrieve users.", "error")
        return render_template("admin.html", is_admin=current_user.is_admin(), users=[])


@admin_bp.route("/admin/pinecone")
@role_required(["super_admin", "org_admin"])
@login_required
def list_indexes() -> str:
    """Return the list indexes page.

    Returns
    -------
    str
        The rendered template of the list indexes page.
    """
    pinecone_helper = PineconeHelper()
    indexes = pinecone_helper.list_indexes()

    return render_template("admin/pinecone.html", indexes=indexes, is_admin=current_user.is_admin())


@admin_bp.route("/admin/pinecone/<host_name>")
@role_required(["super_admin", "org_admin"])
@login_required
def index_details(host_name: str) -> str:
    """Return the index details page."""
    pinecone_helper = PineconeHelper()

    index_metadata = pinecone_helper.get_index_details(index_host=host_name)

    return render_template(
        "admin/index_details.html",
        index_host=host_name,
        metadata=index_metadata,
        is_admin=current_user.is_admin(),
    )


@admin_bp.route("/admin/setup", methods=["GET"])
@role_required(["super_admin", "org_admin"])
@login_required
def setup() -> str:
    """Return the LorelAI setup page.

    Shows the parameters for the database connection,
    and two buttons to test the connection and run the database creation.
    Note that it doesn't support changing the database parameters.

    Returns
    -------
    str
        The rendered template of the setup page.
    """
    conn_string = current_app.config["DB_URL"]
    return render_template(
        "admin/setup.html",
        setup_url=url_for("admin.setup_post"),
        test_connection_url=url_for("admin.test_connection"),
        db=conn_string,
    )


@admin_bp.route("/admin/setup", methods=["POST"])
@role_required(["super_admin", "org_admin"])
@login_required
def setup_post() -> str:
    """Create the database using the .db/baseline_schema.sql file.

    After the database is created, run the Flyway migrations in ./db/migrations.

    Returns
    -------
    str
        A message indicating the result of the setup.

    Raises
    ------
    FileNotFoundError
        If the baseline schema file is not found.
    """
    msg = "<strong>Creating the database and running Flyway migrations.</strong><br/>"
    msg += "<pre style='font-family: monospace;'>"
    # cursor = None
    # conn = None

    try:
        msg += "Connecting to MySQL...<br/>"
        #     conn = get_db_connection(with_db=False)
        #     msg += f"MySQL connection successful.<br/>{conn.get_server_info()}<br/>"

        #     db_config = load_config("db")
        #     db_name = db_config["database"]
        #     dir_path = os.path.dirname(os.path.realpath(__file__ + "/../.."))
        #     baseline_schema_path = os.path.join(dir_path, "db", "baseline_schema.sql")

        #     if not os.path.exists(baseline_schema_path):
        #       raise FileNotFoundError(f"Baseline schema file not found at {baseline_schema_path}")

        #     with open(baseline_schema_path) as file:
        #         baseline_schema = file.read()

        #     msg += "Creating the database...<br/>"
        #     msg += f"Baseline schema loaded:<br/>{baseline_schema}<br/>"

        #     cursor = conn.cursor()
        #     cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        #     cursor.execute(f"USE {db_name}")
        #     for result in cursor.execute(baseline_schema, multi=True):
        #         if result.with_rows:
        #             msg += f"Affected {result.rowcount} rows<br/>"

        #     cursor.close()
        #     conn.close()

        #     flyway_success, flyway_result = run_flyway_migrations(
        #         db_config["host"],
        #         db_name,
        #         db_config["user"],
        #         db_config["password"],
        #     )
        #     if flyway_success:
        #         current_app.config["LORELAI_SETUP"] = False
        #     msg += f"Flyway migrations completed. Flyway result:<br/>{flyway_result}<br/>"

        # msg += "</pre>"
        return msg

    except FileNotFoundError as fnf_error:
        logging.error(f"File error: {fnf_error}")
        return jsonify({"error": f"File error: {fnf_error}"}), 500
    except mysql.connector.Error as db_error:
        logging.error(f"Database error: {db_error}")
        return jsonify({"error": f"Database error: {db_error}"}), 500
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return jsonify({"error": f"An error occurred: {e}"}), 500
    # finally:
    #     if cursor:
    #         cursor.close()
    #     if conn:
    #         conn.close()


# @role_required(["super_admin", "org_admin"])
@admin_bp.route("/admin/invite_user", methods=["POST"])
@login_required
def invite_user():
    """
    Handle user invitation process by sending an invite email with a registration link.

    This function performs the following steps:
    1. Retrieves the invitee's email from the request form.
    2. Creates a JWT token for the invitee using their email, the organisation admin's email, and
    the organisation's name.
    3. Generates an invite registration URL with the JWT token.
    4. Sends an invite email to the invitee with the registration URL.
    5. Displays a success or error message based on the email sending status.
    6. Redirects to the admin page.

    Returns
    -------
        Redirect: A redirect response to the admin page.

    Flask Context:
        - Expects 'user_email' and 'org_name' to be present in the session.
        - Expects 'email' to be present in the request form.
    """
    email = request.form["email"]
    token = create_jwt_token_invite_user(
        invitee_email=email,
        org_admin_email=session["user.email"],
        org_name=session["user.org_name"],
    )
    invite_register_url = url_for("chat.index", token=token, _external=True)

    email_status = send_invite_email(
        org_admin_email=session["user.email"],
        invitee_email=email,
        invite_url=invite_register_url,
    )
    if email_status:
        create_invited_user_in_db(email=email, org_id=session["user.org_id"])
        flash(f"Invitation to {email} sent successfully!", "success")
        logging.info(f"Invitation to {email} sent successfully!")
    else:
        flash("Invitation failed", "error")
        logging.error(f"Invitation to {email} failed")

    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/admin/user/<int:user_id>/roles", methods=["GET", "POST"])
@login_required
@role_required(["super_admin", "org_admin"])
def manage_user_roles(user_id):
    """Manage user roles for a user."""
    user = User.query.get_or_404(user_id)
    all_roles = Role.query.all()
    if request.method == "POST":
        # Get and sanitize roles
        submitted_roles = request.form.getlist("roles")
        new_roles = [role.strip() for role in submitted_roles if role.strip() in VALID_ROLES]
        current_roles = get_user_roles(user_id)

        # Add new roles
        for role in new_roles:
            if role not in current_roles:
                add_user_role(user_id, role)

        # Remove roles that are not in the new list
        for role in current_roles:
            if role not in new_roles:
                remove_user_role(user_id, role)

        flash("User roles updated successfully", "success")
        return redirect(url_for("admin.manage_user_roles", user_id=user_id))

    user_roles = get_user_roles(user_id)
    return render_template(
        "admin/manage_user_roles.html",
        user=user,
        all_roles=all_roles,
        user_roles=user_roles,
    )
