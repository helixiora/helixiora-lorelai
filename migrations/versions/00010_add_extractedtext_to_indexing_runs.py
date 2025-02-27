"""Add extracted text to indexing runs.

Revision ID: 00009
Revises: 00009
Create Date: 2025-01-15 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "00010"
down_revision = "00009"
branch_labels = None
depends_on = None


def upgrade():
    """Add item_extractedtext column to indexing_run_items table."""
    op.add_column("indexing_run_items", sa.Column("item_extractedtext", sa.Text(), nullable=True))


def downgrade():
    """Remove item_extractedtext column from indexing_run_items table."""
    op.drop_column("indexing_run_items", "item_extractedtext")
