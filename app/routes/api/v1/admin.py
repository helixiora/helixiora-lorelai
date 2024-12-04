"""Admin API routes."""

from flask_restx import Namespace, Resource, fields
from flask import session, current_app
from flask_login import current_user
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import mysql
from pydantic import ValidationError

from app.models import User, db, Organisation, Datasource, UserAuth
from app.schemas import UserSchema, OrganisationSchema, UserAuthSchema
from app.helpers.users import create_user, is_org_admin, is_super_admin
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE

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


@admin_ns.route("/create_user")
class CreateUser(Resource):
    """Create a new user."""

    @admin_ns.doc("create_user", security="Bearer")
    @admin_ns.expect(user_model)
    @admin_ns.response(201, "User created successfully")
    @admin_ns.response(400, "Validation error")
    @admin_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
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

    @admin_ns.doc("get_job_status")
    @admin_ns.response(200, "Success", job_status_model)
    @admin_ns.response(404, "Job not found")
    @jwt_required(locations=["headers"])
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

    @admin_ns.doc("start_indexing")
    @admin_ns.response(200, "Indexing started")
    @admin_ns.response(403, "Unauthorized")
    @admin_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
    def post(self, type):
        """Post method to start indexing data for the organization."""
        if type == "organisation" and not is_org_admin(session["user.id"]):
            return {"error": "Only organisation admins can index their organisation"}, 403
        if type == "all" and not is_super_admin(session["user.id"]):
            return {"error": "Only super admins can index all organisations"}, 403

        try:
            logging.info("Started indexing (type: %s)", type)
            if type == "organisation" and not is_org_admin(session["user.id"]):
                return {"error": "Only organisation admins can index their organisation"}, 403
            if type == "all" and not is_super_admin(session["user.id"]):
                return {"error": "Only super admins can index all organisations"}, 403

            if type not in ["user", "organisation", "all"]:
                return {"error": "Invalid type"}, 400

            try:
                redis_conn = Redis.from_url(current_app.config["REDIS_URL"])
                queue = Queue(current_app.config["REDIS_QUEUE_INDEXER"], connection=redis_conn)

                datasource_id = (
                    Datasource.query.filter_by(name=DATASOURCE_GOOGLE_DRIVE).first().datasource_id
                )
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

                    user_auth_rows = []
                    for user_row in user_rows:
                        user_auth_rows_for_user = UserAuth.query.filter_by(
                            user_id=user_row.id, datasource_id=datasource_id
                        )
                        user_auth_rows.extend(
                            [UserAuthSchema.from_orm(auth) for auth in user_auth_rows_for_user]
                        )

                        job = queue.enqueue(
                            run_indexer,
                            organisation=org_row,
                            users=user_rows,
                            user_auths=user_auth_rows,
                            started_by_user_id=user_id,
                            job_timeout=3600,
                            description=f"Indexing started by {user_id}: {len(user_rows)} users in \
        {org_row.name} - Start time: {datetime.now()}",
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
    @jwt_required(locations=["headers"])
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
