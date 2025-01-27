"""API routes for indexing operations."""

from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError
import logging

from app.models.indexing import IndexingRunItem
from app.helpers.users import role_required
from flask_login import current_user

indexing_ns = Namespace(
    name="indexing",
    description="Operations related to indexing runs and their items",
    path="/indexing",
)

# Base model for common error responses
error_model = indexing_ns.model(
    "Error",
    {
        "error": fields.String(required=True, description="Error message"),
        "details": fields.String(required=False, description="Detailed error information"),
    },
)

# Base model for pagination metadata
pagination_model = indexing_ns.model(
    "PaginationMetadata",
    {
        "page": fields.Integer(description="Current page number"),
        "per_page": fields.Integer(description="Items per page"),
        "total_items": fields.Integer(description="Total number of items"),
        "total_pages": fields.Integer(description="Total number of pages"),
    },
)

# Models for request/response documentation
item_model = indexing_ns.model(
    "IndexingRunItem",
    {
        "id": fields.Integer(required=True, description="Item ID"),
        "item_name": fields.String(required=True, description="Item name"),
        "item_type": fields.String(required=True, description="Item type (e.g., document, folder)"),
        "item_status": fields.String(
            required=True,
            description="Processing status",
            enum=["pending", "processing", "completed", "failed"],
        ),
        "created_at": fields.DateTime(required=True, description="Creation timestamp"),
        "item_url": fields.String(required=False, description="URL to access the item"),
        "item_error": fields.String(
            required=False, description="Error message if processing failed"
        ),
    },
)

item_list_model = indexing_ns.model(
    "IndexingRunItemList",
    {
        "items": fields.List(
            fields.Nested(item_model), required=True, description="List of indexing run items"
        ),
        "metadata": fields.Nested(
            pagination_model, required=True, description="Pagination metadata"
        ),
    },
)

item_details_model = indexing_ns.model(
    "IndexingRunItemDetails",
    {
        "item_extractedtext": fields.String(required=False, description="Extracted text content"),
        "item_log": fields.String(required=False, description="Processing log"),
        "item_error": fields.String(required=False, description="Error message if any"),
    },
)

# Request parsers
list_parser = indexing_ns.parser()
list_parser.add_argument("page", type=int, location="args", default=1, help="Page number")
list_parser.add_argument("per_page", type=int, location="args", default=20, help="Items per page")
list_parser.add_argument("status", type=str, location="args", help="Filter by status")
list_parser.add_argument("type", type=str, location="args", help="Filter by item type")
list_parser.add_argument(
    "sort",
    type=str,
    location="args",
    default="-created_at",
    help="Sort field (prefix with - for descending)",
)


@indexing_ns.route("/runs/<int:run_id>/items")
@indexing_ns.param("run_id", "The indexing run identifier")
class IndexingRunItems(Resource):
    """Resource for indexing run items."""

    @indexing_ns.doc(description="Get all items for a specific indexing run")
    @indexing_ns.expect(list_parser)
    @indexing_ns.response(200, "Success", item_list_model)
    @indexing_ns.response(400, "Invalid parameters", error_model)
    @indexing_ns.response(401, "Unauthorized", error_model)
    @indexing_ns.response(403, "Forbidden", error_model)
    @indexing_ns.response(500, "Internal server error", error_model)
    @jwt_required(locations=["headers", "cookies"])
    @role_required(["super_admin"])
    def get(self, run_id):
        """Return the items for a specific indexing run with pagination and filtering."""
        try:
            # Parse request arguments
            args = list_parser.parse_args()
            page = args["page"]
            per_page = min(args["per_page"], 100)  # Limit maximum items per page

            # Build query
            query = IndexingRunItem.query.filter_by(indexing_run_id=run_id)

            # Apply filters
            if args["status"]:
                query = query.filter_by(item_status=args["status"])
            if args["type"]:
                query = query.filter_by(item_type=args["type"])

            # Apply sorting
            sort_field = args["sort"].lstrip("-")
            sort_desc = args["sort"].startswith("-")
            if hasattr(IndexingRunItem, sort_field):
                order_by = (
                    getattr(IndexingRunItem, sort_field).desc()
                    if sort_desc
                    else getattr(IndexingRunItem, sort_field)
                )
                query = query.order_by(order_by)

            # Paginate results
            pagination = query.paginate(page=page, per_page=per_page)

            # Format response
            items_data = [
                {
                    "id": item.id,
                    "item_name": item.item_name,
                    "item_type": item.item_type,
                    "item_status": item.item_status,
                    "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    if item.created_at
                    else None,
                    "item_url": item.item_url,
                    "item_error": item.item_error,
                }
                for item in pagination.items
            ]

            return {
                "items": items_data,
                "metadata": {
                    "page": page,
                    "per_page": per_page,
                    "total_items": pagination.total,
                    "total_pages": pagination.pages,
                },
            }

        except SQLAlchemyError as e:
            logging.error(f"Database error: {e}")
            return {"error": "Failed to retrieve items", "details": str(e)}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {"error": "An unexpected error occurred"}, 500


@indexing_ns.route("/items/<int:item_id>/details")
@indexing_ns.param("item_id", "The indexing item identifier")
class IndexingRunItemDetails(Resource):
    """Resource for indexing run item details."""

    @indexing_ns.doc(description="Get detailed information about a specific indexing item")
    @indexing_ns.response(200, "Success", item_details_model)
    @indexing_ns.response(401, "Unauthorized", error_model)
    @indexing_ns.response(403, "Forbidden", error_model)
    @indexing_ns.response(404, "Item not found", error_model)
    @indexing_ns.response(500, "Internal server error", error_model)
    @jwt_required(locations=["headers", "cookies"])
    def get(self, item_id):
        """Return the details for a specific indexing run item."""
        try:
            item = IndexingRunItem.query.get_or_404(item_id)

            # Check if the user has access to this item
            if not current_user.is_super_admin():
                # Get the indexing run associated with this item
                indexing_run = item.indexing_run
                if not indexing_run or indexing_run.user_id != current_user.id:
                    return {"error": "You do not have permission to access this item"}, 403

            return {
                "item_extractedtext": item.item_extractedtext,
                "item_log": item.item_log,
                "item_error": item.item_error,
            }
        except SQLAlchemyError as e:
            logging.error(f"Database error: {e}")
            return {"error": "Failed to retrieve item details", "details": str(e)}, 500
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return {"error": "An unexpected error occurred"}, 500
