from django.contrib import admin

from .models import (
    Cliente,
    Concessionaria,
    ConsentimentoLGPD,
    Inversor,
    LoteCredito,
    Medidor,
    Rateio,
    UnidadeConsumidora,
    Usina,
)


@admin.register(Concessionaria)
class ConcessionariaAdmin(admin.ModelAdmin):
    list_display = ["nome", "sigla", "uf", "layout_fatura", "ativa"]


class ConsentimentoInline(admin.TabularInline):
    model = ConsentimentoLGPD
    extra = 0
    readonly_fields = ["data", "versao_termo", "ip", "registrado_por"]


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "documento", "integradora", "ativo"]
    list_filter = ["integradora"]
    search_fields = ["nome", "documento"]
    inlines = [ConsentimentoInline]


@admin.register(UnidadeConsumidora)
class UCAdmin(admin.ModelAdmin):
    list_display = ["numero_uc", "codigo_cliente", "cliente", "concessionaria", "grupo", "subgrupo"]
    list_filter = ["integradora", "concessionaria", "grupo"]
    search_fields = ["numero_uc", "codigo_cliente", "cliente__nome"]


class RateioInline(admin.TabularInline):
    model = Rateio
    extra = 0


class InversorInline(admin.StackedInline):
    model = Inversor
    extra = 0
    exclude = ["credenciais"]


@admin.register(Usina)
class UsinaAdmin(admin.ModelAdmin):
    list_display = ["nome", "uc_geradora", "enquadramento", "potencia_kwp", "integradora"]
    list_filter = ["integradora", "enquadramento", "tipo"]
    inlines = [RateioInline, InversorInline]


@admin.register(Medidor)
class MedidorAdmin(admin.ModelAdmin):
    list_display = ["usina", "fabricante", "modelo", "provedor_api"]
    exclude = ["credenciais"]


@admin.register(LoteCredito)
class LoteCreditoAdmin(admin.ModelAdmin):
    list_display = ["uc", "mes_referencia", "kwh_gerado", "kwh_saldo", "validade"]
