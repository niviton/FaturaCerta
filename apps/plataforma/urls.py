from django.urls import path

from . import views as v

app_name = "plataforma"

urlpatterns = [
    path("", v.VisaoView.as_view(), name="visao"),
    path("integradoras/", v.IntegradoraListView.as_view(), name="integradoras"),
    path("integradoras/nova/", v.IntegradoraCreateView.as_view(), name="integradora_nova"),
    path("integradoras/<int:pk>/", v.IntegradoraUpdateView.as_view(), name="integradora_editar"),
    path("integradoras/<int:pk>/atuar/", v.AtuarView.as_view(), name="atuar"),
    path("sair-da-integradora/", v.SairAtuacaoView.as_view(), name="sair_atuacao"),
    path("usuarios/", v.UsuarioListView.as_view(), name="usuarios"),
    path("usuarios/novo/", v.UsuarioCreateView.as_view(), name="usuario_novo"),
    path("usuarios/<int:pk>/", v.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path("integracoes/", v.IntegracoesView.as_view(), name="integracoes"),
    path("integracoes/inversores/<int:pk>/", v.InversorAdminView.as_view(), name="inversor"),
    path("integracoes/inversores/<int:pk>/testar/", v.TestarConexaoView.as_view(), name="testar"),
    path("integracoes/medidores/<int:pk>/", v.MedidorAdminView.as_view(), name="medidor"),
    path("logs/", v.LogsView.as_view(), name="logs"),
]
