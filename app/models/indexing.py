"""Indexing model."""

from datetime import datetime
from app.database import db


class IndexingRun(db.Model):
    """Model for an indexing run."""

    __tablename__ = "indexing_runs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rq_job_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(255), nullable=False)
    error = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    organisation_id = db.Column(db.Integer, db.ForeignKey("organisation.id"), nullable=False)
    datasource_id = db.Column(db.Integer, db.ForeignKey("datasource.datasource_id"), nullable=False)

    # Relationships
    items = db.relationship("IndexingRunItem", back_populates="indexing_run")
    user = db.relationship("User", back_populates="indexing_runs")
    organisation = db.relationship("Organisation", back_populates="indexing_runs")
    datasource = db.relationship("Datasource", back_populates="indexing_runs")

    def __repr__(self):
        """Return a string representation of the indexing run."""
        return f"<IndexingRun {self.id}>"

    def __str__(self):
        """Return a string representation of the indexing run."""
        return f"<IndexingRun {self.id}>"


class IndexingRunItem(db.Model):
    """Model for an indexing run item."""

    __tablename__ = "indexing_run_items"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    indexing_run_id = db.Column(db.Integer, db.ForeignKey("indexing_runs.id"), nullable=False)
    item_id = db.Column(db.String(255), nullable=False)
    item_type = db.Column(db.String(255), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    item_url = db.Column(db.String(255), nullable=False)
    item_status = db.Column(db.String(255), nullable=False)
    item_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    parent_item_id = db.Column(db.Integer, db.ForeignKey("indexing_run_items.id"), nullable=True)

    # Relationships
    indexing_run = db.relationship("IndexingRun", back_populates="items")
    # Self-referential relationship for parent/child items
    parent_item = db.relationship(
        "IndexingRunItem",
        remote_side=[id],
        backref=db.backref("child_items", lazy="dynamic"),
    )

    def __repr__(self):
        """Return a string representation of the indexing run item."""
        return f"<IndexingRunItem {self.item_name}>"

    def __str__(self):
        """Return a string representation of the indexing run item."""
        return f"<IndexingRunItem {self.item_name}>"
