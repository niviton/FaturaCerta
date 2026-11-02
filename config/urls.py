from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.core.views import home
from apps.monitoramento.api import receber_medicoes
from apps.monitoramento.urls import painel_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("entrar/", auth_views.LoginView.as_view(template_name="accounts/login.html",
                                                 redirect_authenticated_user=True), name="login"),
    path("sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("", home, name="home"),
    # administrador geral
    path("plataforma/", include("apps.plataforma.urls")),
    # integradora
    path("painel/", include(painel_urlpatterns)),
    path("usinas/", include("apps.monitoramento.urls")),
    path("cadastro/", include("apps.cadastro.urls")),
    path("faturas/", include("apps.faturas.urls")),
    path("equipe/", include("apps.accounts.urls")),
    # cliente final
    path("meu/", include("apps.portal.urls")),
    # dispositivos (ESP32)
    path("api/medidores/medicoes", receber_medicoes, name="api_medicoes"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
