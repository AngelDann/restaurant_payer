from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="billing_index"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path(
        "connect/start/<slug:slug>/",
        views.connect_onboarding_start,
        name="stripe_connect_onboarding",
    ),
    path(
        "connect/return/<slug:slug>/",
        views.connect_onboarding_return,
        name="stripe_connect_return",
    ),
    path(
        ".well-known/apple-developer-merchantid-domain-association",
        views.apple_pay_domain_association,
        name="billing_apple_pay_domain",
    ),
]
