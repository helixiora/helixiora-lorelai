"""Plan models."""

from datetime import datetime


from app.database import db


class Plan(db.Model):
    """Model for a plan."""

    __tablename__ = "plans"

    plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    plan_name = db.Column(db.String(50), nullable=False)
    message_limit_daily = db.Column(db.Integer, nullable=True)

    stripe_product_id = db.Column(db.String(255), nullable=True, unique=True)  # Stripe product ID

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user_plans = db.relationship("UserPlan", backref="plan", lazy=True)


class UserPlan(db.Model):
    """Model for a user plan."""

    __tablename__ = "user_plans"

    user_plan_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.plan_id"), nullable=False)

    # When the subscription started
    start_date = db.Column(db.Date, nullable=False)

    # Optional end date (for canceled subscriptions)
    end_date = db.Column(db.Date, nullable=True)

    # Whether the subscription is currently active
    is_active = db.Column(db.Boolean, default=True)

    # Stripe subscription ID for reference
    stripe_subscription_id = db.Column(db.String(255), nullable=True)

    # Billing interval (month, year) from Stripe
    billing_interval = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        db.Index("idx_user_plans_plan_id", "plan_id"),
        db.Index("idx_user_plans_user_id", "user_id"),
    )

    @property
    def plan_name(self) -> str:
        """Get the name of the associated plan.

        Returns
        -------
            str: The name of the plan.
        """
        return self.plan.plan_name if self.plan else None

    @property
    def plan_details(self) -> dict:
        """Get details of the associated plan.

        Returns
        -------
            dict: Dictionary containing plan details.
        """
        if not self.plan:
            return None
        return {
            "plan_name": self.plan.plan_name,
            "plan_id": self.plan.plan_id,
            "stripe_product_id": self.plan.stripe_product_id,
        }
