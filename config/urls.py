from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.core.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("entrar/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("", home, name="home"),
    path("cadastro/", include("apps.cadastro.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
