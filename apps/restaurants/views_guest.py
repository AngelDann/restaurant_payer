from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

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

import apps.billing.services as billing_services

if not hasattr(billing_services, "StripeGatewayError"):
    class StripeGatewayError(Exception):
        """Gateway error raised during Stripe payment operations."""
        pass
    billing_services.StripeGatewayError = StripeGatewayError
else:
    StripeGatewayError = billing_services.StripeGatewayError

if not hasattr(billing_services, "verify_and_complete_payment_intent"):
    def verify_and_complete_payment_intent(payment: OrderPayment) -> bool:
        """
        Verify payment status with Stripe and mark succeeded if confirmed.
        Returns True if payment succeeded, False otherwise.
        """
        if payment.status == OrderPayment.Status.SUCCEEDED:
            return True
        secret_key = (getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
        if not secret_key or not payment.stripe_payment_intent_id:
            return False
        try:
            import stripe
            stripe.api_key = secret_key
            intent = stripe.PaymentIntent.retrieve(payment.stripe_payment_intent_id)
            if intent.get("status") == "succeeded":
                payment_method_label = "card"
                types = intent.get("payment_method_types")
                if types and isinstance(types, list) and types:
                    payment_method_label = types[0]
                payment.mark_succeeded(payment_method_label=payment_method_label)
                _broadcast_order_update(payment.order)
                return True
        except Exception as exc:
            logger.warning("Failed to verify PaymentIntent %s: %s", payment.stripe_payment_intent_id, exc)
        return False
    billing_services.verify_and_complete_payment_intent = verify_and_complete_payment_intent
else:
    verify_and_complete_payment_intent = billing_services.verify_and_complete_payment_intent

from apps.billing.services import (
    StripeGatewayError,
    create_order_payment_intent,
    verify_and_complete_payment_intent,
)

logger = logging.getLogger(__name__)


def _broadcast_order_update(order: TableOrder) -> None:
    """Safely notify WebSocket listeners of order changes if Channels is configured."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()
        if channel_layer:
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
    except Exception as exc:  # pragma: no cover
        logger.debug("Failed to broadcast order update: %s", exc)


def _get_active_table(slug: str, table_number: str) -> tuple[Restaurant, Table]:
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(Table, restaurant=restaurant, number=table_number, is_active=True)
    return restaurant, table


def _parse_decimal(val: str | None, default: Decimal = Decimal("0.00")) -> Decimal:
    if not val:
        return default
    cleaned = str(val).strip().replace(",", ".")
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return default


def table_hub(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """Main QR landing card replicating Expirenza / mbnk.biz card UI."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "has_active_order": bool(order and order.is_payable),
        "amount_remaining": order.amount_remaining if order else Decimal("0.00"),
        "guests_count": order.guests_count if order else 2,
    }
    return render(request, "restaurants/guest/table_hub.html", context)


def table_menu(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """Digital menu grouped by category with dish images, weight, price in MXN."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    categories = (
        restaurant.categories.filter(is_active=True)
        .prefetch_related("items")
        .order_by("display_order", "id")
    )
    uncategorized_items = restaurant.menu_items.filter(
        category__isnull=True,
        is_available=True,
    ).order_by("display_order", "name")

    order_items_count = order.items.count() if order else 0
    order_subtotal = order.subtotal if order else Decimal("0.00")

    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "categories": categories,
        "uncategorized_items": uncategorized_items,
        "order_items_count": order_items_count,
        "order_subtotal": order_subtotal,
    }
    return render(request, "restaurants/guest/menu.html", context)


@require_POST
def guest_add_item(request: HttpRequest, slug: str, table_number: str, item_id: int) -> HttpResponse:
    """Add 1 or more of an item to the table's open order (or create a new open order)."""
    restaurant, table = _get_active_table(slug, table_number)
    menu_item = get_object_or_404(MenuItem, id=item_id, restaurant=restaurant, is_available=True)

    try:
        quantity = max(1, int(request.POST.get("quantity", 1)))
    except (ValueError, TypeError):
        quantity = 1

    notes = request.POST.get("notes", "").strip()

    order = table.get_active_order()
    if not order:
        order = TableOrder.objects.create(
            restaurant=restaurant,
            table=table,
            status=TableOrder.Status.OPEN,
            guests_count=2,
        )
    else:
        # Clear prefetch cache so add_item and recalculate_totals evaluate fresh DB items
        if hasattr(order, "_prefetched_objects_cache"):
            order._prefetched_objects_cache.clear()

    order.add_item(menu_item, quantity=quantity, notes=notes)
    _broadcast_order_update(order)

    if request.headers.get("HX-Request") or request.META.get("HTTP_HX_REQUEST") == "true":
        next_url = request.POST.get("next") or reverse(
            "guest_table_menu", kwargs={"slug": slug, "table_number": table_number}
        )
        response = HttpResponse(status=204)
        response["HX-Redirect"] = next_url
        return response

    next_url = request.POST.get("next") or reverse(
        "guest_table_menu", kwargs={"slug": slug, "table_number": table_number}
    )
    return redirect(next_url)


def _compute_bill_totals(
    order: TableOrder | None,
    split_mode: str = "full",
    split_count: int = 1,
    selected_item_ids: list[int] | None = None,
    tip_percent: str = "10",
    custom_tip_amount: Decimal | None = None,
) -> dict:
    """Helper to compute subtotal, tips (10%, 15%, 20%), chosen tip, and total."""
    if not order:
        return {
            "base_subtotal": Decimal("0.00"),
            "tip_10": Decimal("0.00"),
            "tip_15": Decimal("0.00"),
            "tip_20": Decimal("0.00"),
            "tip_amount": Decimal("0.00"),
            "tip_percent": "0",
            "total_amount": Decimal("0.00"),
            "split_mode": "full",
            "split_count": 1,
            "selected_item_ids": [],
        }

    remaining = order.amount_remaining

    if split_mode == OrderPayment.SplitMode.EQUAL:
        split_count = max(1, split_count)
        base_subtotal = (remaining / Decimal(split_count)).quantize(Decimal("0.01"))
    elif split_mode == OrderPayment.SplitMode.ITEMS and selected_item_ids:
        items = order.items.filter(id__in=selected_item_ids)
        base_subtotal = sum(
            (it.unpaid_line_total for it in items),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
    else:
        split_mode = OrderPayment.SplitMode.FULL
        base_subtotal = remaining

    tip_10 = (base_subtotal * Decimal("0.10")).quantize(Decimal("0.01"))
    tip_15 = (base_subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
    tip_20 = (base_subtotal * Decimal("0.20")).quantize(Decimal("0.01"))

    tip_percent_clean = str(tip_percent).strip()
    if tip_percent_clean == "custom" and custom_tip_amount is not None:
        tip_amount = max(Decimal("0.00"), custom_tip_amount).quantize(Decimal("0.01"))
    elif tip_percent_clean == "0" or tip_percent_clean == "sin":
        tip_amount = Decimal("0.00")
        tip_percent_clean = "0"
    elif tip_percent_clean == "15":
        tip_amount = tip_15
    elif tip_percent_clean == "20":
        tip_amount = tip_20
    else:
        tip_amount = tip_10
        tip_percent_clean = "10"

    total_amount = (base_subtotal + tip_amount).quantize(Decimal("0.01"))

    return {
        "base_subtotal": base_subtotal,
        "tip_10": tip_10,
        "tip_15": tip_15,
        "tip_20": tip_20,
        "tip_amount": tip_amount,
        "tip_percent": tip_percent_clean,
        "total_amount": total_amount,
        "split_mode": split_mode,
        "split_count": split_count,
        "selected_item_ids": selected_item_ids or [],
    }


def table_bill(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """Full Bill screen matching Expirenza / mbnk.biz UI."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    items = list(order.items.select_related("menu_item").all()) if order else []
    unpaid_items = [it for it in items if it.unpaid_quantity > 0]

    calc = _compute_bill_totals(order, split_mode="full", tip_percent="10")

    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "items": items,
        "unpaid_items": unpaid_items,
        "stripe_public_key": getattr(settings, "STRIPE_PUBLIC_KEY", ""),
        "stripe_ready": bool(
            restaurant.can_accept_stripe_split
            and getattr(settings, "STRIPE_PUBLIC_KEY", "")
            and getattr(settings, "STRIPE_SECRET_KEY", "")
        ),
        **calc,
    }
    return render(request, "restaurants/guest/bill.html", context)


@require_http_methods(["GET", "POST"])
def bill_calculate_partial(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """HTMX partial endpoint calculating subtotal & tips based on split and tip choice."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    data = request.POST if request.method == "POST" else request.GET

    split_mode = data.get("split_mode", "full")
    try:
        split_count = max(1, int(data.get("split_count", 2)))
    except (ValueError, TypeError):
        split_count = 2

    raw_items = data.getlist("selected_items")
    if not raw_items and data.get("selected_items"):
        raw_items = [s.strip() for s in data.get("selected_items", "").split(",") if s.strip()]

    selected_item_ids: list[int] = []
    for raw in raw_items:
        try:
            selected_item_ids.append(int(raw))
        except (ValueError, TypeError):
            continue

    tip_percent = data.get("tip_percent", "10")
    custom_tip_raw = data.get("custom_tip", "")
    custom_tip_amount = None
    if custom_tip_raw:
        custom_tip_amount = _parse_decimal(custom_tip_raw, None)

    calc = _compute_bill_totals(
        order=order,
        split_mode=split_mode,
        split_count=split_count,
        selected_item_ids=selected_item_ids,
        tip_percent=tip_percent,
        custom_tip_amount=custom_tip_amount,
    )

    items = list(order.items.select_related("menu_item").all()) if order else []
    unpaid_items = [it for it in items if it.unpaid_quantity > 0]

    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "items": items,
        "unpaid_items": unpaid_items,
        "stripe_public_key": getattr(settings, "STRIPE_PUBLIC_KEY", ""),
        "stripe_ready": bool(
            restaurant.can_accept_stripe_split
            and getattr(settings, "STRIPE_PUBLIC_KEY", "")
            and getattr(settings, "STRIPE_SECRET_KEY", "")
        ),
        "custom_tip_input": custom_tip_raw,
        **calc,
    }
    return render(request, "restaurants/guest/_bill_calculator.html", context)


@require_POST
def bill_create_payment(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """Create OrderPayment, trigger Stripe PaymentIntent creation, and return client_secret for Stripe Elements."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    if not order or not order.is_payable:
        err_msg = "No hay una cuenta activa por pagar en esta mesa."
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.content_type == "application/json"
        ):
            return JsonResponse({"error": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("guest_table_hub", slug=slug, table_number=table_number)

    if not restaurant.can_accept_stripe_split:
        err_msg = "El restaurante no tiene configurada su cuenta de Stripe Connect."
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.content_type == "application/json"
        ):
            return JsonResponse({"error": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("guest_table_bill", slug=slug, table_number=table_number)

    split_mode = request.POST.get("split_mode", OrderPayment.SplitMode.FULL)
    try:
        split_count = max(1, int(request.POST.get("split_count", 1)))
    except (ValueError, TypeError):
        split_count = 1

    selected_items_raw = request.POST.getlist("selected_items")
    selected_item_ids: list[int] = []
    for raw in selected_items_raw:
        try:
            selected_item_ids.append(int(raw))
        except (ValueError, TypeError):
            continue

    tip_percent_str = request.POST.get("tip_percentage", "10")
    custom_tip_raw = request.POST.get("custom_tip", "")
    custom_tip_amount = None
    if custom_tip_raw:
        custom_tip_amount = _parse_decimal(custom_tip_raw, None)

    calc = _compute_bill_totals(
        order=order,
        split_mode=split_mode,
        split_count=split_count,
        selected_item_ids=selected_item_ids,
        tip_percent=tip_percent_str,
        custom_tip_amount=custom_tip_amount,
    )

    subtotal_amount = calc["base_subtotal"]
    tip_amount = calc["tip_amount"]
    total_amount = calc["total_amount"]
    try:
        tip_percentage_int = int(calc["tip_percent"])
    except ValueError:
        tip_percentage_int = 0

    payment_method = request.POST.get("payment_method", "card")
    payer_name = request.POST.get("payer_name", "").strip()

    platform_fee = restaurant.calculate_platform_fee(subtotal_amount)

    payment_kwargs = {
        "order": order,
        "payer_name": payer_name,
        "split_mode": split_mode,
        "subtotal_amount": subtotal_amount,
        "tip_percentage": tip_percentage_int,
        "tip_amount": tip_amount,
        "platform_fee_amount": platform_fee,
        "total_amount": total_amount,
        "payment_method_label": payment_method,
        "selected_item_ids": selected_item_ids if split_mode == OrderPayment.SplitMode.ITEMS else [],
        "status": OrderPayment.Status.PENDING,
    }
    if hasattr(OrderPayment, "split_Count"):
        payment_kwargs["split_Count"] = split_count
    else:
        payment_kwargs["split_count"] = split_count

    payment = OrderPayment.objects.create(**payment_kwargs)

    try:
        intent_data = create_order_payment_intent(payment)
    except (StripeGatewayError, Exception) as exc:
        logger.warning("Stripe PaymentIntent creation failed for payment #%s: %s", payment.id, exc)
        payment.status = OrderPayment.Status.FAILED
        payment.save(update_fields=["status"])
        err_msg = str(exc)
        if (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.content_type == "application/json"
        ):
            return JsonResponse({"error": err_msg}, status=400)
        messages.error(request, err_msg)
        return redirect("guest_table_bill", slug=slug, table_number=table_number)

    return_url = request.build_absolute_uri(
        reverse(
            "guest_payment_complete",
            kwargs={"slug": slug, "table_number": table_number, "payment_id": payment.id},
        )
    )

    is_ajax_json = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in request.headers.get("Accept", "")
        or request.content_type == "application/json"
    )

    if is_ajax_json:
        return JsonResponse(
            {
                "client_secret": intent_data.get("client_secret", ""),
                "payment_id": payment.id,
                "return_url": return_url,
            }
        )

    return redirect(return_url)


def payment_complete(request: HttpRequest, slug: str, table_number: str, payment_id: int) -> HttpResponse:
    """Stripe confirmation callback that verifies payment succeeded and redirects to dish review."""
    restaurant, table = _get_active_table(slug, table_number)
    payment = get_object_or_404(
        OrderPayment,
        id=payment_id,
        order__table=table,
        order__restaurant=restaurant,
    )

    is_verified = (payment.status == OrderPayment.Status.SUCCEEDED)
    if not is_verified:
        try:
            is_verified = bool(verify_and_complete_payment_intent(payment))
        except Exception as exc:
            logger.warning("Error verifying payment #%s: %s", payment.id, exc)
            is_verified = False

    payment.refresh_from_db()
    if is_verified or payment.status == OrderPayment.Status.SUCCEEDED:
        return redirect(
            "guest_review_dishes",
            slug=slug,
            table_number=table_number,
            payment_id=payment.id,
        )

    messages.error(request, "El pago aún no ha sido confirmado por el procesador.")
    return redirect("guest_table_bill", slug=slug, table_number=table_number)


@require_http_methods(["GET", "POST"])
def review_dishes(request: HttpRequest, slug: str, table_number: str, payment_id: int) -> HttpResponse:
    """Screen 1: Thumbs up / down rating per dish in the order."""
    restaurant, table = _get_active_table(slug, table_number)
    payment = get_object_or_404(
        OrderPayment,
        id=payment_id,
        order__table=table,
        order__restaurant=restaurant,
    )
    order = payment.order

    # Dishes to rate: from selected_item_ids or all order items
    if payment.selected_item_ids:
        dishes = MenuItem.objects.filter(order_items__id__in=payment.selected_item_ids).distinct()
    else:
        dishes = MenuItem.objects.filter(order_items__order=order).distinct()

    # If order had no specific MenuItem foreign keys, grab all active restaurant items as fallback
    if not dishes.exists():
        dishes = restaurant.menu_items.filter(is_available=True)[:4]

    if request.method == "POST":
        review, _ = OrderReview.objects.get_or_create(
            restaurant=restaurant,
            order=order,
            payment=payment,
        )

        for dish in dishes:
            val = request.POST.get(f"dish_{dish.id}")
            if val in ["1", "like", "up", "true", "True"]:
                DishRating.objects.update_or_create(
                    review=review,
                    menu_item=dish,
                    defaults={"liked": True},
                )
            elif val in ["0", "dislike", "down", "false", "False"]:
                DishRating.objects.update_or_create(
                    review=review,
                    menu_item=dish,
                    defaults={"liked": False},
                )

        return redirect(
            "guest_review_receipt",
            slug=slug,
            table_number=table_number,
            payment_id=payment.id,
        )

    context = {
        "restaurant": restaurant,
        "table": table,
        "payment": payment,
        "order": order,
        "dishes": dishes,
    }
    return render(request, "restaurants/guest/review_dishes.html", context)


@require_http_methods(["GET", "POST"])
def review_receipt(request: HttpRequest, slug: str, table_number: str, payment_id: int) -> HttpResponse:
    """Screen 2: Payment confirmed banner, receipt, 5-star rating & Google Maps modal."""
    restaurant, table = _get_active_table(slug, table_number)
    payment = get_object_or_404(
        OrderPayment,
        id=payment_id,
        order__table=table,
        order__restaurant=restaurant,
    )
    order = payment.order
    review = getattr(payment, "review", None) or OrderReview.objects.filter(payment=payment).first()

    if request.method == "POST":
        try:
            overall_rating = min(5, max(1, int(request.POST.get("overall_rating", 5))))
        except (ValueError, TypeError):
            overall_rating = 5

        comment = request.POST.get("comment", "").strip()
        redirected = request.POST.get("redirected_to_google") in ["1", "true", "True"]

        if not review:
            review = OrderReview.objects.create(
                restaurant=restaurant,
                order=order,
                payment=payment,
                overall_rating=overall_rating,
                comment=comment,
                redirected_to_google=redirected,
            )
        else:
            review.overall_rating = overall_rating
            if comment:
                review.comment = comment
            if redirected:
                review.redirected_to_google = True
            review.save()

        if request.headers.get("HX-Request") or (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return JsonResponse(
                {
                    "success": True,
                    "overall_rating": review.overall_rating,
                    "prompt_google": review.should_prompt_google_maps,
                    "google_maps_url": restaurant.google_maps_review_url,
                }
            )

        context = {
            "restaurant": restaurant,
            "table": table,
            "payment": payment,
            "order": order,
            "review": review,
            "prompt_google": review.should_prompt_google_maps,
            "saved": True,
        }
        return render(request, "restaurants/guest/review_receipt.html", context)

    context = {
        "restaurant": restaurant,
        "table": table,
        "payment": payment,
        "order": order,
        "review": review,
        "prompt_google": review.should_prompt_google_maps if review else False,
        "saved": False,
    }
    return render(request, "restaurants/guest/review_receipt.html", context)


@require_http_methods(["GET", "POST"])
def standalone_feedback(request: HttpRequest, slug: str, table_number: str) -> HttpResponse:
    """Direct feedback screen accessible from the table hub without payment."""
    restaurant, table = _get_active_table(slug, table_number)
    order = table.get_active_order()

    if request.method == "POST":
        try:
            overall_rating = min(5, max(1, int(request.POST.get("overall_rating", 5))))
        except (ValueError, TypeError):
            overall_rating = 5

        comment = request.POST.get("comment", "").strip()
        redirected = request.POST.get("redirected_to_google") in ["1", "true", "True"]

        review = OrderReview.objects.create(
            restaurant=restaurant,
            order=order,
            overall_rating=overall_rating,
            comment=comment,
            redirected_to_google=redirected,
        )

        if request.headers.get("HX-Request") or (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
        ):
            return JsonResponse(
                {
                    "success": True,
                    "overall_rating": review.overall_rating,
                    "prompt_google": review.should_prompt_google_maps,
                    "google_maps_url": restaurant.google_maps_review_url,
                }
            )

        context = {
            "restaurant": restaurant,
            "table": table,
            "order": order,
            "review": review,
            "prompt_google": review.should_prompt_google_maps,
            "saved": True,
        }
        return render(request, "restaurants/guest/standalone_feedback.html", context)

    context = {
        "restaurant": restaurant,
        "table": table,
        "order": order,
        "review": None,
        "prompt_google": False,
        "saved": False,
    }
    return render(request, "restaurants/guest/standalone_feedback.html", context)
