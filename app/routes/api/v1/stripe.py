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
from app.models.plan import Plan, UserPlan
from app.models.stripe_webhook import StripeWebhookEvent
from app.models.user import User

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
            # Get Stripe secret key from config
            stripe_secret_key = current_app.config.get("STRIPE_SECRET_KEY")

            # Check if key exists
            if not stripe_secret_key:
                error_msg = "STRIPE_SECRET_KEY not found in application configuration"
                logging.error(error_msg)
                raise ValueError(error_msg)

            # Initialize Stripe with the secret key
            stripe.api_key = stripe_secret_key

            data = request.get_json()
            user_id = get_jwt_identity()

            # Optional billing interval from request
            billing_interval = data.get("billing_interval", "month")  # Default to monthly

            # Get user details
            user = User.query.get(user_id)
            if not user:
                return {"error": "User not found"}, 404

            # Get plan details from database
            plan = Plan.query.get(data["plan_id"])
            if not plan:
                return {"error": "Plan not found"}, 404

            # Check if plan has a product ID
            if not plan.stripe_product_id:
                return {"error": "Plan is not linked to a Stripe product"}, 400

            # Determine which price to use
            price_id = None

            # If a specific price ID is requested, use that
            if "price_id" in data and data["price_id"]:
                price_id = data["price_id"]
            # Otherwise, find a price based on the billing interval
            else:
                # Get all prices for this product
                prices = stripe.Price.list(
                    product=plan.stripe_product_id,
                    active=True,
                )

                # Filter for the desired interval
                matching_prices = [
                    p
                    for p in prices.data
                    if p.recurring and p.recurring.interval == billing_interval
                ]

                if matching_prices:
                    price_id = matching_prices[0].id
                else:
                    return {"error": f"No {billing_interval}ly price found for this plan"}, 400

            # Check if user has a Stripe customer ID
            if not user.stripe_customer_id:
                # Create a new Stripe customer
                customer = stripe.Customer.create(
                    email=user.email,
                )
                # Save the customer ID to the user model
                user.stripe_customer_id = customer.id
                db.session.commit()

            # Check if user has previously subscribed to the Pro plan
            has_had_pro_plan = any(
                user_plan.plan.plan_name == "Pro" for user_plan in user.user_plans
            )

            # Create Stripe checkout session
            subscription_data = {}
            if not has_had_pro_plan:
                subscription_data["trial_period_days"] = current_app.config.get("STRIPE_TRIAL_DAYS")

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="subscription",
                customer=user.stripe_customer_id,
                line_items=[
                    {
                        "price": price_id,
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
                    "billing_interval": billing_interval,
                },
            )

            return {"sessionId": checkout_session.id}
        except Exception as e:
            logging.error(f"Error creating checkout session: {str(e)}", exc_info=True)
            return {"error": str(e)}, 500


@stripe_ns.route("/webhook")
class StripeWebhookResource(Resource):
    """Resource for handling Stripe webhooks."""

    def post(self):
        """Handle Stripe webhook events."""
        try:
            # Get Stripe secret key from config
            stripe_secret_key = current_app.config.get("STRIPE_SECRET_KEY")

            # Check if key exists
            if not stripe_secret_key:
                error_msg = "STRIPE_SECRET_KEY not found in application configuration"
                logging.error(error_msg)
                raise ValueError(error_msg)

            # Initialize Stripe with the secret key
            stripe.api_key = stripe_secret_key
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
            # Log only essential event information to avoid overwhelming logs
            logging.info(
                f"Storing webhook event: id={event.id}, type={event['type']}, "
                f"created={event.created}, api_version={event.api_version}"
            )
            webhook_event = StripeWebhookEvent(
                stripe_event_id=event.id,
                event_type=event["type"],
                event_data=event,
                status="received",
            )
            db.session.add(webhook_event)
            db.session.commit()
            logging.info(f"Successfully stored webhook event: id={event.id}")
            return webhook_event
        except Exception as e:
            db.session.rollback()
            logging.error(f"Failed to store webhook event: {str(e)}")
            return None

    @staticmethod
    def update_subscription_metadata(subscription_id, metadata):
        """Update the metadata of a Stripe subscription.

        This ensures that future invoices will have the correct metadata.

        Parameters
        ----------
        subscription_id : str
            The Stripe subscription ID.
        metadata : dict
            The metadata to set on the subscription.

        Returns
        -------
        bool
            True if successful, False otherwise.
        """
        try:
            stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
            stripe.Subscription.modify(subscription_id, metadata=metadata)
            return True
        except Exception as e:
            logging.error(f"Error updating subscription metadata: {str(e)}")
            return False

    @staticmethod
    def process_webhook_event(event, webhook_event):
        """Process the webhook event."""
        try:
            # Handle the checkout.session.completed event
            if event["type"] == "checkout.session.completed":
                session = event["data"]["object"]
                user_id = int(session["metadata"]["user_id"])
                plan_name = session["metadata"]["plan_name"]
                billing_interval = session["metadata"].get("billing_interval", "month")

                # Get the subscription ID from the session
                subscription_id = session.get("subscription")

                # Update subscription metadata to ensure it's available for future invoices
                if subscription_id:
                    StripeWebhookResource.update_subscription_metadata(
                        subscription_id,
                        {
                            "user_id": str(user_id),
                            "plan_name": plan_name,
                            "billing_interval": billing_interval,
                        },
                    )

                success = assign_plan_to_user(
                    user_id=user_id,
                    plan_name=plan_name,
                    subscription_id=subscription_id,
                    billing_interval=billing_interval,
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
                subscription_id = invoice.get("subscription")

                # First try to get user_id from invoice metadata
                if invoice.get("metadata") and "user_id" in invoice["metadata"]:
                    user_id = int(invoice["metadata"]["user_id"])
                    plan_name = invoice["metadata"]["plan_name"]
                else:
                    # If not in invoice metadata, retrieve from subscription
                    subscription = stripe.Subscription.retrieve(subscription_id)

                    # Try to find user by stripe_customer_id
                    user = User.query.filter_by(stripe_customer_id=subscription.customer).first()
                    if not user:
                        error_msg = (
                            f"User with Stripe customer ID {subscription.customer} not found"
                        )
                        logging.error(error_msg)
                        StripeWebhookResource.update_webhook_status(
                            webhook_event, "failed", error_msg
                        )
                        return {"error": error_msg}, 404

                    user_id = user.id

                    # Get plan name from subscription metadata or items
                    if subscription.get("metadata") and "plan_name" in subscription.metadata:
                        plan_name = subscription.metadata["plan_name"]
                    else:
                        # Try to get plan from subscription items
                        subscription_item = (
                            subscription.items.data[0] if subscription.items.data else None
                        )
                        if (
                            subscription_item
                            and subscription_item.price
                            and subscription_item.price.metadata
                        ):
                            plan_name = subscription_item.price.metadata.get("plan_name")
                        else:
                            # Default to current plan if we can't determine
                            current_user_plan = UserPlan.query.filter_by(
                                user_id=user_id,
                                is_active=True,
                                stripe_subscription_id=subscription_id,
                            ).first()
                            if current_user_plan and current_user_plan.plan:
                                plan_name = current_user_plan.plan.plan_name
                            else:
                                error_msg = f"Could not determine plan name for subscription \
{subscription_id}"
                                logging.error(error_msg)
                                StripeWebhookResource.update_webhook_status(
                                    webhook_event, "failed", error_msg
                                )
                                return {"error": error_msg}, 400

                # Reassign the plan to update the end date
                success = assign_plan_to_user(user_id=user_id, plan_name=plan_name)
                if success:
                    logging.info(
                        f"Updated subscription:{subscription_id} for user {user_id} \
                            after successful payment"
                    )
                else:
                    error_msg = (
                        f"Failed to update subscription:{subscription_id} for user {user_id}"
                    )
                    logging.error(error_msg)
                    StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)

            # Handle the invoice.payment_failed event
            elif event["type"] == "invoice.payment_failed":
                invoice = event["data"]["object"]
                subscription_id = invoice.get("subscription")

                # First try to get user_id from invoice metadata
                if invoice.get("metadata") and "user_id" in invoice["metadata"]:
                    user_id = int(invoice["metadata"]["user_id"])
                else:
                    # If not in invoice metadata, retrieve from subscription
                    if subscription_id:
                        subscription = stripe.Subscription.retrieve(subscription_id)

                        # Try to find user by stripe_customer_id
                        user = User.query.filter_by(
                            stripe_customer_id=subscription.customer
                        ).first()
                        if not user:
                            error_msg = (
                                f"User with Stripe customer ID {subscription.customer} not found"
                            )
                            logging.error(error_msg)
                            StripeWebhookResource.update_webhook_status(
                                webhook_event, "failed", error_msg
                            )
                            return {"error": error_msg}, 404

                        user_id = user.id
                    else:
                        error_msg = "No subscription ID found in invoice and no user_id in metadata"
                        logging.error(error_msg)
                        StripeWebhookResource.update_webhook_status(
                            webhook_event, "failed", error_msg
                        )
                        return {"error": error_msg}, 400

                logging.warning(f"Payment failed for user {user_id}")

                # Cancel the subscription
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

            # Handle the customer.subscription.updated event (subscription cancellation)
            elif event["type"] == "customer.subscription.updated":
                subscription = event["data"]["object"]
                customer_id = subscription.get("customer")
                status = subscription.get("status")
                cancel_at_period_end = subscription.get("cancel_at_period_end", False)
                current_period_end = subscription.get("current_period_end")

                # Find the user by Stripe customer ID
                user = User.query.filter_by(stripe_customer_id=customer_id).first()
                if not user:
                    error_msg = f"User with Stripe customer ID {customer_id} not found"
                    logging.error(error_msg)
                    StripeWebhookResource.update_webhook_status(webhook_event, "failed", error_msg)
                    return {"error": error_msg}, 404

                # If subscription is canceled immediately
                if status == "canceled":
                    # Assign Free plan to the user
                    success = assign_plan_to_user(user_id=user.id, plan_name="Free")

                    if success:
                        logging.info(
                            f"Switched user {user.id} to Free plan due to subscription cancellation"
                        )
                    else:
                        error_msg = (
                            f"Failed to switch user {user.id} to Free plan after cancellation"
                        )
                        logging.error(error_msg)
                        StripeWebhookResource.update_webhook_status(
                            webhook_event, "failed", error_msg
                        )
                        return {"error": error_msg}, 500

                # If subscription is set to cancel at the end of the billing period
                elif cancel_at_period_end and current_period_end:
                    # Get the current active plan for the user
                    current_user_plan = UserPlan.query.filter_by(
                        user_id=user.id,
                        is_active=True,
                        stripe_subscription_id=subscription.get("id"),
                    ).first()

                    if current_user_plan:
                        # Set the end date to the end of the current billing period
                        end_date = datetime.fromtimestamp(current_period_end).date()
                        current_user_plan.end_date = end_date

                        try:
                            db.session.commit()
                            logging.info(
                                f"Updated end date to {end_date} for user {user.id}'s "
                                f"subscription due to cancellation at period end"
                            )
                            # Mark the webhook event as processed
                            StripeWebhookResource.update_webhook_status(webhook_event, "processed")
                            return {
                                "success": True,
                                "message": "Subscription end date updated",
                            }, 200
                        except Exception as e:
                            db.session.rollback()
                            error_msg = (
                                f"Failed to update end date for user {user.id}'s "
                                f"subscription: {str(e)}"
                            )
                            logging.error(error_msg)
                            StripeWebhookResource.update_webhook_status(
                                webhook_event, "failed", error_msg
                            )
                            return {"error": error_msg}, 500
                    else:
                        error_msg = f"No active subscription found for user {user.id}"
                        logging.warning(error_msg)
                        return {"warning": error_msg}, 200
                else:
                    logging.info(
                        f"Received subscription update with status: {status}, "
                        f"cancel_at_period_end: {cancel_at_period_end}, no action needed"
                    )
                    return {
                        "success": True,
                        "message": "No action needed for this subscription update",
                    }, 200

            # Mark webhook as processed
            StripeWebhookResource.update_webhook_status(webhook_event, "processed")

            return {"status": "success"}

        except Exception as e:
            error_msg = f"Error processing webhook: {str(e)}"
            logging.error(error_msg, exc_info=True)
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
        # decided to disable this endpoint for now as it's not needed. for future debugging,
        # Check if health endpoint is enabled
        if not current_app.config.get("ENABLE_STRIPE_HEALTH_ENDPOINT", False):
            return {"status": "disabled", "message": "Stripe health endpoint is disabled"}, 403

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


@stripe_ns.route("/create-billing-portal-session")
class CreateBillingPortalSessionResource(Resource):
    """Resource to create a Stripe billing portal session."""

    @stripe_ns.doc(security="Bearer Auth")
    @jwt_required()
    def post(self):
        """Create a Stripe billing portal session for the authenticated user."""
        try:
            # Get the current user from the JWT token
            user_id = get_jwt_identity()
            user = User.query.get(user_id)

            if not user:
                return {"status": "error", "message": "User not found"}, 404

            if not user.stripe_customer_id:
                return {"status": "error", "message": "No Stripe customer found for this user"}, 400

            # Initialize Stripe with the secret key
            stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]

            # Create a billing portal session
            session = stripe.billing_portal.Session.create(
                customer=user.stripe_customer_id,
                return_url=f"{request.host_url}profile",
            )

            # Return the URL to redirect the customer to
            return {"status": "success", "url": session.url}, 200

        except Exception as e:
            logging.error(f"Failed to create billing portal session: {str(e)}")
            return {"status": "error", "message": "Failed to create billing portal session"}, 500
