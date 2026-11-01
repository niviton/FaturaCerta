from django.contrib import admin

from .models import Integradora, LogAuditoria


@admin.register(Integradora)
class IntegradoraAdmin(admin.ModelAdmin):
    list_display = ["razao_social", "cnpj", "responsavel_tecnico_nome", "ativa"]
    search_fields = ["razao_social", "cnpj"]


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["momento", "usuario", "integradora", "acao", "objeto_tipo", "objeto_id", "ip"]
    list_filter = ["acao", "integradora"]
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
