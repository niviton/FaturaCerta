from django.contrib import admin

from .models import Fatura


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ["uc", "mes_referencia", "consumo_kwh", "energia_injetada_kwh", "energia_compensada_kwh",
                    "valor_total", "status", "origem"]
    list_filter = ["status", "origem", "integradora"]
    search_fields = ["uc__numero_uc", "uc__cliente__nome"]
