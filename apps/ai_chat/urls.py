from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_index, name="ai_chat_index"),
    path("partial/ping/", views.partial_ping, name="ai_chat_partial_ping"),
]
