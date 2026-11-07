from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="billing_index"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
