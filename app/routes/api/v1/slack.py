"""Slack API routes."""

from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
import logging

from app.database import db
from app.models import UserAuth, Datasource, User
from app.helpers.datasources import DATASOURCE_SLACK
from lorelai.pinecone import delete_user_datasource_vectors


class SlackRevokeResponse(BaseModel):
    """Response model for Slack revoke endpoint."""

    status: str
    message: str
    error: str | None = None


slack_ns = Namespace("slack", description="Slack operations")


@slack_ns.route("/revoke")
class RevokeAccess(Resource):
    """Revoke Slack access."""

    @slack_ns.doc("revoke_access", security="Bearer Auth")
    @slack_ns.response(200, "Access revoked successfully")
    @slack_ns.response(401, "Unauthorized")
    @slack_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers"])
    def post(self):
        """Post method to revoke Slack access."""
        try:
            user_id = get_jwt_identity()
            user = User.query.get(user_id)
            if not user:
                return SlackRevokeResponse(
                    status="error",
                    message="User not found",
                    error="User not found",
                ).dict(), 404

            slack_datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()
            if not slack_datasource:
                return SlackRevokeResponse(
                    status="error",
                    message="Slack integration not found",
                    error="Slack integration not found",
                ).dict(), 404

            # Remove UserAuth records
            UserAuth.query.filter_by(
                user_id=user_id, datasource_id=slack_datasource.datasource_id
            ).delete()

            # Clean up Pinecone vectors
            delete_user_datasource_vectors(
                user_id=user_id,
                datasource_name=DATASOURCE_SLACK,
                user_email=user.email,
                org_name=user.organisation.name,
            )

            db.session.commit()
            return SlackRevokeResponse(
                status="success",
                message="Slack integration has been revoked and data cleaned up",
            ).dict()

        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Database error while revoking Slack access: {e}")
            return SlackRevokeResponse(
                status="error",
                message="Database error while revoking Slack access",
                error=str(e),
            ).dict(), 500
        except Exception as e:
            logging.error(f"Error during Slack revocation: {e}")
            return SlackRevokeResponse(
                status="error",
                message="Error during Slack revocation",
                error=str(e),
            ).dict(), 500
