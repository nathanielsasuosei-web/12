from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "12 Producer Admin"
admin.site.site_title = "12 Admin"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("store.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
