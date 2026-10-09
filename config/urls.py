from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("orders/", include("orders.urls")),
    path("contact/", include("contact.urls")),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    # In production Caddy serves MEDIA_ROOT. Private beat files are never routed.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
