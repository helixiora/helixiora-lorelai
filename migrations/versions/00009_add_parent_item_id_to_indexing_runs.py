"""Add parent_item_id to indexing_run_items table.

Revision ID: 00009
Revises: 00008
Create Date: 2024-01-02 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "00009"
down_revision = "00008"
branch_labels = None
depends_on = None


def upgrade():
    """Add parent_item_id column with foreign key reference."""
    op.add_column(
        "indexing_run_items",
        sa.Column(
            "parent_item_id", sa.Integer, sa.ForeignKey("indexing_run_items.id"), nullable=True
        ),
    )
    # Add index for faster lookups
    op.create_index(
        "ix_indexing_run_items_parent_item_id", "indexing_run_items", ["parent_item_id"]
    )


def downgrade():
    """Remove parent_item_id column."""
    # Remove index first
    op.drop_index("ix_indexing_run_items_parent_item_id", table_name="indexing_run_items")
    # Then remove the column
    op.drop_column("indexing_run_items", "parent_item_id")
