"""
ASGI config: HTTP (Django) + WebSockets (Channels) on one application.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

from apps.ai_chat.routing import websocket_urlpatterns as ai_ws_patterns  # noqa: E402
from apps.restaurants.routing import websocket_urlpatterns as restaurant_ws_patterns  # noqa: E402

websocket_urlpatterns = [*ai_ws_patterns, *restaurant_ws_patterns]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
