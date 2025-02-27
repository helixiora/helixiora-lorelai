"""Stripe webhook event model."""

from datetime import datetime

from app.database import db


class StripeWebhookEvent(db.Model):
    """Model for storing Stripe webhook events."""

    __tablename__ = "stripe_webhook_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    stripe_event_id = db.Column(db.String(255), unique=True, nullable=False)
    event_type = db.Column(db.String(255), nullable=False)
    event_data = db.Column(db.JSON, nullable=False)  # Store complete webhook payload
    status = db.Column(
        db.String(50), nullable=False, default="received"
    )  # received, processed, failed
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.Index("idx_stripe_webhook_events_event_type", "event_type"),
        db.Index("idx_stripe_webhook_events_created_at", "created_at"),
        db.Index("idx_stripe_webhook_events_status", "status"),
    )
