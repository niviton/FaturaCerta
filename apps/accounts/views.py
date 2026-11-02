"""Equipe e acessos da integradora (gestor ou administrador geral atuando como a integradora)."""

from django.contrib import messages
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from apps.core.audit import registrar
from apps.core.mixins import EquipeIntegradoraMixin
from apps.core.models import LogAuditoria

from .forms import UsuarioForm
from .models import User


class EquipeMixin(EquipeIntegradoraMixin):
    apenas_gestor = True

    def get_queryset(self):
        return User.objects.filter(integradora=self.request.tenant).exclude(papel=User.Papel.ADMIN_INTERNO)


class UsuarioListView(EquipeMixin, ListView):
    template_name = "accounts/usuarios.html"

    def get_queryset(self):
        return super().get_queryset().select_related("cliente").order_by("papel", "first_name", "username")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(titulo="Equipe e acessos", novo_url=reverse("equipe:novo"), editar_rota="equipe:editar",
                   subtitulo="Gestores e técnicos da sua empresa e os clientes com acesso ao portal.")
        return ctx


class UsuarioFormMixin(EquipeMixin):
    form_class = UsuarioForm
    template_name = "cadastro/form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["integradora"] = self.request.tenant
        return kw

    def form_valid(self, form):
        novo = form.instance.pk is None
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object,
                  f"usuário {self.object.username} ({self.object.papel})")
        messages.success(self.request, "Usuário salvo.")
        return resp

    def get_success_url(self):
        return reverse("equipe:usuarios")


class UsuarioCreateView(UsuarioFormMixin, CreateView):
    extra_context = {"titulo": "Novo usuário"}


class UsuarioUpdateView(UsuarioFormMixin, UpdateView):
    extra_context = {"titulo": "Editar usuário"}
