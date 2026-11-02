from django.urls import path

from . import views

app_name = "equipe"

urlpatterns = [
    path("", views.UsuarioListView.as_view(), name="usuarios"),
    path("novo/", views.UsuarioCreateView.as_view(), name="novo"),
    path("<int:pk>/", views.UsuarioUpdateView.as_view(), name="editar"),
]
