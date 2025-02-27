"""Change item_extractedtext to LONGTEXT.

Revision ID: 00014
Revises: 00012
Create Date: 2024-02-16 22:17:13.074000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT


# revision identifiers, used by Alembic.
revision = "00014"
down_revision = "00013"
branch_labels = None
depends_on = None


def upgrade():
    """Change item_extractedtext column to LONGTEXT."""
    # Use batch mode to handle potential existing data
    with op.batch_alter_table("indexing_run_items") as batch_op:
        batch_op.alter_column(
            "item_extractedtext", existing_type=sa.Text(), type_=LONGTEXT, existing_nullable=True
        )


def downgrade():
    """Change item_extractedtext column back to TEXT."""
    # Use batch mode to handle potential existing data
    with op.batch_alter_table("indexing_run_items") as batch_op:
        batch_op.alter_column(
            "item_extractedtext", existing_type=LONGTEXT, type_=sa.Text(), existing_nullable=True
        )
