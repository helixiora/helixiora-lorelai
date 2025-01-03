"""Datasource model."""

from . import db


class Datasource(db.Model):
    """Model for a datasource."""

    __tablename__ = "datasource"

    datasource_id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, name="datasource_id"
    )
    datasource_name = db.Column(db.String(255), nullable=False, unique=True)
    datasource_type = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Relationships
    indexing_runs = db.relationship("IndexingRun", back_populates="datasource")
