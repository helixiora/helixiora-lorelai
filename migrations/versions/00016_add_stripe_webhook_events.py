"""Add stripe webhook events table.

Revision ID: 00016
Revises: 00015
Create Date: 2025-02-21 21:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "00016"
down_revision = "00015"
branch_labels = None
depends_on = None


def upgrade():
    """Create stripe_webhook_events table."""
    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stripe_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(255), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )

    # Add indexes
    op.create_index(
        "idx_stripe_webhook_events_event_type",
        "stripe_webhook_events",
        ["event_type"],
    )
    op.create_index(
        "idx_stripe_webhook_events_created_at",
        "stripe_webhook_events",
        ["created_at"],
    )
    op.create_index(
        "idx_stripe_webhook_events_status",
        "stripe_webhook_events",
        ["status"],
    )


def downgrade():
    """Drop stripe_webhook_events table."""
    op.drop_index("idx_stripe_webhook_events_status", "stripe_webhook_events")
    op.drop_index("idx_stripe_webhook_events_created_at", "stripe_webhook_events")
    op.drop_index("idx_stripe_webhook_events_event_type", "stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
