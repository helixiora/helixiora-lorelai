"""Stripe product integration and schema cleanup.

Revision ID: 00017
Revises: 00016
Create Date: 2023-12-15 12:34:56.789012

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = "00017"
down_revision = "00016"
branch_labels = None
depends_on = None


def upgrade():
    """Upgrade the database schema.

    Adds Stripe product integration and cleans up schema:
    1. Adds stripe_product_id to plans table
    2. Removes duration_months from plans table
    3. Removes stripe_price_id from plans table
    4. Updates user_plans table to track subscription details
    5. Makes end_date nullable for active subscriptions
    """
    # Get inspector to check for existing columns
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # Check if stripe_product_id exists in plans table
    plans_columns = [col["name"] for col in inspector.get_columns("plans")]
    if "stripe_product_id" not in plans_columns:
        # 1. Add stripe_product_id to plans table
        op.add_column("plans", sa.Column("stripe_product_id", sa.String(255), nullable=True))
        op.create_unique_constraint("uq_plans_stripe_product_id", "plans", ["stripe_product_id"])

    # Check if duration_months exists in plans table
    if "duration_months" in plans_columns:
        # 2. Remove duration_months from plans table
        op.drop_column("plans", "duration_months")

    # Check if stripe_price_id exists in plans table
    if "stripe_price_id" in plans_columns:
        # 3. Remove stripe_price_id from plans table
        op.drop_column("plans", "stripe_price_id")

    # Check for columns in user_plans table
    user_plans_columns = [col["name"] for col in inspector.get_columns("user_plans")]

    # 4. Update user_plans table to track subscription details
    if "stripe_subscription_id" not in user_plans_columns:
        op.add_column(
            "user_plans", sa.Column("stripe_subscription_id", sa.String(255), nullable=True)
        )

    if "billing_interval" not in user_plans_columns:
        op.add_column("user_plans", sa.Column("billing_interval", sa.String(50), nullable=True))

    # 5. Make end_date nullable for active subscriptions
    # This operation is idempotent, so we can run it without checking
    op.alter_column("user_plans", "end_date", existing_type=sa.DATE(), nullable=True)


def downgrade():
    """Downgrade the database schema.

    Reverts the changes made in the upgrade function:
    1. Removes subscription tracking columns from user_plans
    2. Restores previous schema structure
    """
    # 1. Remove subscription tracking columns from user_plans
    op.drop_column("user_plans", "billing_interval")
    op.drop_column("user_plans", "stripe_subscription_id")

    # 2. Make end_date non-nullable again
    op.alter_column("user_plans", "end_date", existing_type=sa.DATE(), nullable=False)

    # 3. Add stripe_price_id back to plans table
    op.add_column("plans", sa.Column("stripe_price_id", sa.String(255), nullable=True))

    # 4. Add duration_months back to plans table
    op.add_column(
        "plans", sa.Column("duration_months", sa.Integer(), server_default="1", nullable=False)
    )

    # 5. Remove stripe_product_id from plans table
    op.drop_constraint("uq_plans_stripe_product_id", "plans", type_="unique")
    op.drop_column("plans", "stripe_product_id")
