from django.urls import path

from . import views as v

app_name = "cadastro"

urlpatterns = [
    path("clientes/", v.ClienteListView.as_view(), name="clientes"),
    path("clientes/novo/", v.ClienteCreateView.as_view(), name="cliente_novo"),
    path("clientes/<int:pk>/", v.ClienteDetailView.as_view(), name="cliente"),
    path("clientes/<int:pk>/editar/", v.ClienteUpdateView.as_view(), name="cliente_editar"),
    path("clientes/<int:pk>/consentimento/", v.ConsentimentoView.as_view(), name="consentimento"),
    path("clientes/<int:pk>/acesso/", v.AcessoPortalView.as_view(), name="acesso_portal"),
    path("ucs/nova/", v.UCCreateView.as_view(), name="uc_nova"),
    path("ucs/<int:pk>/", v.UCDetailView.as_view(), name="uc"),
    path("ucs/<int:pk>/editar/", v.UCUpdateView.as_view(), name="uc_editar"),
    path("ucs/<int:pk>/creditos/", v.LoteCreditoCreateView.as_view(), name="lote_novo"),
    path("ucs/<int:uc_pk>/medidores/novo/", v.MedidorCreateView.as_view(), name="medidor_novo"),
    path("ucs/<int:uc_pk>/medidores/<int:pk>/", v.MedidorUpdateView.as_view(), name="medidor_editar"),
    path("ucs/<int:uc_pk>/medidores/<int:pk>/token/", v.MedidorTokenView.as_view(), name="medidor_token"),
    path("usinas/nova/", v.UsinaCreateView.as_view(), name="usina_nova"),
    path("usinas/<int:pk>/", v.UsinaDetailView.as_view(), name="usina"),
    path("usinas/<int:pk>/editar/", v.UsinaUpdateView.as_view(), name="usina_editar"),
    path("usinas/<int:usina_pk>/arranjos/", v.ArranjoCreateView.as_view(), name="arranjo_novo"),
    path("usinas/<int:usina_pk>/arranjos/<int:pk>/excluir/", v.ArranjoDeleteView.as_view(), name="arranjo_excluir"),
    path("usinas/<int:usina_pk>/inversores/novo/", v.InversorCreateView.as_view(), name="inversor_novo"),
    path("usinas/<int:usina_pk>/inversores/<int:pk>/", v.InversorUpdateView.as_view(), name="inversor_editar"),
    path("integradora/", v.IntegradoraUpdateView.as_view(), name="integradora"),
]
