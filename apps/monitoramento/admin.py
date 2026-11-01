from django.contrib import admin

from .models import GeracaoDiaria, LeituraMedidor, StatusAtual


@admin.register(GeracaoDiaria)
class GeracaoDiariaAdmin(admin.ModelAdmin):
    list_display = ["inversor", "data", "kwh", "demo"]
    list_filter = ["demo", "inversor__usina__integradora"]
    date_hierarchy = "data"


@admin.register(StatusAtual)
class StatusAtualAdmin(admin.ModelAdmin):
    list_display = ["inversor", "online", "potencia_atual_kw", "energia_hoje_kwh", "medido_em", "erro"]


@admin.register(LeituraMedidor)
class LeituraMedidorAdmin(admin.ModelAdmin):
    list_display = ["medidor", "data", "consumo_kwh", "injecao_kwh", "demo"]
