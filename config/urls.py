from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("captcha/", include("captcha.urls")),
    path("ckeditor/", include("ckeditor_uploader.urls")),
    path("", include("apps.core.urls")),
    path("billing/", include("apps.billing.urls")),
    path("docs/", include("apps.docs.urls")),
    path("legal/", include("apps.legal.urls")),
    path("chat/", include("apps.ai_chat.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
