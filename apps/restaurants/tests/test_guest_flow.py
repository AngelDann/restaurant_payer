from __future__ import annotations

import sys
import types
from decimal import Decimal
from unittest import mock
import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

# Ensure compatibility stub for seed_demo_restaurant in case another subagent is mid-migration
if "apps.restaurants.management.commands.seed_demo_restaurant" not in sys.modules:
    dummy_cmd = types.ModuleType("apps.restaurants.management.commands.seed_demo_restaurant")
    dummy_cmd.ensure_demo_restaurant = lambda *a, **k: None
    dummy_cmd.reset_table_order_demo = lambda *a, **k: None
    dummy_cmd.seed_demo_data = lambda *a, **k: None
    sys.modules["apps.restaurants.management.commands.seed_demo_restaurant"] = dummy_cmd

from apps.restaurants.models import (
    DishRating,
    MenuCategory,
    MenuItem,
    OrderItem,
    OrderPayment,
    OrderReview,
    Restaurant,
    Table,
    TableOrder,
)
from apps.billing.services import StripeGatewayError


@pytest.fixture
def restaurant(db):
    return Restaurant.objects.create(
        name="La Taquería Auténtica",
        slug="la-taqueria-autentica",
        tagline="Tacos gourmet & mezcales",
        currency="MXN",
        google_maps_review_url="https://maps.google.com/?cid=123456789",
        stripe_account_id="acct_test_123456",
        stripe_onboarding_completed=True,
        is_active=True,
    )


@pytest.fixture
def table(restaurant):
    return Table.objects.create(
        restaurant=restaurant,
        number="26",
        label="Terraza 26",
        is_active=True,
    )


@pytest.fixture
def menu_category(restaurant):
    return MenuCategory.objects.create(
        restaurant=restaurant,
        name="Especialidades",
        display_order=1,
    )


@pytest.fixture
def menu_items(restaurant, menu_category):
    item1 = MenuItem.objects.create(
        restaurant=restaurant,
        category=menu_category,
        name="Papas fritas con salsa de queso",
        weight_or_volume="250g",
        price=Decimal("145.00"),
        is_available=True,
    )
    item2 = MenuItem.objects.create(
        restaurant=restaurant,
        category=menu_category,
        name="Vino de verano",
        weight_or_volume="300ml",
        price=Decimal("155.00"),
        is_available=True,
    )
    return [item1, item2]


@pytest.fixture
def active_order(restaurant, table, menu_items):
    order = TableOrder.objects.create(
        restaurant=restaurant,
        table=table,
        status=TableOrder.Status.OPEN,
        guests_count=2,
    )
    order.add_item(menu_items[0], quantity=1)  # 145.00
    order.add_item(menu_items[1], quantity=2)  # 310.00 -> total 455.00
    return order


@pytest.mark.django_db
class TestGuestFlow:
    def test_guest_table_hub(self, client, restaurant, table, active_order):
        url = reverse("guest_table_hub", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "La Taquería Auténtica" in content
        assert "Mesa N°26" in content
        assert "Ver el menú" in content
        assert "Pagar la cuenta" in content
        assert "Dejar reseña" in content

    def test_guest_table_hub_404_for_invalid_table(self, client, restaurant):
        url = reverse("guest_table_hub", kwargs={"slug": restaurant.slug, "table_number": "999"})
        response = client.get(url)
        assert response.status_code == 404

    def test_guest_table_menu(self, client, restaurant, table, menu_items):
        url = reverse("guest_table_menu", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Papas fritas con salsa de queso" in content
        assert "145.00" in content
        assert "250g" in content

    def test_guest_add_item_creates_and_updates_order(self, client, restaurant, table, menu_items):
        item = menu_items[0]
        url = reverse("guest_add_item", kwargs={"slug": restaurant.slug, "table_number": table.number, "item_id": item.id})

        response = client.post(url, {"quantity": 2})
        assert response.status_code == 302

        order = table.get_active_order()
        assert order is not None
        assert order.items.count() == 1
        assert order.subtotal == Decimal("290.00")

        # Test HTMX request
        response_htmx = client.post(url, {"quantity": 1}, HTTP_HX_REQUEST="true")
        assert response_htmx.status_code == 204
        assert "HX-Redirect" in response_htmx.headers

        order.refresh_from_db()
        order_item = order.items.first()
        assert order_item.quantity == 3
        assert order.subtotal == Decimal("435.00")

    def test_guest_table_bill_view(self, client, restaurant, table, active_order):
        url = reverse("guest_table_bill", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Total de la cuenta" in content or "455.00" in content
        assert "Pagar con Apple Pay" in content
        assert "Pagar con Google Pay" in content
        assert "Pagar con tarjeta" in content
        assert "demo_seed" not in content
        assert "demo_instant" not in content

    def test_guest_table_bill_empty_state_has_no_demo_button(self, client, restaurant, table):
        url = reverse("guest_table_bill", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "No hay cuenta abierta" in content
        assert "demo_seed" not in content
        assert "Cargar orden demo" not in content
        assert "Ver menú para ordenar" in content

    def test_guest_table_bill_shows_disabled_notice_when_stripe_not_ready(self, client, restaurant, table, active_order):
        restaurant.stripe_onboarding_completed = False
        restaurant.stripe_account_id = ""
        restaurant.save()

        url = reverse("guest_table_bill", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "El pago en línea no está disponible en este momento" in content

    def test_bill_calculate_partial_full_and_percentages(self, client, restaurant, table, active_order):
        url = reverse("guest_bill_calculate", kwargs={"slug": restaurant.slug, "table_number": table.number})

        # Test 10% tip on full bill (455.00 -> tip 45.50 -> total 500.50)
        res_10 = client.post(url, {"split_mode": "full", "tip_percent": "10"})
        assert res_10.status_code == 200
        content_10 = res_10.content.decode("utf-8")
        assert "45.50" in content_10
        assert "500.50" in content_10

        # Test 15% tip (455.00 -> tip 68.25 -> total 523.25)
        res_15 = client.post(url, {"split_mode": "full", "tip_percent": "15"})
        assert res_15.status_code == 200
        content_15 = res_15.content.decode("utf-8")
        assert "68.25" in content_15
        assert "523.25" in content_15

        # Test 0% tip
        res_0 = client.post(url, {"split_mode": "full", "tip_percent": "0"})
        assert res_0.status_code == 200
        assert "0.00" in res_0.content.decode("utf-8")

    def test_bill_calculate_partial_equal_split(self, client, restaurant, table, active_order):
        url = reverse("guest_bill_calculate", kwargs={"slug": restaurant.slug, "table_number": table.number})
        response = client.post(url, {"split_mode": "equal", "split_count": "2", "tip_percent": "10"})
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "227.50" in content
        assert "250.25" in content

    def test_bill_calculate_partial_items_split(self, client, restaurant, table, active_order):
        url = reverse("guest_bill_calculate", kwargs={"slug": restaurant.slug, "table_number": table.number})
        item1 = active_order.items.first()
        response = client.post(url, {
            "split_mode": "items",
            "selected_items": [str(item1.id)],
            "tip_percent": "10",
        })
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "145.00" in content
        assert "14.50" in content
        assert "159.50" in content

    def test_bill_checkout_creates_payment_intent_when_stripe_configured(self, client, restaurant, table, active_order):
        url = reverse("guest_bill_checkout", kwargs={"slug": restaurant.slug, "table_number": table.number})
        post_data = {
            "split_mode": "full",
            "split_count": "1",
            "tip_percentage": "10",
            "payment_method": "apple_pay",
        }

        mock_intent_response = {
            "id": "pi_test_12345",
            "client_secret": "pi_test_12345_secret_abcde",
        }

        with mock.patch("apps.restaurants.views_guest.create_order_payment_intent", return_value=mock_intent_response) as mock_create:
            response = client.post(
                url,
                post_data,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_ACCEPT="application/json",
            )
            assert response.status_code == 200
            json_data = response.json()
            assert json_data["client_secret"] == "pi_test_12345_secret_abcde"
            assert "payment_id" in json_data
            assert "return_url" in json_data
            mock_create.assert_called_once()

            payment = OrderPayment.objects.get(id=json_data["payment_id"])
            assert payment.status == OrderPayment.Status.PENDING
            assert payment.payment_method_label == "apple_pay"
            assert payment.subtotal_amount == Decimal("455.00")
            assert payment.tip_amount == Decimal("45.50")
            assert payment.total_amount == Decimal("500.50")

    def test_bill_checkout_returns_400_when_restaurant_not_onboarded(self, client, restaurant, table, active_order):
        restaurant.stripe_onboarding_completed = False
        restaurant.save()

        url = reverse("guest_bill_checkout", kwargs={"slug": restaurant.slug, "table_number": table.number})
        post_data = {
            "split_mode": "full",
            "split_count": "1",
            "tip_percentage": "10",
            "payment_method": "card",
        }

        # AJAX request returns 400 JSON
        response = client.post(
            url,
            post_data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )
        assert response.status_code == 400
        json_data = response.json()
        assert "error" in json_data
        assert "Stripe Connect" in json_data["error"]

        # Standard POST redirects with message
        response_post = client.post(url, post_data)
        assert response_post.status_code == 302
        expected_bill_url = reverse("guest_table_bill", kwargs={"slug": restaurant.slug, "table_number": table.number})
        assert response_post.url == expected_bill_url

    def test_bill_checkout_handles_gateway_error(self, client, restaurant, table, active_order):
        url = reverse("guest_bill_checkout", kwargs={"slug": restaurant.slug, "table_number": table.number})
        post_data = {
            "split_mode": "full",
            "split_count": "1",
            "tip_percentage": "10",
            "payment_method": "card",
        }

        with mock.patch("apps.restaurants.views_guest.create_order_payment_intent", side_effect=StripeGatewayError("Network timeout")):
            response = client.post(
                url,
                post_data,
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                HTTP_ACCEPT="application/json",
            )
            assert response.status_code == 400
            json_data = response.json()
            assert "Network timeout" in json_data["error"]

            failed_payment = OrderPayment.objects.filter(order=active_order).last()
            assert failed_payment is not None
            assert failed_payment.status == OrderPayment.Status.FAILED

    def test_payment_complete_success_redirects_to_review(self, client, restaurant, table, active_order):
        payment = OrderPayment.objects.create(
            order=active_order,
            subtotal_amount=Decimal("455.00"),
            total_amount=Decimal("500.50"),
            stripe_payment_intent_id="pi_test_success_123",
            status=OrderPayment.Status.PENDING,
        )
        url = reverse("guest_payment_complete", kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id})

        with mock.patch("apps.restaurants.views_guest.verify_and_complete_payment_intent", return_value=True) as mock_verify:
            response = client.get(url)
            assert response.status_code == 302
            expected_redirect = reverse(
                "guest_review_dishes",
                kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id},
            )
            assert response.url == expected_redirect
            mock_verify.assert_called_once()

    def test_payment_complete_unconfirmed_redirects_to_bill(self, client, restaurant, table, active_order):
        payment = OrderPayment.objects.create(
            order=active_order,
            subtotal_amount=Decimal("455.00"),
            total_amount=Decimal("500.50"),
            stripe_payment_intent_id="pi_test_pending_123",
            status=OrderPayment.Status.PENDING,
        )
        url = reverse("guest_payment_complete", kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id})

        with mock.patch("apps.restaurants.views_guest.verify_and_complete_payment_intent", return_value=False):
            response = client.get(url)
            assert response.status_code == 302
            expected_bill = reverse("guest_table_bill", kwargs={"slug": restaurant.slug, "table_number": table.number})
            assert response.url == expected_bill

            messages = list(get_messages(response.wsgi_request))
            assert any("El pago aún no ha sido confirmado" in str(m) for m in messages)

    def test_payment_complete_already_succeeded_proceeds_directly(self, client, restaurant, table, active_order):
        payment = OrderPayment.objects.create(
            order=active_order,
            subtotal_amount=Decimal("455.00"),
            total_amount=Decimal("500.50"),
            stripe_payment_intent_id="pi_test_webhook_done",
            status=OrderPayment.Status.SUCCEEDED,
        )
        url = reverse("guest_payment_complete", kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id})

        with mock.patch("apps.restaurants.views_guest.verify_and_complete_payment_intent") as mock_verify:
            response = client.get(url)
            assert response.status_code == 302
            expected_redirect = reverse(
                "guest_review_dishes",
                kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id},
            )
            assert response.url == expected_redirect
            mock_verify.assert_not_called()

    def test_review_dishes_get_and_post(self, client, restaurant, table, active_order, menu_items):
        payment = OrderPayment.objects.create(
            order=active_order,
            subtotal_amount=Decimal("455.00"),
            total_amount=Decimal("500.50"),
            status=OrderPayment.Status.SUCCEEDED,
        )
        url = reverse("guest_review_dishes", kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id})

        # GET Screen 1
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Califica los platillos de tu orden" in content
        assert "Papas fritas con salsa de queso" in content
        assert "Ver mi recibo" in content

        # POST ratings
        item1, item2 = menu_items[0], menu_items[1]
        post_data = {
            f"dish_{item1.id}": "like",
            f"dish_{item2.id}": "dislike",
        }
        post_res = client.post(url, post_data)
        assert post_res.status_code == 302

        review = OrderReview.objects.filter(payment=payment).first()
        assert review is not None

        ratings = {r.menu_item_id: r.liked for r in review.dish_ratings.all()}
        assert ratings[item1.id] is True
        assert ratings[item2.id] is False

    def test_review_receipt_get_and_post_triggers_google(self, client, restaurant, table, active_order):
        payment = OrderPayment.objects.create(
            order=active_order,
            subtotal_amount=Decimal("455.00"),
            tip_amount=Decimal("45.50"),
            total_amount=Decimal("500.50"),
            status=OrderPayment.Status.SUCCEEDED,
            payment_method_label="apple_pay",
        )
        url = reverse("guest_review_receipt", kwargs={"slug": restaurant.slug, "table_number": table.number, "payment_id": payment.id})

        # GET Screen 2
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Pago confirmado" in content
        assert "500.50" in content
        assert "¿Te gustó La Taquería Auténtica?" in content
        assert "¿Te gustaría dejarnos una reseña en Google Maps?" in content

        # POST 5 stars via AJAX
        post_res = client.post(
            url,
            {"overall_rating": "5", "comment": "¡Excelente servicio y comida!", "redirected_to_google": "true"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert post_res.status_code == 200
        json_data = post_res.json()
        assert json_data["success"] is True
        assert json_data["prompt_google"] is True
        assert json_data["google_maps_url"] == restaurant.google_maps_review_url

        review = OrderReview.objects.get(payment=payment)
        assert review.overall_rating == 5
        assert review.redirected_to_google is True

    def test_standalone_feedback(self, client, restaurant, table):
        url = reverse("guest_feedback", kwargs={"slug": restaurant.slug, "table_number": table.number})

        get_res = client.get(url)
        assert get_res.status_code == 200
        assert "Califica tu experiencia" in get_res.content.decode("utf-8")

        post_res = client.post(url, {"overall_rating": "4", "comment": "Muy rico"})
        assert post_res.status_code == 200
        review = OrderReview.objects.filter(restaurant=restaurant).first()
        assert review is not None
        assert review.overall_rating == 4
        assert review.should_prompt_google_maps is True
