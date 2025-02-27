"""Add datasource_config table.

Revision ID: 00015
Revises: 00014
Create Date: 2024-02-24 15:55:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00015"
down_revision: str | None = "00014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create datasource_config table."""
    op.create_table(
        "datasource_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plugin_name", sa.String(255), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "plugin_name", "field_name", name="unique_user_plugin_field"
        ),
    )
    # Add index for faster lookups
    op.create_index(
        "idx_datasource_config_lookup",
        "datasource_config",
        ["user_id", "plugin_name"],
        unique=False,
    )


def downgrade() -> None:
    """Remove datasource_config table."""
    op.drop_index("idx_datasource_config_lookup", table_name="datasource_config")
    op.drop_table("datasource_config")
