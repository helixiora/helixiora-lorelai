"""Organisation model."""

from . import db


class Organisation(db.Model):
    """Model for an organisation."""

    __tablename__ = "organisation"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)

    # Relationships
    users = db.relationship("User", back_populates="organisation", lazy=True)
    indexing_runs = db.relationship("IndexingRun", back_populates="organisation")

    def __repr__(self):
        """Return a string representation of the organisation."""
        return f"<Organisation {self.name}>"
