"""Google Drive API routes."""

from flask_restx import Namespace, Resource, fields
from flask import session, request
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.models import db, UserAuth, Datasource, GoogleDriveItem, User
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE
from flask_jwt_extended import jwt_required
from lorelai.pinecone import delete_user_datasource_vectors

googledrive_ns = Namespace("googledrive", description="Google Drive operations")

# Models for request/response documentation
file_model = googledrive_ns.model(
    "File",
    {
        "id": fields.String(required=True, description="Google Drive file ID"),
        "name": fields.String(required=True, description="File name"),
        "mimeType": fields.String(required=True, description="MIME type"),
        "type": fields.String(required=True, description="File type"),
    },
)


@googledrive_ns.route("/revoke")
class RevokeAccess(Resource):
    """Revoke Google Drive access."""

    @googledrive_ns.doc("revoke_access", security="Bearer Auth")
    @googledrive_ns.response(200, "Access revoked successfully")
    @googledrive_ns.response(401, "Unauthorized")
    @googledrive_ns.response(500, "Internal server error")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Post method to revoke Google Drive access."""
        user_id = session.get("user.id")
        if not user_id:
            return {"error": "User not logged in or session expired"}, 401

        try:
            # Get user and organization info
            user = User.query.get(user_id)
            if not user:
                return {"error": "User not found"}, 404

            datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first()
            if not datasource:
                raise ValueError(f"{DATASOURCE_GOOGLE_DRIVE} missing from datasource table")

            # Delete database records
            UserAuth.query.filter_by(
                user_id=user_id, datasource_id=datasource.datasource_id
            ).delete()
            GoogleDriveItem.query.filter_by(user_id=user_id).delete()

            # Delete vectors from Pinecone
            delete_user_datasource_vectors(
                user_id=user_id,
                datasource_name=DATASOURCE_GOOGLE_DRIVE,
                user_email=user.email,
                org_name=user.organisation.name,
            )

            db.session.commit()
            return {"status": "success", "message": "User deauthorized from Google Drive"}

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"error": f"Database error: {str(e)}"}, 500
        except Exception as e:
            db.session.rollback()
            return {"error": f"Error during revocation: {str(e)}"}, 500


@googledrive_ns.route("/processfilepicker", doc=False)
class ProcessFilePicker(Resource):
    """Process selected Google Drive files."""

    @googledrive_ns.doc("process_files", security="Bearer Auth")
    @googledrive_ns.expect([file_model])
    @googledrive_ns.response(200, "Files processed successfully")
    @googledrive_ns.response(400, "No documents selected")
    @googledrive_ns.response(500, "Processing error")
    def post(self):
        """Post method to process selected Google Drive files."""
        user_id = session["user.id"]
        documents = request.get_json()

        if not documents:
            return {"error": "No documents selected"}, 400

        try:
            for doc in documents:
                new_item = GoogleDriveItem(
                    user_id=user_id,
                    google_drive_id=doc["id"],
                    item_name=doc["name"],
                    mime_type=doc["mimeType"],
                    item_type=doc["type"],
                    item_url=doc["url"],
                    icon_url=doc["iconUrl"],
                )
                db.session.add(new_item)
                logging.info(f"Inserted google doc id: {doc['id']} for user id: {user_id}")
            db.session.commit()
            return {"message": "Success"}
        except SQLAlchemyError as e:
            db.session.rollback()
            return {"error": f"Error inserting google doc: {str(e)}"}, 500


@googledrive_ns.route("/removefile")
class RemoveFile(Resource):
    """Remove a Google Drive file from the database."""

    @googledrive_ns.doc("remove_file", security="Bearer Auth")
    @googledrive_ns.expect(
        googledrive_ns.model(
            "RemoveFile",
            {"google_drive_id": fields.String(required=True, description="Google Drive file ID")},
        )
    )
    @googledrive_ns.response(200, "File removed successfully")
    @googledrive_ns.response(500, "Removal error")
    @jwt_required(locations=["headers", "cookies"])
    def post(self):
        """Post method to remove a Google Drive file from the database."""
        user_id = session["user.id"]
        google_drive_id = request.get_json()["google_drive_id"]

        try:
            GoogleDriveItem.query.filter_by(
                user_id=user_id, google_drive_id=google_drive_id
            ).delete()
            db.session.commit()
            return {"message": "OK"}
        except SQLAlchemyError as e:
            db.session.rollback()
            logging.error(f"Error deleting google doc id: {google_drive_id}, Error: {str(e)}")
            return {
                "error": f"Error deleting google doc id: {google_drive_id}, Error: {str(e)}"
            }, 500
