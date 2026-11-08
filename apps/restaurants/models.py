from __future__ import annotations

import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.db.models import Sum
from django.urls import reverse


def generate_qr_token() -> str:
    return secrets.token_urlsafe(12)


class RestaurantQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def stripe_ready(self):
        return self.filter(is_active=True, stripe_onboarding_completed=True).exclude(
            stripe_account_id=""
        )


class Restaurant(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="restaurants",
    )
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True, db_index=True)
    tagline = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    logo_url = models.URLField(max_length=500, blank=True, default="")
    cover_image_url = models.URLField(max_length=500, blank=True, default="")
    currency = models.CharField(max_length=10, default="MXN")
    is_active = models.BooleanField(default=True, db_index=True)

    # Stripe Connect (México)
    stripe_account_id = models.CharField(
        max_length=120,
        blank=True,
        default="",
        help_text="Stripe Connected Account ID (acct_...)",
    )
    stripe_onboarding_completed = models.BooleanField(default=False)
    platform_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("2.50"),
        help_text="Porcentaje de comisión para la plataforma por transacción.",
    )

    # Google Maps review link
    google_maps_review_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Link directo para dejar reseña en Google Maps.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RestaurantQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("restaurant_dashboard", kwargs={"slug": self.slug})

    @property
    def can_accept_stripe_split(self) -> bool:
        return bool(self.stripe_account_id and self.stripe_onboarding_completed)

    def calculate_platform_fee(self, subtotal_amount: Decimal) -> Decimal:
        fee = (subtotal_amount * self.platform_fee_percent) / Decimal("100.00")
        return fee.quantize(Decimal("0.01"))


class MenuCategory(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="categories",
    )
    name = models.CharField(max_length=120)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "id"]
        verbose_name_plural = "Menu categories"

    def __str__(self) -> str:
        return f"{self.restaurant.name} — {self.name}"


class MenuItemQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_available=True)


class MenuItem(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="menu_items",
    )
    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="items",
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    weight_or_volume = models.CharField(max_length=60, blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image_url = models.URLField(max_length=500, blank=True, default="")
    is_available = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)

    objects = MenuItemQuerySet.as_manager()

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return f"{self.name} (${self.price} {self.restaurant.currency})"


class Table(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="tables",
    )
    number = models.CharField(max_length=20)
    label = models.CharField(max_length=80, blank=True, default="")
    qr_token = models.CharField(
        max_length=32,
        unique=True,
        default=generate_qr_token,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["number"]
        unique_together = [("restaurant", "number")]

    def __str__(self) -> str:
        return f"{self.restaurant.name} - Mesa N°{self.number}"

    @property
    def display_name(self) -> str:
        return self.label or f"Mesa N°{self.number}"

    def get_guest_url(self) -> str:
        return reverse(
            "guest_table_hub",
            kwargs={"slug": self.restaurant.slug, "table_number": self.number},
        )

    def get_active_order(self) -> TableOrder | None:
        return (
            self.orders.filter(
                status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
            )
            .prefetch_related("items__menu_item", "payments")
            .order_by("-created_at")
            .first()
        )


class TableOrderQuerySet(models.QuerySet):
    def active(self):
        return self.filter(
            status__in=[TableOrder.Status.OPEN, TableOrder.Status.PARTIALLY_PAID]
        )


class TableOrder(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Abierta"
        PARTIALLY_PAID = "partially_paid", "Pago Parcial"
        PAID = "paid", "Pagada"
        CANCELLED = "cancelled", "Cancelada"

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    waiter_name = models.CharField(max_length=100, blank=True, default="")
    guests_count = models.PositiveSmallIntegerField(default=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tips_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = TableOrderQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Orden #{self.pk} - {self.table} ({self.get_status_display()})"

    @property
    def amount_remaining(self) -> Decimal:
        remaining = self.subtotal - self.amount_paid
        return max(Decimal("0.00"), remaining.quantize(Decimal("0.01")))

    @property
    def is_payable(self) -> bool:
        return (
            self.status in {self.Status.OPEN, self.Status.PARTIALLY_PAID}
            and self.amount_remaining > Decimal("0.00")
        )

    @property
    def payment_progress_percent(self) -> int:
        if self.subtotal <= Decimal("0.00"):
            return 0
        pct = int((self.amount_paid / self.subtotal) * 100)
        return min(100, max(0, pct))

    def recalculate_totals(self) -> None:
        items_total = Decimal("0.00")
        for item in self.items.all():
            items_total += item.line_total
        succeeded_payments = self.payments.filter(status=OrderPayment.Status.SUCCEEDED)
        paid_sum = succeeded_payments.aggregate(total=Sum("subtotal_amount"))["total"] or Decimal("0.00")
        tips_sum = succeeded_payments.aggregate(total=Sum("tip_amount"))["total"] or Decimal("0.00")

        self.subtotal = items_total.quantize(Decimal("0.01"))
        self.amount_paid = paid_sum.quantize(Decimal("0.01"))
        self.tips_total = tips_sum.quantize(Decimal("0.01"))

        if self.status != self.Status.CANCELLED:
            if self.subtotal > Decimal("0.00") and self.amount_paid >= self.subtotal:
                self.status = self.Status.PAID
            elif self.amount_paid > Decimal("0.00"):
                self.status = self.Status.PARTIALLY_PAID
            else:
                self.status = self.Status.OPEN

        self.save(update_fields=["subtotal", "amount_paid", "tips_total", "status", "updated_at"])

    def add_item(self, menu_item: MenuItem, quantity: int = 1, notes: str = "") -> OrderItem:
        with transaction.atomic():
            item, created = self.items.get_or_create(
                menu_item=menu_item,
                notes=notes,
                defaults={
                    "name_snapshot": menu_item.name,
                    "unit_price": menu_item.price,
                    "quantity": quantity,
                },
            )
            if not created:
                item.quantity += quantity
                item.save(update_fields=["quantity"])
            self.recalculate_totals()
            return item


class OrderItem(models.Model):
    order = models.ForeignKey(
        TableOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    name_snapshot = models.CharField(max_length=160)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    paid_quantity = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.quantity} x {self.name_snapshot}"

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    @property
    def unpaid_quantity(self) -> int:
        return max(0, self.quantity - self.paid_quantity)

    @property
    def unpaid_line_total(self) -> Decimal:
        return (self.unit_price * self.unpaid_quantity).quantize(Decimal("0.01"))


class OrderPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        SUCCEEDED = "succeeded", "Completado"
        FAILED = "failed", "Fallido"
        REFUNDED = "refunded", "Reembolsado"

    class SplitMode(models.TextChoices):
        FULL = "full", "Cuenta Completa"
        EQUAL = "equal", "Partes Iguales"
        ITEMS = "items", "Por Platillos"
        CUSTOM = "custom", "Monto Personalizado"

    order = models.ForeignKey(
        TableOrder,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    payer_name = models.CharField(max_length=100, blank=True, default="")
    split_mode = models.CharField(
        max_length=20,
        choices=SplitMode.choices,
        default=SplitMode.FULL,
    )
    split_Count = models.PositiveSmallIntegerField(default=1)
    subtotal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tip_percentage = models.PositiveSmallIntegerField(default=10)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    platform_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method_label = models.CharField(max_length=60, blank=True, default="apple_pay")
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
    )
    stripe_client_secret = models.CharField(max_length=255, blank=True, default="")
    selected_item_ids = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Pago #{self.pk} - ${self.total_amount} ({self.get_status_display()})"

    def mark_succeeded(self, payment_method_label: str = "") -> None:
        from django.utils import timezone

        with transaction.atomic():
            if self.status == self.Status.SUCCEEDED:
                return
            self.status = self.Status.SUCCEEDED
            if payment_method_label:
                self.payment_method_label = payment_method_label
            self.paid_at = timezone.now()
            self.save(update_fields=["status", "payment_method_label", "paid_at"])

            if self.selected_item_ids:
                for item in self.order.items.filter(id__in=self.selected_item_ids):
                    if item.paid_quantity < item.quantity:
                        item.paid_quantity = min(item.quantity, item.paid_quantity + 1)
                        item.save(update_fields=["paid_quantity"])

            self.order.recalculate_totals()


class OrderReview(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    order = models.ForeignKey(
        TableOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
    )
    payment = models.OneToOneField(
        OrderPayment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
    )
    overall_rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField(blank=True, default="")
    redirected_to_google = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.restaurant.name} — {self.overall_rating}★"

    @property
    def should_prompt_google_maps(self) -> bool:
        return self.overall_rating >= 4 and bool(self.restaurant.google_maps_review_url)


class DishRating(models.Model):
    review = models.ForeignKey(
        OrderReview,
        on_delete=models.CASCADE,
        related_name="dish_ratings",
    )
    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    liked = models.BooleanField(default=True)

    class Meta:
        unique_together = [("review", "menu_item")]

    def __str__(self) -> str:
        icon = "👍" if self.liked else "👎"
        return f"{self.menu_item.name}: {icon}"
