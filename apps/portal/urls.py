from django.urls import path

from . import views

app_name = "portal"

urlpatterns = [
    path("", views.InicioView.as_view(), name="inicio"),
    path("usinas/<int:pk>/", views.UsinaView.as_view(), name="usina"),
]
