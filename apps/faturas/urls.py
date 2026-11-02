from django.urls import path

from . import views

app_name = "faturas"

urlpatterns = [
    path("", views.FaturaListView.as_view(), name="lista"),
    path("nova/", views.FaturaCreateView.as_view(), name="nova"),
    path("<int:pk>/", views.FaturaUpdateView.as_view(), name="editar"),
]
