from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/", include("caricue.api_urls")),
    path("django-admin/", admin.site.urls),
]

if settings.DEBUG:
    # Development only; production Nginx serves /media/ from the shared volume.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
