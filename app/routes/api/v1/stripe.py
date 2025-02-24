"""Stripe payment integration routes and webhook handlers.

This module handles all Stripe-related operations including:
- Payment configuration
- Checkout session creation
- Webhook processing for subscription events
- Health checks for Stripe integration
"""

import logging
from datetime import datetime

import stripe
from flask import current_app, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from flask_restx import Namespace, Resource, fields

from app.database import db
from app.helpers.users import assign_plan_to_user
from app.models.plan import Plan
from app.models.stripe_webhook import StripeWebhookEvent
from app.models.user import User

# Define global variable for trial days
TRIAL_DAYS = 7

# Initialize Stripe with the secret key from config
stripe_ns = Namespace("stripe", description="Stripe payment operations")

# Models for request/response documentation
config_model = stripe_ns.model(
    "StripeConfig",
    {
        "publishableKey": fields.String(description="Stripe publishable key"),
    },
)

checkout_session_model = stripe_ns.model(
    "CheckoutSession",
    {
        "plan_id": fields.Integer(required=True, description="Plan ID to subscribe to"),
    },
)


@stripe_ns.route("/config")
class StripeConfigResource(Resource):
    """Resource for getting Stripe configuration."""

    @stripe_ns.doc(security="Bearer Auth")
    @stripe_ns.marshal_with(config_model)
    @jwt_required()
    def get(self):
        """Get Stripe publishable key."""
        stripe_config = {"publishableKey": current_app.config["STRIPE_PUBLISHABLE_KEY"]}
        return stripe_config


@stripe_ns.route("/create-checkout-session")
class CreateCheckoutSessionResource(Resource):
    """Resource for creating Stripe checkout sessions."""

    @stripe_ns.doc(security="Bearer Auth")
    @stripe_ns.expect(checkout_session_model)
    @jwt_required()
    def post(self):
        """Create a Stripe checkout session."""
        try:
            # Initialize Stripe with the secret key
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

            data = request.get_json()
            user_id = get_jwt_identity()

            # Get user details
            user = User.query.get(user_id)
            if not user:
                return {"error": "User not found"}, 404

            # Get plan details from database
            plan = Plan.query.get(data["plan_id"])
            if not plan:
                return {"error": "Plan not found"}, 404

            # Check if user has a Stripe customer ID
            if not user.stripe_customer_id:
                # Create a new Stripe customer
                customer = stripe.Customer.create(
                    email=user.email,
                )
                # Save the customer ID to the user model
                user.stripe_customer_id = customer.id
                db.session.commit()  # Save changes to the database

            # Check if user has previously subscribed to the Pro plan
            has_had_pro_plan = any(
                user_plan.plan.plan_name == "Pro" for user_plan in user.user_plans
            )
            print("&&&&&&&&&&&& has_had_pro_plan", has_had_pro_plan)
            # Create Stripe checkout session
            subscription_data = {}
            if not has_had_pro_plan:
                subscription_data["trial_period_days"] = TRIAL_DAYS

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                customer=user.stripe_customer_id,
                line_items=[
                    {
                        "price": plan.stripe_price_id,
                        "quantity": 1,
                    }
                ],
                subscription_data=subscription_data,
                success_url=f"{request.host_url}profile?payment=success",
                cancel_url=f"{request.host_url}profile?payment=cancelled",
                client_reference_id=str(user_id),
                metadata={
                    "plan_id": plan.plan_id,
                    "plan_name": plan.plan_name,
                    "user_id": user_id,
                    "user_email": user.email,
                },
            )

            return {"sessionId": checkout_session.id}
        except Exception as e:
            logging.error(f"Error creating checkout session: {str(e)}")
            return {"error": str(e)}, 500


@stripe_ns.route("/webhook")
class StripeWebhookResource(Resource):
    """Resource for handling Stripe webhooks."""

    def post(self):
        """Handle Stripe webhook events."""
        try:
            # Initialize Stripe with the secret key
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
            event = None
            payload = request.data
            sig_header = request.headers.get("Stripe-Signature")

            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, current_app.config["STRIPE_WEBHOOK_SECRET"]
                )
            except ValueError as e:
                logging.error(f"Invalid payload: {str(e)}")
                return {"error": "Invalid payload"}, 400
            except stripe.error.SignatureVerificationError as e:
                logging.error(f"Invalid signature: {str(e)}")
                return {"error": "Invalid signature"}, 400

            # Separate the webhook event into different types so if storing in db fails,
            # we can still process the event

            # Store the webhook event in db
            webhook_event = self.store_webhook_event(event)

            # Process the webhook event
            return self.process_webhook_event(event, webhook_event)

        except Exception as e:
            logging.error(f"Error processing webhook: {str(e)}")
            return {"error": str(e)}, 500

    @staticmethod
    def store_webhook_event(event):
        """Store the webhook event in the database."""
        try:
            webhook_event = StripeWebhookEvent(
                stripe_event_id=event.id,
                event_type=event["type"],
                event_data=event,
                status="received",
            )
            db.session.add(webhook_event)
            db.session.commit()
            return webhook_event
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to store webhook event: {str(e)}")
            return None

    @staticmethod
    def process_webhook_event(event, webhook_event):
        """Process the webhook event."""
        try:
            # Handle the checkout.session.completed event
            if event["type"] == "checkout.session.completed":
                session = event["data"]["object"]
                user_id = int(session["metadata"]["user_id"])
                plan_name = session["metadata"]["plan_name"]

                # Determine trial days
                trial_days = (
                    TRIAL_DAYS
                    if plan_name == "Pro"
                    and not any(
                        plan.plan_name == "Pro" for plan in User.query.get(user_id).user_plans
                    )
                    else None
                )

                success = assign_plan_to_user(
                    user_id=user_id, plan_name=plan_name, trial_days=trial_days
                )

                if not success:
                    error_msg = f"Failed to assign plan {plan_name} to user {user_id}"
                    logging.error(error_msg)
                    StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)
                    return {"error": "Failed to assign plan"}, 400

                logging.info(f"Successfully processed subscription for user {user_id}")

            # Handle the invoice.payment_succeeded event
            elif event["type"] == "invoice.payment_succeeded":
                invoice = event["data"]["object"]
                subscription = stripe.Subscription.retrieve(invoice.subscription)
                user_id = int(invoice["metadata"]["user_id"])
                plan_name = invoice["metadata"]["plan_name"]

                # Reassign the plan to update the end date
                success = assign_plan_to_user(user_id=user_id, plan_name=plan_name)
                if success:
                    logging.info(
                        f"Updated subscription:{subscription.id} for user {user_id} \
                            after successful payment"
                    )
                else:
                    error_msg = (
                        f"Failed to update subscription:{subscription.id} for user {user_id}"
                    )
                    logging.error(error_msg)
                    StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)

            # Handle the invoice.payment_failed event
            elif event["type"] == "invoice.payment_failed":
                invoice = event["data"]["object"]
                user_id = int(invoice["metadata"]["user_id"])
                logging.warning(f"Payment failed for user {user_id}")

                # Cancel the subscription
                subscription_id = invoice.get("subscription")
                if subscription_id:
                    stripe.Subscription.delete(subscription_id)

                # Switch user to free plan
                success = assign_plan_to_user(user_id=user_id, plan_name="Free")
                if success:
                    logging.info(f"Switched user {user_id} to Free plan due to payment failure")
                else:
                    error_msg = f"Failed to switch user {user_id} to Free plan"
                    logging.error(error_msg)
                    StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)

            # Mark webhook as processed
            StripeWebhookResource.update_webhook_status(webhook_event, "processed")

            return {"status": "success"}

        except Exception as e:
            error_msg = f"Error processing webhook: {str(e)}"
            logging.error(error_msg)
            StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)
            return {"error": str(e)}, 500

    @staticmethod
    def update_webhook_status(webhook_event, status, error_message=None):
        """Update the status of the webhook event."""
        if webhook_event:
            try:
                webhook_event.status = status
                webhook_event.processed_at = datetime.utcnow()
                if error_message:
                    webhook_event.error_message = error_message
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logging.error(f"Failed to update webhook event status: {str(e)}")


@stripe_ns.route("/health")
class StripeHealthResource(Resource):
    """Resource for checking Stripe health status."""

    @stripe_ns.doc(security="Bearer Auth")
    # @jwt_required()
    def get(self):
        """Check if Stripe is properly configured and accessible."""
        try:
            # Check if keys are configured
            publishable_key = current_app.config["STRIPE_PUBLISHABLE_KEY"]
            secret_key = current_app.config["STRIPE_SECRET_KEY"]
            webhook_secret = current_app.config["STRIPE_WEBHOOK_SECRET"]

            if not all([publishable_key, secret_key, webhook_secret]):
                missing_keys = []
                if not publishable_key:
                    missing_keys.append("STRIPE_PUBLISHABLE_KEY")
                if not secret_key:
                    missing_keys.append("STRIPE_SECRET_KEY")
                if not webhook_secret:
                    missing_keys.append("STRIPE_WEBHOOK_SECRET")
                return {
                    "status": "error",
                    "message": "Missing Stripe configuration",
                    "details": f"Missing keys: {', '.join(missing_keys)}",
                }, 500

            # Initialize Stripe with the secret key
            stripe.api_key = secret_key

            # Make a test API call
            stripe.PaymentMethod.list(limit=1)

            return {
                "status": "healthy",
                "message": "Stripe is properly configured and accessible",
                "details": {
                    "publishable_key_configured": bool(publishable_key),
                    "secret_key_configured": bool(secret_key),
                    "webhook_secret_configured": bool(webhook_secret),
                },
            }

        except stripe.error.AuthenticationError as e:
            logging.error(f"Stripe authentication error: {str(e)}")
            return {"status": "error", "message": "Invalid Stripe API keys", "details": str(e)}, 500
        except Exception as e:
            logging.error(f"Error checking Stripe health: {str(e)}")
            return {
                "status": "error",
                "message": "Failed to check Stripe health",
                "details": str(e),
            }, 500
