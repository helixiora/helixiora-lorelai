"""Stripe helper functions."""

import logging

import stripe
from flask import current_app


def get_stripe_product_details(product_id: str) -> dict | None:
    """Fetch product details from Stripe.

    Parameters
    ----------
    product_id : str
        The Stripe product ID.

    Returns
    -------
    Optional[Dict]
        A dictionary containing the product details, or None if the product was not found.
    """
    try:
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
        product = stripe.Product.retrieve(product_id)
        return {
            "name": product.name,
            "description": product.description,
            "active": product.active,
            "metadata": product.metadata,
        }
    except Exception as e:
        logging.error(f"Error fetching Stripe product {product_id}: {str(e)}")
        return None


def get_stripe_prices(product_id: str, active_only: bool = True) -> list[dict]:
    """Fetch prices for a Stripe product.

    Parameters
    ----------
    product_id : str
        The Stripe product ID.
    active_only : bool, optional
        Whether to only return active prices, by default True.

    Returns
    -------
    List[Dict]
        A list of dictionaries containing price details.
    """
    try:
        stripe.api_key = current_app.config["STRIPE_SECRET_KEY"]
        prices = stripe.Price.list(product=product_id, active=active_only)

        result = []
        for price in prices.data:
            price_data = {
                "id": price.id,
                "currency": price.currency,
                "unit_amount": price.unit_amount / 100.0,  # Convert from cents to dollars
                "active": price.active,
                "nickname": price.nickname,
                "metadata": price.metadata,
            }

            if price.recurring:
                price_data["recurring"] = {
                    "interval": price.recurring.interval,
                    "interval_count": price.recurring.interval_count,
                }

            result.append(price_data)

        return result
    except Exception as e:
        logging.error(f"Error fetching Stripe prices for product {product_id}: {str(e)}")
        return []


def get_plan_price(product_id: str, interval: str = "month") -> float | None:
    """Get the price for a plan with a specific billing interval.

    Parameters
    ----------
    product_id : str
        The Stripe product ID.
    interval : str, optional
        The billing interval (month, year), by default "month".

    Returns
    -------
    Optional[float]
        The price in dollars, or None if no matching price was found.
    """
    prices = get_stripe_prices(product_id)

    # Filter for the desired interval
    matching_prices = [
        p for p in prices if p.get("recurring") and p["recurring"]["interval"] == interval
    ]

    if matching_prices:
        return matching_prices[0]["unit_amount"]

    return None


def get_plan_description(product_id: str) -> str | None:
    """Get the description for a plan.

    Parameters
    ----------
    product_id : str
        The Stripe product ID.

    Returns
    -------
    Optional[str]
        The description, or None if the product was not found.
    """
    product = get_stripe_product_details(product_id)

    if product:
        return product.get("description")

    return None
