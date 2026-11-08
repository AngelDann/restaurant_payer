from __future__ import annotations

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db.models import Avg, Count, Prefetch, Q, Sum
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.restaurants.forms import (
    MenuCategoryForm,
    MenuItemForm,
    OpenOrderForm,
    RestaurantForm,
    TableForm,
)
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


def _get_owned_restaurant(request: HttpRequest, slug: str) -> Restaurant:
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if restaurant.owner_id and restaurant.owner_id != request.user.id and not request.user.is_staff:
        raise Http404("Restaurante no encontrado o sin permisos de acceso.")
    return restaurant


def dashboard_login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard_home")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            messages.success(request, f"¡Bienvenido, {request.user.username}!")
            next_url = request.GET.get("next") or request.POST.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("dashboard_home")
    else:
        form = AuthenticationForm(request)

    return render(request, "restaurants/dashboard/login.html", {"form": form})


def dashboard_register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("dashboard_home")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(
                request,
                "¡Cuenta de propietario creada con éxito! Ahora registra tu restaurante.",
            )
            return redirect("dashboard_home")
    else:
        form = UserCreationForm()

    return render(request, "restaurants/dashboard/register.html", {"form": form})


def dashboard_logout(request: HttpRequest) -> HttpResponse:
    logout(request)
    messages.info(request, "Sesión cerrada correctamente.")
    return redirect("home")


@login_required
def dashboard_home(request: HttpRequest) -> HttpResponse:
    if request.user.is_staff:
        restaurants = Restaurant.objects.all().order_by("name")
    else:
        restaurants = Restaurant.objects.filter(owner=request.user).order_by("name")

    if request.method == "POST":
        form = RestaurantForm(request.POST)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            restaurant.save()
            messages.success(request, f"¡Restaurante '{restaurant.name}' registrado exitosamente!")
            return redirect("restaurant_dashboard", slug=restaurant.slug)
    else:
        form = RestaurantForm()

    return render(
        request,
        "restaurants/dashboard/index.html",
        {
            "restaurants": restaurants,
            "form": form,
        },
    )


@login_required
def restaurant_dashboard(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)

    tables = (
        restaurant.tables.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "orders",
                queryset=TableOrder.objects.filter(
                    status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
                )
                .prefetch_related("items__menu_item")
                .order_by("-created_at"),
                to_attr="active_orders_list",
            )
        )
        .order_by("number")
    )

    tables_data = []
    total_open_balance = Decimal("0.00")
    active_tables_count = 0

    for tbl in tables:
        active_order = tbl.active_orders_list[0] if tbl.active_orders_list else None
        guest_path = f"/r/{restaurant.slug}/t/{tbl.number}/"
        if active_order:
            active_tables_count += 1
            total_open_balance += active_order.amount_remaining

        tables_data.append(
            {
                "table": tbl,
                "active_order": active_order,
                "guest_path": guest_path,
                "guest_url": request.build_absolute_uri(guest_path),
            }
        )

    # Financial metrics
    succeeded_payments = OrderPayment.objects.filter(
        order__restaurant=restaurant, status=OrderPayment.Status.SUCCEEDED
    )
    tips_sum = succeeded_payments.aggregate(Sum("tip_amount"))["tip_amount__sum"] or Decimal("0.00")
    revenue_sum = (
        succeeded_payments.aggregate(Sum("subtotal_amount"))["subtotal_amount__sum"]
        or Decimal("0.00")
    )
    payments_count = succeeded_payments.count()

    # Reviews and dish stats
    reviews = OrderReview.objects.filter(restaurant=restaurant)
    avg_rating = reviews.aggregate(Avg("overall_rating"))["overall_rating__avg"]
    avg_rating_formatted = f"{avg_rating:.1f}" if avg_rating else "5.0"
    reviews_count = reviews.count()

    # Dish popularity ratings
    dish_stats = []
    for dish in restaurant.menu_items.filter(is_available=True):
        thumbs_up = DishRating.objects.filter(menu_item=dish, liked=True).count()
        thumbs_down = DishRating.objects.filter(menu_item=dish, liked=False).count()
        total_dish_ratings = thumbs_up + thumbs_down
        satisfaction_pct = (
            int((thumbs_up / total_dish_ratings) * 100) if total_dish_ratings > 0 else 100
        )
        dish_stats.append(
            {
                "dish": dish,
                "thumbs_up": thumbs_up,
                "thumbs_down": thumbs_down,
                "total_ratings": total_dish_ratings,
                "satisfaction_pct": satisfaction_pct,
            }
        )

    recent_payments = (
        succeeded_payments.select_related("order__table")
        .order_by("-paid_at", "-created_at")[:8]
    )

    table_form = TableForm(restaurant=restaurant)
    restaurant_form = RestaurantForm(instance=restaurant)

    context = {
        "restaurant": restaurant,
        "tables_data": tables_data,
        "total_tables": len(tables),
        "active_tables_count": active_tables_count,
        "total_open_balance": total_open_balance,
        "tips_sum": tips_sum,
        "revenue_sum": revenue_sum,
        "payments_count": payments_count,
        "avg_rating": avg_rating_formatted,
        "reviews_count": reviews_count,
        "dish_stats": dish_stats,
        "recent_payments": recent_payments,
        "table_form": table_form,
        "restaurant_form": restaurant_form,
    }
    return render(request, "restaurants/dashboard/overview.html", context)


@login_required
def restaurant_settings(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    if request.method == "POST":
        form = RestaurantForm(request.POST, instance=restaurant)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuración del restaurante actualizada correctamente.")
            return redirect("restaurant_dashboard", slug=restaurant.slug)
        else:
            messages.error(request, "Error al actualizar la configuración del restaurante.")
    return redirect("restaurant_dashboard", slug=restaurant.slug)


@login_required
@require_POST
def table_create(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    form = TableForm(request.POST, restaurant=restaurant)
    if form.is_valid():
        table = form.save(commit=False)
        table.restaurant = restaurant
        table.save()
        messages.success(request, f"Mesa N°{table.number} creada con éxito.")
    else:
        error_msgs = "; ".join([f"{err}" for errs in form.errors.values() for err in errs])
        messages.error(request, f"Error al crear mesa: {error_msgs}")
    return redirect("restaurant_dashboard", slug=restaurant.slug)


@login_required
@require_POST
def table_delete(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)
    num = table.number
    table.delete()
    messages.success(request, f"Mesa N°{num} eliminada correctamente.")
    return redirect("restaurant_dashboard", slug=restaurant.slug)


@login_required
def menu_manage(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)

    categories = (
        restaurant.categories.all()
        .prefetch_related(
            Prefetch("items", queryset=MenuItem.objects.all().order_by("display_order", "name"))
        )
        .order_by("display_order", "name")
    )
    uncategorized_items = restaurant.menu_items.filter(category__isnull=True).order_by(
        "display_order", "name"
    )

    category_form = MenuCategoryForm()
    item_form = MenuItemForm(restaurant=restaurant)

    context = {
        "restaurant": restaurant,
        "categories": categories,
        "uncategorized_items": uncategorized_items,
        "category_form": category_form,
        "item_form": item_form,
    }
    return render(request, "restaurants/dashboard/menu_manage.html", context)


@login_required
@require_POST
def category_create(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    form = MenuCategoryForm(request.POST)
    if form.is_valid():
        category = form.save(commit=False)
        category.restaurant = restaurant
        category.save()
        messages.success(request, f"Categoría '{category.name}' agregada exitosamente.")
    else:
        error_msgs = "; ".join([f"{err}" for errs in form.errors.values() for err in errs])
        messages.error(request, f"Error al crear categoría: {error_msgs}")
    return redirect("restaurant_menu_manage", slug=restaurant.slug)


@login_required
@require_POST
def menu_item_create(request: HttpRequest, slug: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    form = MenuItemForm(request.POST, restaurant=restaurant)
    if form.is_valid():
        item = form.save(commit=False)
        item.restaurant = restaurant
        item.save()
        messages.success(request, f"Platillo '{item.name}' agregado al menú.")
    else:
        error_msgs = "; ".join([f"{err}" for errs in form.errors.values() for err in errs])
        messages.error(request, f"Error al crear platillo: {error_msgs}")
    return redirect("restaurant_menu_manage", slug=restaurant.slug)


@login_required
@require_POST
def menu_item_toggle(request: HttpRequest, slug: str, item_id: int) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    item = get_object_or_404(MenuItem, restaurant=restaurant, pk=item_id)
    item.is_available = not item.is_available
    item.save(update_fields=["is_available"])
    status_label = "disponible" if item.is_available else "agotado"
    messages.success(request, f"'{item.name}' marcado como {status_label}.")
    return redirect("restaurant_menu_manage", slug=restaurant.slug)


@login_required
def table_pos(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)
    order = (
        table.orders.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )
        .order_by("-created_at")
        .first()
    )

    categories = (
        restaurant.categories.filter(is_active=True)
        .prefetch_related(
            Prefetch("items", queryset=MenuItem.objects.filter(is_available=True).order_by("display_order"))
        )
        .order_by("display_order")
    )

    open_order_form = OpenOrderForm(
        initial={
            "waiter_name": request.user.get_full_name() or request.user.username,
            "guests_count": 2,
        }
    )

    guest_path = f"/r/{restaurant.slug}/t/{table.number}/"
    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "categories": categories,
        "open_order_form": open_order_form,
        "guest_path": guest_path,
        "guest_url": request.build_absolute_uri(guest_path),
    }
    return render(request, "restaurants/dashboard/table_pos.html", context)


@login_required
@require_POST
def pos_open_order(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)

    order = (
        table.orders.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )
        .order_by("-created_at")
        .first()
    )
    if not order:
        form = OpenOrderForm(request.POST)
        default_waiter = request.user.get_full_name() or request.user.username
        if form.is_valid():
            waiter = form.cleaned_data.get("waiter_name") or default_waiter
            guests = form.cleaned_data.get("guests_count") or 2
        else:
            waiter = request.POST.get("waiter_name") or default_waiter
            try:
                guests = int(request.POST.get("guests_count", 2))
            except (ValueError, TypeError):
                guests = 2

        order = TableOrder.objects.create(
            restaurant=restaurant,
            table=table,
            status=TableOrder.Status.OPEN,
            waiter_name=waiter,
            guests_count=guests,
        )
        messages.success(request, f"Comanda abierta para Mesa N°{table.number}.")

    if request.headers.get("HX-Request"):
        return render(
            request,
            "restaurants/dashboard/_order_panel.html",
            {
                "restaurant": restaurant,
                "table": table,
                "order": order,
                "guest_path": f"/r/{restaurant.slug}/t/{table.number}/",
            },
        )

    return redirect("restaurant_table_pos", slug=restaurant.slug, table_number=table.number)


@login_required
@require_POST
def pos_add_item(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)

    order = (
        table.orders.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )
        .order_by("-created_at")
        .first()
    )
    if not order:
        default_waiter = request.user.get_full_name() or request.user.username
        order = TableOrder.objects.create(
            restaurant=restaurant,
            table=table,
            status=TableOrder.Status.OPEN,
            waiter_name=default_waiter,
            guests_count=2,
        )

    menu_item_id = request.POST.get("menu_item_id")
    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (ValueError, TypeError):
        quantity = 1

    if menu_item_id:
        menu_item = get_object_or_404(MenuItem, restaurant=restaurant, pk=menu_item_id)
        order.add_item(menu_item, quantity=quantity)

    order = (
        table.orders.filter(pk=order.pk)
        .prefetch_related("items__menu_item")
        .first()
    )

    if request.headers.get("HX-Request"):
        return render(
            request,
            "restaurants/dashboard/_order_panel.html",
            {
                "restaurant": restaurant,
                "table": table,
                "order": order,
                "guest_path": f"/r/{restaurant.slug}/t/{table.number}/",
            },
        )

    return redirect("restaurant_table_pos", slug=restaurant.slug, table_number=table.number)


@login_required
@require_POST
def pos_update_item(request: HttpRequest, slug: str, table_number: str, item_id: int) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)
    order = (
        table.orders.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )
        .order_by("-created_at")
        .first()
    )

    if order:
        item = get_object_or_404(OrderItem, order=order, pk=item_id)
        action = request.POST.get("action", "")
        if action == "increment":
            item.quantity += 1
            item.save(update_fields=["quantity"])
        elif action == "decrement":
            if item.quantity > 1:
                item.quantity -= 1
                item.save(update_fields=["quantity"])
            else:
                item.delete()
        elif action == "remove":
            item.delete()

        order.recalculate_totals()
        order = (
            table.orders.filter(pk=order.pk)
            .prefetch_related("items__menu_item")
            .first()
        )

    if request.headers.get("HX-Request"):
        return render(
            request,
            "restaurants/dashboard/_order_panel.html",
            {
                "restaurant": restaurant,
                "table": table,
                "order": order,
                "guest_path": f"/r/{restaurant.slug}/t/{table.number}/",
            },
        )

    return redirect("restaurant_table_pos", slug=restaurant.slug, table_number=table.number)


@login_required
@require_POST
def pos_close_order(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)
    order = (
        table.orders.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )
        .order_by("-created_at")
        .first()
    )

    if order:
        order.status = (
            TableOrder.Status.PAID
            if order.amount_remaining == Decimal("0.00")
            else TableOrder.Status.CANCELLED
        )
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at", "updated_at"])
        messages.success(request, f"Comanda de Mesa N°{table.number} cerrada.")

    if request.headers.get("HX-Request"):
        return render(
            request,
            "restaurants/dashboard/_order_panel.html",
            {
                "restaurant": restaurant,
                "table": table,
                "order": None,
                "guest_path": f"/r/{restaurant.slug}/t/{table.number}/",
            },
        )

    return redirect("restaurant_table_pos", slug=restaurant.slug, table_number=table.number)


@login_required
def table_qr_print(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    restaurant = _get_owned_restaurant(request, slug)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number)

    guest_path = f"/r/{restaurant.slug}/t/{table.number}/"
    guest_url = request.build_absolute_uri(guest_path)

    context = {
        "restaurant": restaurant,
        "table": table,
        "guest_path": guest_path,
        "guest_url": guest_url,
    }
    return render(request, "restaurants/dashboard/qr_print.html", context)
