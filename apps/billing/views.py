"""
Stripe webhook and billing views.

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
    payment_intent.succeeded
    payment_intent.payment_failed
    account.updated
"""

from __future__ import annotations

import logging
from pathlib import Path

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.billing.models import StripeWebhookEvent
from apps.billing.services import (
    StripeGatewayError,
    create_account_login_link,
    create_account_onboarding_link,
)
from apps.billing.stripe_handlers import dispatch_stripe_event
from apps.restaurants.models import Restaurant

logger = logging.getLogger(__name__)


def index(request):
    return HttpResponse("Billing / Stripe integration placeholder.")


def apple_pay_domain_association(request):
    """
    Serve Apple Pay domain association file from settings content or disk.
    """
    content = getattr(settings, "APPLE_PAY_DOMAIN_ASSOCIATION_CONTENT", "") or ""
    if not content:
        base_dir = getattr(settings, "BASE_DIR", None)
        if base_dir:
            file_path = (
                Path(base_dir)
                / ".well-known"
                / "apple-developer-merchantid-domain-association"
            )
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                except Exception:
                    content = ""
    return HttpResponse(content, content_type="text/plain")


def _redirect_to_dashboard(slug: str):
    try:
        return redirect(reverse("restaurant_dashboard", kwargs={"slug": slug}))
    except Exception:
        return redirect(f"/dashboard/{slug}/")


@login_required
def connect_onboarding_start(request, slug: str):
    """
    Initiate Stripe Connect Express onboarding flow for a restaurant.
    Redirects to Stripe onboarding URL.
    """
    restaurant = get_object_or_404(Restaurant, slug=slug)

    if (
        restaurant.owner_id
        and restaurant.owner_id != request.user.id
        and not request.user.is_staff
    ):
        return HttpResponseForbidden("No tienes permiso sobre este restaurante.")

    try:
        return_url = request.build_absolute_uri(
            reverse("stripe_connect_return", kwargs={"slug": slug})
        )
    except Exception:
        return_url = request.build_absolute_uri(f"/billing/connect/return/{slug}/")

    try:
        refresh_url = request.build_absolute_uri(
            reverse("stripe_connect_onboarding", kwargs={"slug": slug})
        )
    except Exception:
        refresh_url = request.build_absolute_uri(f"/billing/connect/start/{slug}/")

    try:
        if restaurant.stripe_onboarding_completed and restaurant.stripe_account_id:
            try:
                dashboard_url = create_account_login_link(restaurant)
                return redirect(dashboard_url)
            except StripeGatewayError:
                logger.info(
                    "Login link creation failed for onboarded restaurant %s; falling back to onboarding link.",
                    restaurant.slug,
                )

        onboarding_url = create_account_onboarding_link(
            restaurant=restaurant,
            return_url=return_url,
            refresh_url=refresh_url,
        )
        return redirect(onboarding_url)
    except StripeGatewayError as exc:
        messages.error(request, str(exc))
        return _redirect_to_dashboard(slug)


@login_required
def connect_onboarding_return(request, slug: str):
    """
    Handle return redirect from Stripe Connect Express onboarding.
    Retrieves account from Stripe, verifies status, and updates restaurant.
    """
    restaurant = get_object_or_404(Restaurant, slug=slug)

    if (
        restaurant.owner_id
        and restaurant.owner_id != request.user.id
        and not request.user.is_staff
    ):
        return HttpResponseForbidden("No tienes permiso sobre este restaurante.")

    secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    if not secret_key:
        messages.error(request, "STRIPE_SECRET_KEY no está configurada.")
        return _redirect_to_dashboard(slug)

    if not restaurant.stripe_account_id:
        messages.error(
            request, "No se encontró una cuenta de Stripe para este restaurante."
        )
        return _redirect_to_dashboard(slug)

    stripe.api_key = secret_key
    try:
        acct = stripe.Account.retrieve(restaurant.stripe_account_id)
        is_completed = bool(
            acct.get("charges_enabled") and acct.get("details_submitted")
        )
        restaurant.stripe_onboarding_completed = is_completed
        restaurant.save(update_fields=["stripe_onboarding_completed", "updated_at"])

        if is_completed:
            messages.success(
                request, "Cuenta de Stripe Connect configurada exitosamente."
            )
        else:
            messages.warning(
                request,
                "Stripe requiere información adicional para habilitar pagos en tu cuenta.",
            )
    except stripe.StripeError as exc:
        logger.warning(
            "Could not retrieve Stripe account %s: %s",
            restaurant.stripe_account_id,
            exc,
        )
        messages.error(request, f"Error al verificar la cuenta de Stripe: {exc}")

    return _redirect_to_dashboard(slug)


def _stripe_object_to_dict(obj: object) -> dict:
    if isinstance(obj, dict):
        return obj
    to_dict_recursive = getattr(obj, "to_dict_recursive", None)
    if callable(to_dict_recursive):
        return to_dict_recursive()
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if hasattr(obj, "__dict__"):
        return dict(obj)
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
