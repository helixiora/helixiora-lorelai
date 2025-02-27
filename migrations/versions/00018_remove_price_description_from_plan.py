"""Remove price and description from Plan model.

Revision ID: 00018
Revises: 00017
Create Date: 2023-08-01 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "00018"
down_revision = "00017"
branch_labels = None
depends_on = None


def upgrade():
    """Remove price and description columns from plans table."""
    # Drop the columns
    op.drop_column("plans", "price")
    op.drop_column("plans", "description")


def downgrade():
    """Add back price and description columns to plans table."""
    # Add the columns back
    op.add_column("plans", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "plans",
        sa.Column(
            "price", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0.00"
        ),
    )
