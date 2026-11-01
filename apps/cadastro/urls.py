from django.urls import path

from . import views as v

app_name = "cadastro"

urlpatterns = [
    path("clientes/", v.ClienteListView.as_view(), name="clientes"),
    path("clientes/novo/", v.ClienteCreateView.as_view(), name="cliente_novo"),
    path("clientes/<int:pk>/", v.ClienteDetailView.as_view(), name="cliente"),
    path("clientes/<int:pk>/editar/", v.ClienteUpdateView.as_view(), name="cliente_editar"),
    path("clientes/<int:pk>/consentimento/", v.ConsentimentoView.as_view(), name="consentimento"),
    path("ucs/nova/", v.UCCreateView.as_view(), name="uc_nova"),
    path("ucs/<int:pk>/", v.UCDetailView.as_view(), name="uc"),
    path("ucs/<int:pk>/editar/", v.UCUpdateView.as_view(), name="uc_editar"),
    path("ucs/<int:pk>/creditos/", v.LoteCreditoCreateView.as_view(), name="lote_novo"),
    path("usinas/nova/", v.UsinaCreateView.as_view(), name="usina_nova"),
    path("usinas/<int:pk>/", v.UsinaDetailView.as_view(), name="usina"),
    path("usinas/<int:pk>/editar/", v.UsinaUpdateView.as_view(), name="usina_editar"),
    path("usinas/<int:usina_pk>/inversores/novo/", v.InversorCreateView.as_view(), name="inversor_novo"),
    path("usinas/<int:usina_pk>/inversores/<int:pk>/", v.InversorUpdateView.as_view(), name="inversor_editar"),
    path("usinas/<int:usina_pk>/medidor/novo/", v.MedidorCreateView.as_view(), name="medidor_novo"),
    path("usinas/<int:usina_pk>/medidor/<int:pk>/", v.MedidorUpdateView.as_view(), name="medidor_editar"),
    path("integradora/", v.IntegradoraUpdateView.as_view(), name="integradora"),
]
