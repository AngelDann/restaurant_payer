"""
Stripe webhook business handlers for LandingPageCreator.

Each handler receives only the expanded data.object as a plain dict.
Wire these to domain models when subscription/customer tables exist.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from apps.billing.services import broadcast_order_update
from apps.restaurants.models import OrderPayment, Restaurant

logger = logging.getLogger(__name__)

StripeObjectDict = dict[str, Any]
Handler = Callable[[StripeObjectDict], None]


def handle_checkout_session_completed(data_object: StripeObjectDict) -> None:
    # TODO: read metadata (tenant/user/org id), persist Stripe customer, subscription, session id.
    logger.info(
        "checkout.session.completed id=%s metadata=%s",
        data_object.get("id"),
        data_object.get("metadata"),
    )


def handle_customer_subscription_updated(data_object: StripeObjectDict) -> None:
    # TODO: locate internal entity by subscription id or customer metadata.
    logger.info(
        "customer.subscription.updated id=%s customer=%s status=%s",
        data_object.get("id"),
        data_object.get("customer"),
        data_object.get("status"),
    )


def handle_customer_subscription_deleted(data_object: StripeObjectDict) -> None:
    # TODO: locate internal entity by subscription id or customer metadata.
    logger.info(
        "customer.subscription.deleted id=%s customer=%s",
        data_object.get("id"),
        data_object.get("customer"),
    )


def handle_invoice_payment_failed(data_object: StripeObjectDict) -> None:
    # TODO: locate subscription/customer from invoice and mark past_due or notify.
    logger.info(
        "invoice.payment_failed id=%s subscription=%s customer=%s",
        data_object.get("id"),
        data_object.get("subscription"),
        data_object.get("customer"),
    )


def handle_invoice_payment_succeeded(data_object: StripeObjectDict) -> None:
    # TODO: extend access / reconcile billing period from invoice.
    logger.info(
        "invoice.payment_succeeded id=%s subscription=%s customer=%s",
        data_object.get("id"),
        data_object.get("subscription"),
        data_object.get("customer"),
    )


def handle_charge_refunded(data_object: StripeObjectDict) -> None:
    logger.info("charge.refunded id=%s amount_refunded=%s", data_object.get("id"), data_object.get("amount_refunded"))


def handle_refund_created(data_object: StripeObjectDict) -> None:
    logger.info("refund.created id=%s charge=%s status=%s", data_object.get("id"), data_object.get("charge"), data_object.get("status"))


def handle_refund_updated(data_object: StripeObjectDict) -> None:
    logger.info("refund.updated id=%s charge=%s status=%s", data_object.get("id"), data_object.get("charge"), data_object.get("status"))


def handle_charge_refund_updated(data_object: StripeObjectDict) -> None:
    logger.info(
        "charge.refund.updated id=%s charge=%s status=%s",
        data_object.get("id"),
        data_object.get("charge"),
        data_object.get("status"),
    )


def _extract_payment_method_label(data_object: StripeObjectDict) -> str:
    """Extract a human-readable or normalized payment method label from Stripe PaymentIntent."""
    charges = data_object.get("charges", {}).get("data", [])
    if charges:
        charge = charges[0]
        pm_details = charge.get("payment_method_details", {})
        pm_type = pm_details.get("type")
        if pm_type == "card":
            wallet = pm_details.get("card", {}).get("wallet")
            if wallet and isinstance(wallet, dict) and wallet.get("type"):
                return str(wallet.get("type"))
            return "card"
        if pm_type:
            return str(pm_type)

    metadata = data_object.get("metadata") or {}
    if metadata.get("payment_method_label"):
        return str(metadata.get("payment_method_label"))

    pm_types = data_object.get("payment_method_types")
    if pm_types and isinstance(pm_types, list) and pm_types:
        return str(pm_types[0])

    return "card"


def handle_payment_intent_succeeded(data_object: StripeObjectDict) -> None:
    """
    Handle payment_intent.succeeded webhook.
    Marks OrderPayment as succeeded, updates order totals, and broadcasts table update.
    """
    intent_id = data_object.get("id")
    metadata = data_object.get("metadata") or {}
    payment_id = metadata.get("payment_id")

    payment = None
    if intent_id:
        payment = OrderPayment.objects.filter(stripe_payment_intent_id=intent_id).first()
    if not payment and payment_id:
        try:
            payment = OrderPayment.objects.filter(id=payment_id).first()
        except (ValueError, TypeError):
            pass

    if not payment:
        logger.warning(
            "OrderPayment not found for payment_intent.succeeded id=%s metadata=%s",
            intent_id,
            metadata,
        )
        return

    payment_method_label = _extract_payment_method_label(data_object)
    payment.mark_succeeded(payment_method_label=payment_method_label)
    payment.order.refresh_from_db()
    broadcast_order_update(payment.order)
    logger.info(
        "OrderPayment #%s (order #%s) marked succeeded with method=%s",
        payment.id,
        payment.order_id,
        payment_method_label,
    )


def handle_payment_intent_failed(data_object: StripeObjectDict) -> None:
    """
    Handle payment_intent.payment_failed webhook.
    Marks OrderPayment as failed and broadcasts table update.
    """
    intent_id = data_object.get("id")
    metadata = data_object.get("metadata") or {}
    payment_id = metadata.get("payment_id")

    payment = None
    if intent_id:
        payment = OrderPayment.objects.filter(stripe_payment_intent_id=intent_id).first()
    if not payment and payment_id:
        try:
            payment = OrderPayment.objects.filter(id=payment_id).first()
        except (ValueError, TypeError):
            pass

    if not payment:
        logger.warning(
            "OrderPayment not found for payment_intent.payment_failed id=%s metadata=%s",
            intent_id,
            metadata,
        )
        return

    payment.status = OrderPayment.Status.FAILED
    payment.save(update_fields=["status"])
    payment.order.refresh_from_db()
    broadcast_order_update(payment.order)
    logger.info(
        "OrderPayment #%s (order #%s) marked failed",
        payment.id,
        payment.order_id,
    )


def handle_account_updated(data_object: StripeObjectDict) -> None:
    """
    Handle account.updated webhook.
    Updates Restaurant.stripe_onboarding_completed if charges are enabled and details submitted.
    """
    acct_id = data_object.get("id")
    if not acct_id:
        return

    restaurant = Restaurant.objects.filter(stripe_account_id=acct_id).first()
    if not restaurant:
        logger.warning(
            "Restaurant not found for account.updated stripe_account_id=%s", acct_id
        )
        return

    charges_enabled = bool(data_object.get("charges_enabled"))
    details_submitted = bool(data_object.get("details_submitted"))

    is_completed = bool(charges_enabled and details_submitted)
    restaurant.stripe_onboarding_completed = is_completed
    restaurant.save(update_fields=["stripe_onboarding_completed", "updated_at"])
    logger.info(
        "Restaurant #%s (%s) onboarding completed=%s (charges_enabled=%s, details_submitted=%s)",
        restaurant.id,
        restaurant.slug,
        is_completed,
        charges_enabled,
        details_submitted,
    )


STRIPE_WEBHOOK_HANDLERS: dict[str, Handler] = {
    "checkout.session.completed": handle_checkout_session_completed,
    "customer.subscription.updated": handle_customer_subscription_updated,
    "customer.subscription.deleted": handle_customer_subscription_deleted,
    "invoice.payment_failed": handle_invoice_payment_failed,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "charge.refunded": handle_charge_refunded,
    "refund.created": handle_refund_created,
    "refund.updated": handle_refund_updated,
    "charge.refund.updated": handle_charge_refund_updated,
    "payment_intent.succeeded": handle_payment_intent_succeeded,
    "payment_intent.payment_failed": handle_payment_intent_failed,
    "account.updated": handle_account_updated,
}


def dispatch_stripe_event(event_type: str, data_object: StripeObjectDict) -> None:
    handler = STRIPE_WEBHOOK_HANDLERS.get(event_type)
    if handler is None:
        return
    handler(data_object)
