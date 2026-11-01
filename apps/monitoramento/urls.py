from django.urls import path

from . import views

app_name = "monitoramento"

urlpatterns = [
    path("", views.PainelView.as_view(), name="painel"),
]
