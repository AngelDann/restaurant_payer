from django.contrib import admin

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


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "currency", "stripe_account_id", "stripe_onboarding_completed", "is_active")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug", "stripe_account_id")


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "display_order", "is_active")
    list_filter = ("restaurant", "is_active")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "category", "price", "is_available")
    list_filter = ("restaurant", "category", "is_available")
    search_fields = ("name", "description")


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("number", "label", "restaurant", "qr_token", "is_active")
    list_filter = ("restaurant", "is_active")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(TableOrder)
class TableOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "table", "status", "subtotal", "amount_paid", "tips_total", "created_at")
    list_filter = ("restaurant", "status")
    inlines = [OrderItemInline]


@admin.register(OrderPayment)
class OrderPaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "total_amount", "subtotal_amount", "tip_amount", "status", "payment_method_label", "created_at")
    list_filter = ("status", "split_mode")


@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "overall_rating", "redirected_to_google", "created_at")
    list_filter = ("restaurant", "overall_rating")


@admin.register(DishRating)
class DishRatingAdmin(admin.ModelAdmin):
    list_display = ("review", "menu_item", "liked")
