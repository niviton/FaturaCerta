from django.urls import path

from . import views

app_name = "monitoramento"

urlpatterns = [
    path("", views.PainelView.as_view(), name="painel"),
]

painel_urlpatterns = ([path("", views.VisaoGeralView.as_view(), name="visao")], "painel")
