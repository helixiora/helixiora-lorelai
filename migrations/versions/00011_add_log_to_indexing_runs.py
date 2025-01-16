"""Add log field to indexing runs.

Revision ID: 00011
Revises: 00010
Create Date: 2025-01-16 18:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "00011"
down_revision = "00010"
branch_labels = None
depends_on = None


def upgrade():
    """Add item_log column to indexing_run_items table."""
    op.add_column("indexing_run_items", sa.Column("item_log", sa.Text(), nullable=True))


def downgrade():
    """Remove item_log column from indexing_run_items table."""
    op.drop_column("indexing_run_items", "item_log")
