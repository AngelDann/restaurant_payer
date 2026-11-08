from django.urls import include, path

urlpatterns = [
    path("r/", include("apps.restaurants.urls_guest")),
    path("dashboard/", include("apps.restaurants.urls_dashboard")),
]
