from django.urls import re_path

from apps.restaurants.consumers import TableOrderConsumer

websocket_urlpatterns = [
    re_path(
        r"^ws/restaurants/(?P<slug>[-a-zA-Z0-9_]+)/table/(?P<table_number>[-a-zA-Z0-9_]+)/$",
        TableOrderConsumer.as_asgi(),
    ),
]
