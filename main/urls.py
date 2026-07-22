"""Root URL configuration.

/admin/  Django admin
/api/    JSON API (DRF + JWT)
/        HTMX-rendered pages
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from travel.urls import api_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include((api_urlpatterns, "api"))),
    # Session auth for the browser app (JWT lives under /api for programmatic use).
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("travel.urls")),
]
