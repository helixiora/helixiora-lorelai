"""Routes for indexing runs."""

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import IndexingRun, Datasource
from app.helpers.datasources import DATASOURCE_GOOGLE_DRIVE, DATASOURCE_SLACK

bp = Blueprint("indexing", __name__)


@bp.route("/indexing-runs/<datasource_type>")
@login_required
def indexing_runs(datasource_type):
    """Show indexing runs for a specific datasource type."""
    if datasource_type not in ["google_drive", "slack"]:
        return render_template("error.html", message="Invalid datasource type"), 400

    if datasource_type == "google_drive":
        datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_GOOGLE_DRIVE).first()
    elif datasource_type == "slack":
        datasource = Datasource.query.filter_by(datasource_name=DATASOURCE_SLACK).first()

    if not datasource:
        return render_template("error.html", message="Invalid datasource type"), 400

    # Get all indexing runs for this user and datasource type
    runs = (
        IndexingRun.query.filter_by(user_id=current_user.id, datasource_id=datasource.datasource_id)
        .order_by(IndexingRun.created_at.desc())
        .all()
    )

    datasource_name = "Google Drive" if datasource_type == "google_drive" else "Slack"

    return render_template(
        "integrations/indexing-runs.html",
        indexing_runs=runs,
        datasource_name=datasource_name,
    )
