from __future__ import annotations

from django.urls import path

from apps.restaurants import views_guest

urlpatterns = [
    path(
        "<slug:slug>/t/<str:table_number>/",
        views_guest.table_hub,
        name="guest_table_hub",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/menu/",
        views_guest.table_menu,
        name="guest_table_menu",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/menu/add/<int:item_id>/",
        views_guest.guest_add_item,
        name="guest_add_item",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/bill/",
        views_guest.table_bill,
        name="guest_table_bill",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/bill/calculate/",
        views_guest.bill_calculate_partial,
        name="guest_bill_calculate",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/bill/checkout/",
        views_guest.bill_create_payment,
        name="guest_bill_checkout",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/payment/<int:payment_id>/complete/",
        views_guest.payment_complete,
        name="guest_payment_complete",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/payment/<int:payment_id>/review-dishes/",
        views_guest.review_dishes,
        name="guest_review_dishes",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/payment/<int:payment_id>/receipt/",
        views_guest.review_receipt,
        name="guest_review_receipt",
    ),
    path(
        "<slug:slug>/t/<str:table_number>/feedback/",
        views_guest.standalone_feedback,
        name="guest_feedback",
    ),
]
