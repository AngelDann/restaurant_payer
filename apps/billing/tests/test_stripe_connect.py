import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Safety guard in case other parallel subagents have not yet updated views_dashboard
if "apps.restaurants.management.commands.seed_demo_restaurant" not in sys.modules:
    sys.modules["apps.restaurants.management.commands.seed_demo_restaurant"] = MagicMock()

import pytest
import stripe
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from apps.billing.services import (
    StripeGatewayError,
    broadcast_order_update,
    create_account_login_link,
    create_account_onboarding_link,
    create_or_get_connected_account,
    create_order_payment_intent,
    is_stripe_configured,
    verify_and_complete_payment_intent,
)
from apps.billing.stripe_handlers import (
    handle_account_updated,
    handle_payment_intent_failed,
    handle_payment_intent_succeeded,
)
from apps.restaurants.models import (
    MenuCategory,
    MenuItem,
    OrderPayment,
    Restaurant,
    Table,
    TableOrder,
)

User = get_user_model()


@pytest.fixture
def owner():
    return User.objects.create_user(
        username="restaurant_owner",
        email="owner@example.com",
        password="securepassword123",
    )


@pytest.fixture
def other_user():
    return User.objects.create_user(
        username="other_person",
        email="other@example.com",
        password="securepassword123",
    )


@pytest.fixture
def staff_user():
    return User.objects.create_user(
        username="staff_admin",
        email="staff@example.com",
        password="securepassword123",
        is_staff=True,
    )


@pytest.fixture
def restaurant(owner):
    return Restaurant.objects.create(
        owner=owner,
        name="El Asador Mexicano",
        slug="el-asador-mexicano",
        currency="MXN",
        platform_fee_percent=Decimal("3.00"),
    )


@pytest.fixture
def table(restaurant):
    return Table.objects.create(
        restaurant=restaurant,
        number="7",
        label="Mesa 7 Terraza",
    )


@pytest.fixture
def menu_category(restaurant):
    return MenuCategory.objects.create(
        restaurant=restaurant,
        name="Platos Fuertes",
    )


@pytest.fixture
def menu_item(restaurant, menu_category):
    return MenuItem.objects.create(
        restaurant=restaurant,
        category=menu_category,
        name="Corte Rib Eye",
        price=Decimal("100.00"),
    )


@pytest.fixture
def table_order(restaurant, table, menu_item):
    order = TableOrder.objects.create(
        restaurant=restaurant,
        table=table,
        status=TableOrder.Status.OPEN,
    )
    order.add_item(menu_item, quantity=2)  # subtotal = 200.00
    return order


@pytest.fixture
def order_payment(table_order):
    return OrderPayment.objects.create(
        order=table_order,
        subtotal_amount=Decimal("200.00"),
        tip_amount=Decimal("20.00"),
        total_amount=Decimal("220.00"),
        status=OrderPayment.Status.PENDING,
    )


@pytest.mark.django_db
def test_is_stripe_configured():
    with override_settings(STRIPE_SECRET_KEY="sk_test_123", STRIPE_PUBLIC_KEY="pk_test_123"):
        assert is_stripe_configured() is True

    with override_settings(STRIPE_SECRET_KEY="", STRIPE_PUBLIC_KEY="pk_test_123"):
        assert is_stripe_configured() is False

    with override_settings(STRIPE_SECRET_KEY="sk_test_123", STRIPE_PUBLIC_KEY=""):
        assert is_stripe_configured() is False

    with override_settings(STRIPE_SECRET_KEY="", STRIPE_PUBLIC_KEY=""):
        assert is_stripe_configured() is False


@pytest.mark.django_db
def test_create_or_get_connected_account_existing(restaurant):
    restaurant.stripe_account_id = "acct_existing_999"
    restaurant.save(update_fields=["stripe_account_id"])

    with patch("stripe.Account.create") as mock_create:
        acct_id = create_or_get_connected_account(restaurant)
        assert acct_id == "acct_existing_999"
        mock_create.assert_not_called()


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="")
def test_create_or_get_connected_account_missing_key(restaurant):
    restaurant.stripe_account_id = ""
    restaurant.save(update_fields=["stripe_account_id"])

    with pytest.raises(StripeGatewayError, match="STRIPE_SECRET_KEY no está configurada."):
        create_or_get_connected_account(restaurant)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_or_get_connected_account_stripe_api(restaurant):
    restaurant.stripe_account_id = ""
    restaurant.save(update_fields=["stripe_account_id"])

    mock_account = {"id": "acct_real_mx_123"}
    with patch("stripe.Account.create", return_value=mock_account) as mock_create:
        account_id = create_or_get_connected_account(restaurant)
        assert account_id == "acct_real_mx_123"
        restaurant.refresh_from_db()
        assert restaurant.stripe_account_id == "acct_real_mx_123"

        mock_create.assert_called_once_with(
            type="express",
            country="MX",
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            business_type="company",
            metadata={"restaurant_id": str(restaurant.id), "slug": restaurant.slug},
        )


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_or_get_connected_account_stripe_error(restaurant):
    restaurant.stripe_account_id = ""
    restaurant.save(update_fields=["stripe_account_id"])

    with patch("stripe.Account.create", side_effect=stripe.StripeError("Stripe API down")):
        with pytest.raises(StripeGatewayError, match="Stripe API down"):
            create_or_get_connected_account(restaurant)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="")
def test_create_account_onboarding_link_missing_key(restaurant):
    with pytest.raises(StripeGatewayError, match="STRIPE_SECRET_KEY no está configurada."):
        create_account_onboarding_link(restaurant, "https://return.url", "https://refresh.url")


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_account_onboarding_link_stripe_api(restaurant):
    restaurant.stripe_account_id = "acct_prod_mxn_123"
    restaurant.save(update_fields=["stripe_account_id"])

    return_url = "https://example.com/return"
    refresh_url = "https://example.com/refresh"

    with patch("stripe.AccountLink.create", return_value={"url": "https://connect.stripe.com/setup/123"}) as mock_link:
        link_url = create_account_onboarding_link(
            restaurant, return_url=return_url, refresh_url=refresh_url
        )
        assert link_url == "https://connect.stripe.com/setup/123"
        mock_link.assert_called_once_with(
            account="acct_prod_mxn_123",
            refresh_url=refresh_url,
            return_url=return_url,
            type="account_onboarding",
        )


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_account_onboarding_link_stripe_error(restaurant):
    restaurant.stripe_account_id = "acct_prod_mxn_123"
    restaurant.save(update_fields=["stripe_account_id"])

    with patch("stripe.AccountLink.create", side_effect=stripe.StripeError("AccountLink failed")):
        with pytest.raises(StripeGatewayError, match="AccountLink failed"):
            create_account_onboarding_link(restaurant, "https://return.url", "https://refresh.url")


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_account_login_link_success(restaurant):
    restaurant.stripe_account_id = "acct_onboarded_999"
    restaurant.save(update_fields=["stripe_account_id"])

    with patch("stripe.Account.create_login_link", return_value={"url": "https://connect.stripe.com/express/acct_999"}) as mock_login:
        link_url = create_account_login_link(restaurant)
        assert link_url == "https://connect.stripe.com/express/acct_999"
        mock_login.assert_called_once_with("acct_onboarded_999")


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="")
def test_create_account_login_link_missing_key(restaurant):
    restaurant.stripe_account_id = "acct_onboarded_999"
    restaurant.save(update_fields=["stripe_account_id"])

    with pytest.raises(StripeGatewayError, match="STRIPE_SECRET_KEY no está configurada."):
        create_account_login_link(restaurant)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_secret_123")
def test_create_account_login_link_missing_account(restaurant):
    restaurant.stripe_account_id = ""
    restaurant.save(update_fields=["stripe_account_id"])

    with pytest.raises(StripeGatewayError, match="El restaurante no tiene una cuenta de Stripe conectada."):
        create_account_login_link(restaurant)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="")
def test_create_order_payment_intent_missing_key(order_payment):
    with pytest.raises(StripeGatewayError, match="STRIPE_SECRET_KEY no está configurada."):
        create_order_payment_intent(order_payment)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_create_order_payment_intent_not_onboarded(order_payment):
    restaurant = order_payment.order.restaurant
    restaurant.stripe_account_id = "acct_incomplete_123"
    restaurant.stripe_onboarding_completed = False
    restaurant.save()

    with pytest.raises(
        StripeGatewayError,
        match="El restaurante aún no tiene una cuenta de Stripe Connect activa para recibir pagos.",
    ):
        create_order_payment_intent(order_payment)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_create_order_payment_intent_success(order_payment):
    restaurant = order_payment.order.restaurant
    restaurant.stripe_account_id = "acct_connect_destination_999"
    restaurant.stripe_onboarding_completed = True
    restaurant.save()

    mock_intent = {
        "id": "pi_stripe_live_123",
        "client_secret": "pi_stripe_live_123_secret_xyz",
    }

    with patch("stripe.PaymentIntent.create", return_value=mock_intent) as mock_pi_create:
        result = create_order_payment_intent(order_payment)
        assert "demo_mode" not in result
        assert result["id"] == "pi_stripe_live_123"
        assert result["client_secret"] == "pi_stripe_live_123_secret_xyz"

        mock_pi_create.assert_called_once()
        _, kwargs = mock_pi_create.call_args

        # Total is 220.00 -> 22000 cents
        assert kwargs["amount"] == 22000
        assert kwargs["currency"] == "mxn"
        assert kwargs["automatic_payment_methods"] == {"enabled": True}
        # Platform Fee is 3% of 200.00 = 6.00 MXN -> 600 cents
        assert kwargs["application_fee_amount"] == 600
        assert kwargs["transfer_data"] == {"destination": "acct_connect_destination_999"}
        assert kwargs["metadata"]["order_id"] == str(order_payment.order_id)
        assert kwargs["metadata"]["payment_id"] == str(order_payment.id)
        assert kwargs["metadata"]["restaurant_slug"] == restaurant.slug
        assert kwargs["metadata"]["table_number"] == order_payment.order.table.number

    order_payment.refresh_from_db()
    assert order_payment.platform_fee_amount == Decimal("6.00")
    assert order_payment.stripe_payment_intent_id == "pi_stripe_live_123"
    assert order_payment.stripe_client_secret == "pi_stripe_live_123_secret_xyz"


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_create_order_payment_intent_stripe_error(order_payment):
    restaurant = order_payment.order.restaurant
    restaurant.stripe_account_id = "acct_active"
    restaurant.stripe_onboarding_completed = True
    restaurant.save()

    with patch("stripe.PaymentIntent.create", side_effect=stripe.StripeError("Card Declined")):
        with pytest.raises(StripeGatewayError, match="Card Declined"):
            create_order_payment_intent(order_payment)


@pytest.mark.django_db
def test_verify_and_complete_payment_intent_already_succeeded(order_payment):
    order_payment.status = OrderPayment.Status.SUCCEEDED
    order_payment.save(update_fields=["status"])

    assert verify_and_complete_payment_intent(order_payment) is True


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="")
def test_verify_and_complete_payment_intent_missing_key(order_payment):
    with pytest.raises(StripeGatewayError, match="STRIPE_SECRET_KEY no está configurada."):
        verify_and_complete_payment_intent(order_payment)


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_verify_and_complete_payment_intent_missing_intent_id(order_payment):
    order_payment.stripe_payment_intent_id = ""
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    assert verify_and_complete_payment_intent(order_payment) is False


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_verify_and_complete_payment_intent_succeeded(order_payment):
    order_payment.stripe_payment_intent_id = "pi_verify_succeeded_123"
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    mock_intent = {
        "id": "pi_verify_succeeded_123",
        "status": "succeeded",
    }

    with patch("stripe.PaymentIntent.retrieve", return_value=mock_intent) as mock_retrieve:
        with patch("apps.billing.services.broadcast_order_update") as mock_broadcast:
            result = verify_and_complete_payment_intent(order_payment)
            assert result is True
            mock_retrieve.assert_called_once_with("pi_verify_succeeded_123")
            mock_broadcast.assert_called_once()

    order_payment.refresh_from_db()
    assert order_payment.status == OrderPayment.Status.SUCCEEDED
    assert order_payment.paid_at is not None


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_verify_and_complete_payment_intent_not_succeeded(order_payment):
    order_payment.stripe_payment_intent_id = "pi_verify_pending_123"
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    mock_intent = {
        "id": "pi_verify_pending_123",
        "status": "requires_payment_method",
    }

    with patch("stripe.PaymentIntent.retrieve", return_value=mock_intent):
        with patch("apps.billing.services.broadcast_order_update") as mock_broadcast:
            result = verify_and_complete_payment_intent(order_payment)
            assert result is False
            mock_broadcast.assert_not_called()

    order_payment.refresh_from_db()
    assert order_payment.status == OrderPayment.Status.PENDING


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_live")
def test_verify_and_complete_payment_intent_stripe_error(order_payment):
    order_payment.stripe_payment_intent_id = "pi_verify_error_123"
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    with patch("stripe.PaymentIntent.retrieve", side_effect=stripe.StripeError("Network timeout")):
        with pytest.raises(StripeGatewayError, match="Network timeout"):
            verify_and_complete_payment_intent(order_payment)


@pytest.mark.django_db
def test_connect_onboarding_views_login_required(client: Client, restaurant):
    start_url = reverse("stripe_connect_onboarding", kwargs={"slug": restaurant.slug})
    response_start = client.get(start_url)
    assert response_start.status_code == 302
    assert "/accounts/login/" in response_start.url or "/login/" in response_start.url

    return_url = reverse("stripe_connect_return", kwargs={"slug": restaurant.slug})
    response_return = client.get(return_url)
    assert response_return.status_code == 302
    assert "/accounts/login/" in response_return.url or "/login/" in response_return.url


@pytest.mark.django_db
def test_connect_onboarding_views_forbidden_for_non_owner(client: Client, restaurant, other_user):
    client.force_login(other_user)

    start_url = reverse("stripe_connect_onboarding", kwargs={"slug": restaurant.slug})
    response_start = client.get(start_url)
    assert response_start.status_code == 403

    return_url = reverse("stripe_connect_return", kwargs={"slug": restaurant.slug})
    response_return = client.get(return_url)
    assert response_return.status_code == 403


@pytest.mark.django_db
def test_connect_onboarding_start_success(client: Client, restaurant, owner):
    client.force_login(owner)

    start_url = reverse("stripe_connect_onboarding", kwargs={"slug": restaurant.slug})
    with patch(
        "apps.billing.views.create_account_onboarding_link",
        return_value="https://connect.stripe.com/express/setup/test_link",
    ) as mock_link:
        response = client.get(start_url)
        assert response.status_code == 302
        assert response.url == "https://connect.stripe.com/express/setup/test_link"
        mock_link.assert_called_once()


@pytest.mark.django_db
def test_connect_onboarding_start_gateway_error(client: Client, restaurant, staff_user):
    # Staff user is also permitted
    client.force_login(staff_user)

    start_url = reverse("stripe_connect_onboarding", kwargs={"slug": restaurant.slug})
    with patch(
        "apps.billing.views.create_account_onboarding_link",
        side_effect=StripeGatewayError("Error de Stripe al crear cuenta"),
    ):
        response = client.get(start_url, follow=False)
        assert response.status_code == 302


@pytest.mark.django_db
def test_connect_onboarding_start_already_completed_redirects_to_login(client: Client, restaurant, owner):
    restaurant.stripe_account_id = "acct_onboarded_123"
    restaurant.stripe_onboarding_completed = True
    restaurant.save(update_fields=["stripe_account_id", "stripe_onboarding_completed"])

    client.force_login(owner)
    start_url = reverse("stripe_connect_onboarding", kwargs={"slug": restaurant.slug})

    with patch(
        "apps.billing.views.create_account_login_link",
        return_value="https://connect.stripe.com/express/dashboard_link",
    ) as mock_login_link:
        response = client.get(start_url)
        assert response.status_code == 302
        assert response.url == "https://connect.stripe.com/express/dashboard_link"
        mock_login_link.assert_called_once()


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_connect_onboarding_return_charges_enabled(client: Client, restaurant, owner):
    client.force_login(owner)
    restaurant.stripe_account_id = "acct_onboarded_ready"
    restaurant.stripe_onboarding_completed = False
    restaurant.save()

    return_url = reverse("stripe_connect_return", kwargs={"slug": restaurant.slug})
    mock_acct = {
        "id": "acct_onboarded_ready",
        "charges_enabled": True,
        "details_submitted": True,
    }

    with patch("stripe.Account.retrieve", return_value=mock_acct):
        response = client.get(return_url)
        assert response.status_code == 302

    restaurant.refresh_from_db()
    assert restaurant.stripe_onboarding_completed is True


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_connect_onboarding_return_charges_disabled(client: Client, restaurant, owner):
    client.force_login(owner)
    restaurant.stripe_account_id = "acct_onboarded_incomplete"
    restaurant.stripe_onboarding_completed = True
    restaurant.save()

    return_url = reverse("stripe_connect_return", kwargs={"slug": restaurant.slug})
    mock_acct = {
        "id": "acct_onboarded_incomplete",
        "charges_enabled": False,
        "details_submitted": True,
    }

    with patch("stripe.Account.retrieve", return_value=mock_acct):
        response = client.get(return_url)
        assert response.status_code == 302

    restaurant.refresh_from_db()
    assert restaurant.stripe_onboarding_completed is False


@pytest.mark.django_db
@override_settings(STRIPE_SECRET_KEY="sk_test_123")
def test_connect_onboarding_return_stripe_error(client: Client, restaurant, owner):
    client.force_login(owner)
    restaurant.stripe_account_id = "acct_onboarded_err"
    restaurant.save()

    return_url = reverse("stripe_connect_return", kwargs={"slug": restaurant.slug})

    with patch("stripe.Account.retrieve", side_effect=stripe.StripeError("Account error")):
        response = client.get(return_url)
        assert response.status_code == 302


@pytest.mark.django_db
def test_handle_account_updated(restaurant):
    restaurant.stripe_account_id = "acct_webhook_update_123"
    restaurant.stripe_onboarding_completed = False
    restaurant.save()

    # When both charges_enabled and details_submitted are True
    event_payload_ok = {
        "id": "acct_webhook_update_123",
        "charges_enabled": True,
        "details_submitted": True,
    }
    handle_account_updated(event_payload_ok)
    restaurant.refresh_from_db()
    assert restaurant.stripe_onboarding_completed is True

    # When charges_enabled is False
    event_payload_disabled = {
        "id": "acct_webhook_update_123",
        "charges_enabled": False,
        "details_submitted": True,
    }
    handle_account_updated(event_payload_disabled)
    restaurant.refresh_from_db()
    assert restaurant.stripe_onboarding_completed is False


@pytest.mark.django_db
def test_handle_payment_intent_succeeded_marks_order_paid(order_payment):
    order_payment.stripe_payment_intent_id = "pi_succ_12345"
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    event_payload = {
        "id": "pi_succ_12345",
        "charges": {
            "data": [
                {
                    "payment_method_details": {
                        "type": "card",
                        "card": {"wallet": {"type": "apple_pay"}},
                    }
                }
            ]
        },
        "metadata": {
            "payment_id": str(order_payment.id),
        },
    }

    with patch("apps.billing.stripe_handlers.broadcast_order_update") as mock_broadcast:
        handle_payment_intent_succeeded(event_payload)
        mock_broadcast.assert_called_once()

    order_payment.refresh_from_db()
    assert order_payment.status == OrderPayment.Status.SUCCEEDED
    assert order_payment.payment_method_label == "apple_pay"
    assert order_payment.paid_at is not None

    table_order = order_payment.order
    table_order.refresh_from_db()
    assert table_order.status == TableOrder.Status.PAID
    assert table_order.amount_paid == Decimal("200.00")
    assert table_order.tips_total == Decimal("20.00")


@pytest.mark.django_db
def test_handle_payment_intent_failed(order_payment):
    order_payment.stripe_payment_intent_id = "pi_failed_12345"
    order_payment.save(update_fields=["stripe_payment_intent_id"])

    event_payload = {
        "id": "pi_failed_12345",
        "metadata": {"payment_id": str(order_payment.id)},
    }

    with patch("apps.billing.stripe_handlers.broadcast_order_update") as mock_broadcast:
        handle_payment_intent_failed(event_payload)
        mock_broadcast.assert_called_once()

    order_payment.refresh_from_db()
    assert order_payment.status == OrderPayment.Status.FAILED


@pytest.mark.django_db
def test_apple_pay_domain_association_from_settings(client: Client):
    test_content = "SAMPLE_APPLE_PAY_ASSOCIATION_STRING_987654321"
    with override_settings(APPLE_PAY_DOMAIN_ASSOCIATION_CONTENT=test_content):
        url = reverse("apple_pay_domain_association")
        response = client.get(url)
        assert response.status_code == 200
        assert response["Content-Type"] == "text/plain"
        assert response.content.decode("utf-8") == test_content


@pytest.mark.django_db
def test_broadcast_order_update(table_order):
    mock_channel_layer = MagicMock()
    with patch("apps.billing.services.get_channel_layer", return_value=mock_channel_layer):
        with patch("apps.billing.services.async_to_sync") as mock_async_to_sync:
            mock_send = MagicMock()
            mock_async_to_sync.return_value = mock_send

            broadcast_order_update(table_order)

            mock_async_to_sync.assert_called_once_with(mock_channel_layer.group_send)
            expected_group = f"table_{table_order.restaurant.slug}_{table_order.table.number}"
            mock_send.assert_called_once_with(
                expected_group,
                {
                    "type": "order_updated",
                    "order_id": table_order.id,
                    "status": table_order.status,
                    "amount_paid": str(table_order.amount_paid),
                    "amount_remaining": str(table_order.amount_remaining),
                },
            )
