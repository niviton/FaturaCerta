from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect

from .audit import registrar
from .models import LogAuditoria


class EquipeIntegradoraMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Painel da integradora: gestor, técnico ou administrador geral atuando como a integradora.
    Tudo é filtrado por request.tenant."""

    apenas_gestor = False

    def test_func(self):
        u = self.request.user
        if self.request.tenant is None:
            return False
        if u.is_admin_geral:
            return True
        return u.is_gestor if self.apenas_gestor else u.is_equipe

    def handle_no_permission(self):
        u = self.request.user
        if u.is_authenticated and u.is_admin_geral and self.request.tenant is None:
            messages.info(self.request, "Escolha uma integradora para ver o painel dela.")
            return redirect("plataforma:integradoras")
        return super().handle_no_permission()


class AdminGeralMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin_geral


class ClienteFinalMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_cliente_final


class TenantQuerysetMixin(EquipeIntegradoraMixin):
    def get_queryset(self):
        return super().get_queryset().da_integradora(self.request.tenant)


class TenantFormMixin(TenantQuerysetMixin):
    """Injeta o tenant no form (para filtrar escolhas) e grava a integradora no objeto."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["integradora"] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        novo = form.instance.pk is None
        form.instance.integradora = self.request.tenant
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object)
        messages.success(self.request, "Salvo.")
        return resp


class AuditarVisualizacaoMixin:
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        registrar(self.request, LogAuditoria.Acao.VER, obj)
        return obj
