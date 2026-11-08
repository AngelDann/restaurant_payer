from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import stripe
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

from apps.restaurants.models import OrderPayment, Restaurant, TableOrder

logger = logging.getLogger(__name__)


class StripeGatewayError(Exception):
    """Raised when Stripe configuration is missing or a Stripe API operation fails."""


def is_stripe_configured() -> bool:
    """Check if Stripe API keys are configured in Django settings."""
    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    public_key = (getattr(settings, "STRIPE_PUBLIC_KEY", "") or "").strip()
    return bool(secret_key and public_key)


def create_or_get_connected_account(restaurant: Restaurant) -> str:
    """
    Get or create a Stripe Express Connected Account for a restaurant (Mexico MXN).
    Requires STRIPE_SECRET_KEY.
    """
    if restaurant.stripe_account_id:
        return restaurant.stripe_account_id

    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise StripeGatewayError("STRIPE_SECRET_KEY no está configurada.")

    stripe.api_key = secret_key
    try:
        acct = stripe.Account.create(
            type="express",
            country="MX",
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True},
            },
            business_type="company",
            metadata={
                "restaurant_id": str(restaurant.id),
                "slug": restaurant.slug,
            },
        )
    except stripe.StripeError as exc:
        logger.exception(
            "Failed to create connected account for restaurant %s: %s",
            restaurant.slug,
            exc,
        )
        raise StripeGatewayError(str(exc)) from exc

    account_id = acct["id"]
    restaurant.stripe_account_id = account_id
    restaurant.save(update_fields=["stripe_account_id", "updated_at"])
    return account_id


def create_account_onboarding_link(
    restaurant: Restaurant, return_url: str, refresh_url: str
) -> str:
    """
    Generate a Stripe Express onboarding AccountLink.
    Requires STRIPE_SECRET_KEY and creates/retrieves connected account.
    """
    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise StripeGatewayError("STRIPE_SECRET_KEY no está configurada.")

    account_id = create_or_get_connected_account(restaurant)

    stripe.api_key = secret_key
    try:
        link = stripe.AccountLink.create(
            account=account_id,
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )
        return link["url"]
    except stripe.StripeError as exc:
        logger.exception(
            "Failed to create onboarding link for restaurant %s: %s",
            restaurant.slug,
            exc,
        )
        raise StripeGatewayError(str(exc)) from exc


def create_account_login_link(restaurant: Restaurant) -> str:
    """
    Generate a single-use login link to the Stripe Express Dashboard for an onboarded restaurant.
    Requires STRIPE_SECRET_KEY and that restaurant has a stripe_account_id.
    """
    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise StripeGatewayError("STRIPE_SECRET_KEY no está configurada.")

    if not restaurant.stripe_account_id:
        raise StripeGatewayError("El restaurante no tiene una cuenta de Stripe conectada.")

    stripe.api_key = secret_key
    try:
        login_link = stripe.Account.create_login_link(restaurant.stripe_account_id)
        return login_link["url"]
    except stripe.StripeError as exc:
        logger.exception(
            "Failed to create login link for restaurant %s: %s",
            restaurant.slug,
            exc,
        )
        raise StripeGatewayError(str(exc)) from exc


def create_order_payment_intent(order_payment: OrderPayment) -> dict[str, Any]:
    """
    Create a real Stripe PaymentIntent for an OrderPayment.
    Requires STRIPE_SECRET_KEY and that restaurant has completed Stripe Connect onboarding.
    Supports platform fee and direct transfer to connected account (Stripe Connect).
    """
    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise StripeGatewayError("STRIPE_SECRET_KEY no está configurada.")

    restaurant = order_payment.order.restaurant
    if not restaurant.can_accept_stripe_split:
        raise StripeGatewayError(
            "El restaurante aún no tiene una cuenta de Stripe Connect activa para recibir pagos."
        )

    if not order_payment.pk:
        order_payment.save()

    amount_cents = int((order_payment.total_amount * 100).quantize(Decimal("1")))
    fee_pesos = restaurant.calculate_platform_fee(order_payment.subtotal_amount)
    fee_cents = int((fee_pesos * 100).quantize(Decimal("1")))
    currency = (restaurant.currency or "mxn").lower()

    stripe.api_key = secret_key
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            automatic_payment_methods={"enabled": True},
            application_fee_amount=fee_cents,
            transfer_data={"destination": restaurant.stripe_account_id},
            metadata={
                "order_id": str(order_payment.order_id),
                "payment_id": str(order_payment.id),
                "restaurant_slug": restaurant.slug,
                "table_number": str(order_payment.order.table.number),
            },
        )
    except stripe.StripeError as exc:
        logger.exception(
            "Failed to create PaymentIntent for payment #%s: %s", order_payment.id, exc
        )
        raise StripeGatewayError(str(exc)) from exc

    order_payment.platform_fee_amount = fee_pesos
    order_payment.stripe_payment_intent_id = intent["id"]
    order_payment.stripe_client_secret = intent.get("client_secret") or ""
    order_payment.save(
        update_fields=[
            "platform_fee_amount",
            "stripe_payment_intent_id",
            "stripe_client_secret",
        ]
    )
    return {
        "id": intent["id"],
        "client_secret": order_payment.stripe_client_secret,
    }


def verify_and_complete_payment_intent(order_payment: OrderPayment) -> bool:
    """
    Verify payment status with Stripe and mark OrderPayment as succeeded if verified.
    """
    if order_payment.status == OrderPayment.Status.SUCCEEDED:
        return True

    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        raise StripeGatewayError("STRIPE_SECRET_KEY no está configurada.")

    if not order_payment.stripe_payment_intent_id:
        return False

    stripe.api_key = secret_key
    try:
        intent = stripe.PaymentIntent.retrieve(order_payment.stripe_payment_intent_id)
    except stripe.StripeError as exc:
        logger.exception(
            "Failed to retrieve PaymentIntent %s: %s",
            order_payment.stripe_payment_intent_id,
            exc,
        )
        raise StripeGatewayError(str(exc)) from exc

    if intent.get("status") == "succeeded":
        order_payment.mark_succeeded()
        broadcast_order_update(order_payment.order)
        return True

    return False


def broadcast_order_update(order: TableOrder) -> None:
    """
    Broadcast order updates to the table channel group via Django Channels.
    Fails safely without raising if Channels layer is not configured or offline.
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        group_name = f"table_{order.restaurant.slug}_{order.table.number}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "order_updated",
                "order_id": order.id,
                "status": order.status,
                "amount_paid": str(order.amount_paid),
                "amount_remaining": str(order.amount_remaining),
            },
        )
    except Exception as exc:
        logger.warning(
            "broadcast_order_update failed for order #%s: %s",
            getattr(order, "id", None),
            exc,
        )
