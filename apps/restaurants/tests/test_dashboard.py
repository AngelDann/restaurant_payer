from __future__ import annotations

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.restaurants.models import (
    MenuCategory,
    MenuItem,
    Restaurant,
    Table,
    TableOrder,
)

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user(username="owner1", password="secure_password_123")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username="owner2", password="secure_password_456")


@pytest.fixture
def staff_user(db):
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="admin_password_123"
    )


@pytest.fixture
def restaurant(db, owner):
    return Restaurant.objects.create(
        owner=owner,
        name="La Taquería Central",
        slug="taqueria-central",
        tagline="Tacos y Mezcal artesanal",
        address="Álvaro Obregón 123, Roma Norte",
        currency="MXN",
    )


@pytest.fixture
def table(db, restaurant):
    return Table.objects.create(
        restaurant=restaurant,
        number="5",
        label="Terraza 1",
    )


@pytest.fixture
def menu_category(db, restaurant):
    return MenuCategory.objects.create(
        restaurant=restaurant,
        name="Tacos al Carbón",
        display_order=1,
    )


@pytest.fixture
def menu_item(db, restaurant, menu_category):
    return MenuItem.objects.create(
        restaurant=restaurant,
        category=menu_category,
        name="Taco de Ribeye",
        description="Con costra de queso y guacamole",
        price=Decimal("120.00"),
        weight_or_volume="150 g",
        is_available=True,
    )


# ==============================================================================
# Authentication Tests
# ==============================================================================


@pytest.mark.django_db
def test_dashboard_login_page_renders(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    assert "Iniciar sesión" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_dashboard_login_successful(client, owner):
    response = client.post(
        reverse("login"),
        {"username": "owner1", "password": "secure_password_123"},
    )
    assert response.status_code == 302
    assert response.url == reverse("dashboard_home")


@pytest.mark.django_db
def test_dashboard_register_page_renders(client):
    response = client.get(reverse("register"))
    assert response.status_code == 200
    assert "Registra tu restaurante" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_dashboard_register_successful(client):
    response = client.post(
        reverse("register"),
        {
            "username": "new_chef",
            "password1": "ComplexPass123!",
            "password2": "ComplexPass123!",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("dashboard_home")
    assert User.objects.filter(username="new_chef").exists()


@pytest.mark.django_db
def test_dashboard_logout(client, owner):
    client.force_login(owner)
    response = client.get(reverse("logout"))
    assert response.status_code == 302
    assert response.url == reverse("home")


# ==============================================================================
# Dashboard Home & Restaurant Ownership
# ==============================================================================


@pytest.mark.django_db
def test_dashboard_home_requires_login(client):
    response = client.get(reverse("dashboard_home"))
    assert response.status_code == 302
    assert reverse("login") in response.url


@pytest.mark.django_db
def test_dashboard_home_authenticated(client, owner, restaurant):
    client.force_login(owner)
    response = client.get(reverse("dashboard_home"))
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "La Taquería Central" in content
    assert "Registrar nuevo restaurante" in content


@pytest.mark.django_db
def test_dashboard_home_create_restaurant(client, owner):
    client.force_login(owner)
    response = client.post(
        reverse("dashboard_home"),
        {
            "name": "Bistró del Parque",
            "slug": "",
            "tagline": "Cocina francesa",
            "address": "Parque México 45",
        },
    )
    assert response.status_code == 302
    new_rest = Restaurant.objects.get(name="Bistró del Parque")
    assert new_rest.owner == owner
    assert new_rest.slug == "bistro-del-parque"
    assert response.url == reverse("restaurant_dashboard", kwargs={"slug": new_rest.slug})


# ==============================================================================
# Restaurant Dashboard & Ownership Isolation
# ==============================================================================


@pytest.mark.django_db
def test_restaurant_dashboard_view(client, owner, restaurant, table):
    client.force_login(owner)
    response = client.get(reverse("restaurant_dashboard", kwargs={"slug": restaurant.slug}))
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert restaurant.name in content
    assert "Mesa N°5" in content
    assert "Stripe Connect" in content


@pytest.mark.django_db
def test_restaurant_dashboard_ownership_isolation(client, other_user, restaurant):
    client.force_login(other_user)
    # other_user has no permissions on restaurant owned by owner
    response = client.get(reverse("restaurant_dashboard", kwargs={"slug": restaurant.slug}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_can_access_any_restaurant(client, staff_user, restaurant):
    client.force_login(staff_user)
    response = client.get(reverse("restaurant_dashboard", kwargs={"slug": restaurant.slug}))
    assert response.status_code == 200
    assert restaurant.name in response.content.decode("utf-8")


@pytest.mark.django_db
def test_restaurant_settings_update(client, owner, restaurant):
    client.force_login(owner)
    url = reverse("restaurant_settings", kwargs={"slug": restaurant.slug})
    response = client.post(
        url,
        {
            "name": "La Gran Taquería Central",
            "slug": restaurant.slug,
            "tagline": "Tacos gourmet y mezcales",
            "address": restaurant.address,
        },
    )
    assert response.status_code == 302
    restaurant.refresh_from_db()
    assert restaurant.name == "La Gran Taquería Central"
    assert restaurant.tagline == "Tacos gourmet y mezcales"


# ==============================================================================
# Table CRUD Operations
# ==============================================================================


@pytest.mark.django_db
def test_table_create(client, owner, restaurant):
    client.force_login(owner)
    url = reverse("restaurant_table_add", kwargs={"slug": restaurant.slug})
    response = client.post(url, {"number": "12", "label": "Barra"})
    assert response.status_code == 302
    assert Table.objects.filter(restaurant=restaurant, number="12").exists()


@pytest.mark.django_db
def test_table_delete(client, owner, restaurant, table):
    client.force_login(owner)
    url = reverse(
        "restaurant_table_delete",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )
    response = client.post(url)
    assert response.status_code == 302
    assert not Table.objects.filter(restaurant=restaurant, number=table.number).exists()


# ==============================================================================
# Menu CRUD Operations
# ==============================================================================


@pytest.mark.django_db
def test_menu_manage_view(client, owner, restaurant, menu_category, menu_item):
    client.force_login(owner)
    url = reverse("restaurant_menu_manage", kwargs={"slug": restaurant.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert menu_category.name in content
    assert menu_item.name in content


@pytest.mark.django_db
def test_category_create(client, owner, restaurant):
    client.force_login(owner)
    url = reverse("restaurant_category_add", kwargs={"slug": restaurant.slug})
    response = client.post(url, {"name": "Postres Caseros", "display_order": 5})
    assert response.status_code == 302
    assert MenuCategory.objects.filter(restaurant=restaurant, name="Postres Caseros").exists()


@pytest.mark.django_db
def test_menu_item_create(client, owner, restaurant, menu_category):
    client.force_login(owner)
    url = reverse("restaurant_menu_item_add", kwargs={"slug": restaurant.slug})
    response = client.post(
        url,
        {
            "category": menu_category.id,
            "name": "Guacamole con Totopos",
            "price": "95.00",
            "weight_or_volume": "200 g",
            "is_available": "on",
            "display_order": 2,
        },
    )
    assert response.status_code == 302
    assert MenuItem.objects.filter(restaurant=restaurant, name="Guacamole con Totopos").exists()


@pytest.mark.django_db
def test_menu_item_toggle(client, owner, restaurant, menu_item):
    client.force_login(owner)
    url = reverse(
        "restaurant_menu_item_toggle",
        kwargs={"slug": restaurant.slug, "item_id": menu_item.id},
    )
    assert menu_item.is_available is True
    response = client.post(url)
    assert response.status_code == 302
    menu_item.refresh_from_db()
    assert menu_item.is_available is False


# ==============================================================================
# POS & Order Operations
# ==============================================================================


@pytest.mark.django_db
def test_table_pos_view(client, owner, restaurant, table, menu_item):
    client.force_login(owner)
    url = reverse(
        "restaurant_table_pos",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert f"Mesa N°{table.number}" in content
    assert menu_item.name in content


@pytest.mark.django_db
def test_pos_open_order(client, owner, restaurant, table):
    client.force_login(owner)
    url = reverse(
        "pos_open_order",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )
    response = client.post(
        url,
        {"waiter_name": "Valeria R.", "guests_count": 4},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    order = table.get_active_order()
    assert order is not None
    assert order.waiter_name == "Valeria R."
    assert order.guests_count == 4
    assert order.status == TableOrder.Status.OPEN


@pytest.mark.django_db
def test_pos_add_item_standard_and_htmx(client, owner, restaurant, table, menu_item):
    client.force_login(owner)
    url = reverse(
        "pos_add_item",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )

    # 1. Standard POST creates order if none exists and adds item
    response = client.post(url, {"menu_item_id": menu_item.id, "quantity": 2})
    assert response.status_code == 302
    order = table.get_active_order()
    assert order is not None
    assert order.subtotal == Decimal("240.00")

    # 2. HTMX POST returns partial panel
    response = client.post(
        url,
        {"menu_item_id": menu_item.id, "quantity": 1},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    assert 'id="order-panel"' in response.content.decode("utf-8")
    order.refresh_from_db()
    assert order.subtotal == Decimal("360.00")


@pytest.mark.django_db
def test_pos_update_item(client, owner, restaurant, table, menu_item):
    client.force_login(owner)
    order = TableOrder.objects.create(
        restaurant=restaurant,
        table=table,
        status=TableOrder.Status.OPEN,
    )
    order_item = order.add_item(menu_item, quantity=1)

    url = reverse(
        "pos_update_item",
        kwargs={
            "slug": restaurant.slug,
            "table_number": table.number,
            "item_id": order_item.id,
        },
    )

    # Increment
    response = client.post(url, {"action": "increment"}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    order_item.refresh_from_db()
    assert order_item.quantity == 2

    # Decrement
    client.post(url, {"action": "decrement"}, HTTP_HX_REQUEST="true")
    order_item.refresh_from_db()
    assert order_item.quantity == 1

    # Remove
    client.post(url, {"action": "remove"}, HTTP_HX_REQUEST="true")
    assert not order.items.filter(id=order_item.id).exists()


@pytest.mark.django_db
def test_pos_close_order(client, owner, restaurant, table, menu_item):
    client.force_login(owner)
    order = TableOrder.objects.create(
        restaurant=restaurant,
        table=table,
        status=TableOrder.Status.OPEN,
    )
    order.add_item(menu_item, quantity=1)

    url = reverse(
        "pos_close_order",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )
    response = client.post(url, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == TableOrder.Status.CANCELLED
    assert table.get_active_order() is None


@pytest.mark.django_db
def test_table_qr_print_view(client, owner, restaurant, table):
    client.force_login(owner)
    url = reverse(
        "restaurant_table_qr",
        kwargs={"slug": restaurant.slug, "table_number": table.number},
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert f"Mesa N°{table.number}" in content
    assert restaurant.name in content
    assert f"/r/{restaurant.slug}/t/{table.number}/" in content
