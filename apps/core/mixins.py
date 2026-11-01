from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .audit import registrar
from .models import LogAuditoria


class EquipeIntegradoraMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Acesso para gestor e técnico da integradora. Filtra tudo pelo tenant."""

    apenas_gestor = False

    def test_func(self):
        u = self.request.user
        if self.request.tenant is None:
            return False
        return u.is_gestor if self.apenas_gestor else u.is_equipe


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
        return resp


class AuditarVisualizacaoMixin:
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        registrar(self.request, LogAuditoria.Acao.VER, obj)
        return obj
