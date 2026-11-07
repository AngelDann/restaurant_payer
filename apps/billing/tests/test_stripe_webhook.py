from unittest.mock import patch

import pytest
import stripe
from django.test import override_settings
from django.urls import reverse

from apps.billing.models import StripeWebhookEvent
from apps.billing.stripe_handlers import STRIPE_WEBHOOK_HANDLERS, dispatch_stripe_event


def _sample_event_dict(*, event_id: str = "evt_test_webhook_1", event_type: str = "checkout.session.completed"):
    return {
        "id": event_id,
        "object": "event",
        "api_version": "2024-06-20",
        "type": event_type,
        "data": {
            "object": {
                "id": "cs_test_1",
                "object": "checkout.session",
                "metadata": {"tenant_id": "42"},
            }
        },
    }


@pytest.mark.django_db
def test_stripe_webhook_get_returns_405(client):
    url = reverse("stripe_webhook")
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_test")
def test_stripe_webhook_missing_signature_returns_400(client):
    url = reverse("stripe_webhook")
    response = client.post(url, data=b"{}", content_type="application/json")
    assert response.status_code == 400
    assert b"Stripe-Signature" in response.content


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="", STRIPE_WEBHOOK_SECRET="whsec_test")
def test_stripe_webhook_missing_secret_key_returns_400(client):
    url = reverse("stripe_webhook")
    response = client.post(
        url,
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="v0,foo",
    )
    assert response.status_code == 400
    assert b"STRIPE_SECRET_KEY" in response.content


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_test")
def test_stripe_webhook_invalid_signature_returns_400(client, monkeypatch):
    def boom(_payload, _sig, _secret):
        raise stripe.SignatureVerificationError("bad", "sig", "body")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(boom))
    url = reverse("stripe_webhook")
    response = client.post(
        url,
        data=b'{"id":"evt_1"}',
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=0,v1=deadbeef",
    )
    assert response.status_code == 400
    assert b"signature" in response.content.lower()


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_test")
def test_stripe_webhook_idempotent_second_post_skips_dispatch(client, monkeypatch):
    event_dict = _sample_event_dict()
    built = stripe.Event.construct_from(event_dict, stripe.api_key or "sk_test_x")

    monkeypatch.setattr(stripe.Webhook, "construct_event", staticmethod(lambda *a, **k: built))

    url = reverse("stripe_webhook")
    with patch("apps.billing.views.dispatch_stripe_event") as dispatch:
        r1 = client.post(
            url,
            data=b'{"unused":true}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=fake",
        )
        r2 = client.post(
            url,
            data=b'{"unused":true}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=fake",
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json() == {"ok": True}
    assert r2.json() == {"ok": True}
    assert dispatch.call_count == 1
    assert StripeWebhookEvent.objects.filter(event_id=event_dict["id"]).count() == 1


def test_dispatch_maps_known_types():
    seen: list[tuple[str, dict]] = []

    def capture(obj: dict) -> None:
        seen.append(("checkout.session.completed", obj))

    with patch.dict(STRIPE_WEBHOOK_HANDLERS, {"checkout.session.completed": capture}, clear=False):
        dispatch_stripe_event("checkout.session.completed", {"id": "cs_1"})

    assert seen == [("checkout.session.completed", {"id": "cs_1"})]


def test_dispatch_ignores_unknown_type():
    dispatch_stripe_event("customer.created", {"id": "cus_1"})  # no crash
