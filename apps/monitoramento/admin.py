from django.contrib import admin

from .models import GeracaoDiaria, LeituraMedidor, MedicaoBruta, StatusAtual


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
    list_display = ["medidor", "data", "importacao_kwh", "exportacao_kwh", "carga_kwh", "demo"]


@admin.register(MedicaoBruta)
class MedicaoBrutaAdmin(admin.ModelAdmin):
    list_display = ["medidor", "momento", "potencia_w", "importacao_kwh", "exportacao_kwh", "tensao_v"]
    list_filter = ["medidor"]
