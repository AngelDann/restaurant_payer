"""
Stripe webhook business handlers for LandingPageCreator.

Each handler receives only the expanded data.object as a plain dict.
Wire these to domain models when subscription/customer tables exist.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

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
}


def dispatch_stripe_event(event_type: str, data_object: StripeObjectDict) -> None:
    handler = STRIPE_WEBHOOK_HANDLERS.get(event_type)
    if handler is None:
        return
    handler(data_object)
