"""
Stripe webhook (POST /billing/stripe/webhook/):

Environment:
  STRIPE_SECRET_KEY — API key used by the Stripe SDK (required before verify).
  STRIPE_WEBHOOK_SECRET — endpoint signing secret (whsec_...).

Stripe Dashboard (or CLI: stripe listen --forward-to localhost:8000/billing/stripe/webhook/):
  Enable these webhook events:
    checkout.session.completed
    customer.subscription.updated
    customer.subscription.deleted
    invoice.payment_failed
    invoice.payment_succeeded
    charge.refunded
    refund.created
    refund.updated
    charge.refund.updated
"""

from __future__ import annotations

import logging

import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.billing.models import StripeWebhookEvent
from apps.billing.stripe_handlers import dispatch_stripe_event

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("Billing / Stripe integration placeholder.")


def _stripe_object_to_dict(obj: object) -> dict:
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    raise TypeError("Expected Stripe object with to_dict()")


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        api_key = (settings.STRIPE_SECRET_KEY or "").strip()
        webhook_secret = (settings.STRIPE_WEBHOOK_SECRET or "").strip()
        if not api_key:
            return HttpResponseBadRequest("STRIPE_SECRET_KEY is not configured")
        if not webhook_secret:
            return HttpResponseBadRequest("STRIPE_WEBHOOK_SECRET is not configured")

        stripe.api_key = api_key

        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        if not sig_header:
            return HttpResponseBadRequest("Missing Stripe-Signature header")

        payload: bytes = request.body

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.SignatureVerificationError as exc:
            logger.warning("Stripe webhook signature verification failed: %s", exc)
            return HttpResponseBadRequest("Invalid Stripe webhook signature")
        except ValueError as exc:
            logger.warning("Stripe webhook invalid payload: %s", exc)
            return HttpResponseBadRequest("Invalid webhook payload")

        try:
            event_id = event["id"]
        except KeyError:
            return HttpResponseBadRequest("Event missing id")
        if not isinstance(event_id, str):
            return HttpResponseBadRequest("Event missing id")

        try:
            with transaction.atomic():
                StripeWebhookEvent.objects.create(event_id=event_id)
        except IntegrityError:
            return JsonResponse({"ok": True}, status=200)

        try:
            event_type = event["type"]
        except KeyError:
            event_type = ""
        data_object = None
        try:
            data_object = event["data"]["object"]
        except KeyError:
            pass
        if data_object is None:
            logger.warning("Stripe event %s has no data.object", event_id)
        else:
            try:
                obj_dict = _stripe_object_to_dict(data_object)
            except TypeError:
                logger.exception("Could not convert data.object for event %s", event_id)
            else:
                try:
                    dispatch_stripe_event(str(event_type), obj_dict)
                except Exception:
                    logger.exception("Stripe webhook handler failed for %s", event_type)

        return JsonResponse({"ok": True}, status=200)


stripe_webhook = StripeWebhookView.as_view()
