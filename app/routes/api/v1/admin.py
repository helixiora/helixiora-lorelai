"""Admin API routes."""

from flask_restx import Namespace, Resource, fields
from flask import session, current_app
from flask_login import current_user
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import mysql
from pydantic import ValidationError

from app.database import db
from app.models.user import User, VALID_ROLES
from app.models.organisation import Organisation
from app.models.user_auth import UserAuth
from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema
from app.helpers.users import (
    create_user,
    get_user_roles,
    add_user_role,
    remove_user_role,
    role_required,
)

from redis import Redis
from rq import Queue
from datetime import datetime
import logging

from app.tasks import run_indexer

admin_ns = Namespace("admin", description="Admin operations")

# Models for request/response documentation
user_model = admin_ns.model(
    "User",
    {
        "email": fields.String(required=True, description="User email"),
        "full_name": fields.String(required=True, description="User full name"),
        "org_name": fields.String(description="Organization name"),
        "roles": fields.List(fields.String, description="User roles"),
    },
)

job_status_model = admin_ns.model(
    "JobStatus",
    {
        "job_id": fields.String(description="Job ID"),
        "state": fields.String(description="Job state"),
        "metadata": fields.Raw(description="Job metadata"),
        "result": fields.Raw(description="Job result", required=False),
    },
)

# Models for API documentation
role_model = admin_ns.model(
    "Role", {"role": fields.String(required=True, description="Role name", enum=VALID_ROLES)}
)

roles_model = admin_ns.model(
    "UserRoles",
    {
        "roles": fields.List(
            fields.String(enum=list(VALID_ROLES)), required=True, description="List of role names"
        )
    },
)


@admin_ns.route("/create_user")
class CreateUser(Resource):
    """Create a new user."""

    @admin_ns.doc("create_user", security="Bearer Auth")
    @admin_ns.expect(user_model)
    @admin_ns.response(201, "User created successfully")
    @admin_ns.response(400, "Validation error")
    @admin_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Post method to create a new user."""
        if not current_user.is_admin:
            return {"message": "Unauthorized access"}, 401

        try:
            user_data = UserSchema(**admin_ns.payload)
            user = create_user(
                email=user_data.email,
                full_name=user_data.full_name,
                org_name=admin_ns.payload.get("org_name"),
                roles=[role.name for role in user_data.roles],
            )
            return {"status": "success", "user": UserSchema.from_orm(user).dict()}, 201
        except ValidationError as e:
            return {"status": "error", "message": e.errors()}, 400
        except SQLAlchemyError:
            return {"status": "error", "message": "Failed to create user."}, 500


@admin_ns.route("/indexer/job-status/<string:job_id>")
class JobStatus(Resource):
    """Get the status of an indexing job."""

    @admin_ns.doc("get_job_status", security="Bearer Auth")
    @admin_ns.response(200, "Success", job_status_model)
    @admin_ns.response(404, "Job not found")
    @jwt_required(locations=["headers", "cookies"])
    def get(self, job_id):
        """Get the status of an indexing job."""
        redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
        queue = Queue(current_app.config["REDIS_QUEUE_INDEXER"], connection=redis_conn)
        job = queue.fetch_job(job_id)

        if job is None:
            return {"job_id": job_id, "state": "unknown", "status": "unknown"}, 404

        response = {"job_id": job_id, "state": job.get_status(), "metadata": job.meta}

        if job.is_finished:
            response["result"] = job.result

        return response


@admin_ns.route("/index/<string:type>")
class StartIndexing(Resource):
    """Start indexing data for the organization."""

    @admin_ns.doc("start_indexing", security="Bearer Auth")
    @admin_ns.response(200, "Indexing started")
    @admin_ns.response(403, "Unauthorized")
    @admin_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers", "cookies"])
    def post(self, type):
        """Post method to start indexing data for the organization."""
        if type == "organisation" and not current_user.is_org_admin():
            return {"error": "Only organisation admins can index their organisation"}, 403
        if type == "all" and not current_user.is_super_admin():
            return {"error": "Only super admins can index all organisations"}, 403

        try:
            logging.info("Started indexing (type: %s)", type)
            if type not in ["user", "organisation", "all"]:
                return {"error": "Invalid type"}, 400

            try:
                redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
                queue = Queue(current_app.config["REDIS_QUEUE_INDEXER"], connection=redis_conn)

                user_id = session["user.id"]
                org_id = session.get("user.org_id")
                if not org_id and type != "all":
                    return {
                        "error": "No organisation ID found for the user in the session details"
                    }, 403

                jobs = []

                # Convert SQLAlchemy objects to Pydantic models
                org_rows = (
                    Organisation.query.filter_by(id=org_id)
                    if type in ["user", "organisation"]
                    else Organisation.query.all()
                )
                org_rows = [OrganisationSchema.from_orm(org) for org in org_rows]

                for org_row in org_rows:
                    user_rows = (
                        User.query.filter_by(org_id=org_row.id)
                        if type in ["organisation", "all"]
                        else User.query.filter_by(id=user_id, org_id=org_id)
                    )
                    # Ensure all required fields are present
                    user_rows = [UserSchema.from_orm(user) for user in user_rows]

                    for user_row in user_rows:
                        # Get auth rows only for this specific user
                        user_auth_rows_for_user = UserAuth.query.filter_by(user_id=user_row.id)
                        user_auth_rows = [
                            UserAuthSchema.from_orm(auth) for auth in user_auth_rows_for_user
                        ]

                        # Create a job per user
                        job = queue.enqueue(
                            run_indexer,
                            organisation=org_row,
                            users=[user_row],  # Pass single user
                            user_auths=user_auth_rows,  # Pass only this user's auths
                            started_by_user_id=user_id,
                            job_timeout=3600,
                            description=f"Indexing started by {user_id} for user {user_row.email} \
in {org_row.name} - Start time: {datetime.now()}",
                        )

                        job_id = job.get_id()
                        jobs.append(job_id)

                logging.info("Started indexing for %s jobs", len(jobs))
                return {"jobs": jobs}, 202
            except ValidationError as e:
                logging.error(f"Validation error: {e}")
                return {"error": "Validation error", "details": e.errors()}, 400
            except Exception:
                logging.exception("Error starting indexing")
                return {"error": "Failed to start indexing"}, 500
        finally:
            db.session.close()


# doc=False to disable this endpoint from the API docs and remove it from swagger.json
@admin_ns.route("/test-connection", doc=False)
class TestConnection(Resource):
    """Test database connection."""

    # Disable this endpoint from the API docs
    @admin_ns.hide
    @admin_ns.response(200, "Connection successful")
    @admin_ns.response(500, "Connection failed")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Post method to test database connection."""
        try:
            if db.session.execute("SELECT 1").fetchone():
                return {"message": "Connected to database"}
            return {"message": "Failed to connect to database"}, 500
        except mysql.connector.Error as e:
            if e.errno == 1049:
                return {"error": f"{e.msg} (error {str(e.errno)})"}, 500
            raise


@admin_ns.route("/users/<int:user_id>/roles")
class UserRoles(Resource):
    """Resource for managing user roles."""

    @admin_ns.doc("get_user_roles", security="Bearer Auth")
    @admin_ns.response(200, "Success", roles_model)
    @admin_ns.response(403, "Unauthorized")
    @admin_ns.response(404, "User not found")
    @jwt_required(locations=["headers", "cookies"])
    @role_required(["super_admin", "org_admin"])
    def get(self, user_id):
        """Get roles for a specific user."""
        User.query.get_or_404(user_id)
        roles = get_user_roles(user_id)
        return {"roles": roles}

    @admin_ns.doc("update_user_roles", security="Bearer Auth")
    @admin_ns.expect(roles_model)
    @admin_ns.response(200, "Success")
    @admin_ns.response(400, "Invalid roles")
    @admin_ns.response(403, "Unauthorized")
    @admin_ns.response(404, "User not found")
    @jwt_required(locations=["headers", "cookies"])
    @role_required(["super_admin", "org_admin"])
    def put(self, user_id):
        """Update roles for a specific user."""
        User.query.get_or_404(user_id)
        data = admin_ns.payload
        new_roles = data.get("roles", [])

        # Validate roles
        if not all(role in VALID_ROLES for role in new_roles):
            return {"error": "Invalid roles provided"}, 400

        # Get current roles
        current_roles = get_user_roles(user_id)

        # Add new roles
        for role in new_roles:
            if role not in current_roles:
                add_user_role(user_id, role)

        # Remove roles that are not in the new list
        for role in current_roles:
            if role not in new_roles:
                remove_user_role(user_id, role)

        return {"message": "User roles updated successfully"}


@admin_ns.route("/users/<int:user_id>")
class UserManagement(Resource):
    """Resource for managing users."""

    @admin_ns.doc("delete_user", security="Bearer Auth")
    @admin_ns.response(200, "Success")
    @admin_ns.response(403, "Unauthorized")
    @admin_ns.response(404, "User not found")
    @jwt_required(locations=["headers", "cookies"])
    @role_required(["super_admin"])
    def delete(self, user_id):
        """Delete a specific user."""
        user = User.query.get_or_404(user_id)

        try:
            db.session.delete(user)
            db.session.commit()
            return {"message": "User deleted successfully"}
        except Exception as e:
            db.session.rollback()
            return {"error": str(e)}, 500
