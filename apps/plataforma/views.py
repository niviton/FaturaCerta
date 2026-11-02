"""Administrador geral: visão de toda a plataforma, cadastro de integradoras e usuários,
integrações (APIs dos inversores, dispositivos ESP) e logs. Pode atuar como qualquer integradora."""

from collections import Counter
from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView

from apps.accounts.forms import UsuarioForm
from apps.accounts.models import User
from apps.cadastro.forms import IntegradoraAdminForm, InversorForm, MedidorForm
from apps.cadastro.models import Cliente, Inversor, Medidor, UnidadeConsumidora, Usina
from apps.core import charts
from apps.core.audit import registrar
from apps.core.middleware import SESSAO_ATUANDO
from apps.core.mixins import AdminGeralMixin
from apps.core.models import Integradora, LogAuditoria
from apps.faturas.models import Fatura
from apps.integracoes.base import ErroIntegracao
from apps.integracoes.registro import provedor_inversor
from apps.monitoramento import graficos as g_monit


class VisaoView(AdminGeralMixin, TemplateView):
    template_name = "plataforma/visao.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        linhas = []
        for i in Integradora.objects.order_by("razao_social"):
            us = Usina.objects.filter(integradora=i)
            linhas.append({
                "obj": i,
                "clientes": Cliente.objects.filter(integradora=i).count(),
                "usinas": us.count(),
                "kwp": us.aggregate(s=Sum("potencia_kwp"))["s"] or Decimal(0),
                "faturas_div": Fatura.objects.filter(integradora=i, status=Fatura.Status.DIVERGENTE).count(),
                "usuarios": i.usuarios.count(),
            })
        inversores = list(Inversor.objects.select_related("usina").prefetch_related("usina__inversores"))
        conectados = sum(1 for inv in inversores if inv.credenciais_configuradas)
        medidores = list(Medidor.objects.all())
        ucs = UnidadeConsumidora.objects.all()
        sub = Counter(ucs.values_list("subgrupo", flat=True))
        enq = Counter(Usina.objects.values_list("enquadramento", flat=True))
        papeis = Counter(User.objects.values_list("papel", flat=True))
        ctx.update(
            linhas=linhas,
            n_integradoras=Integradora.objects.filter(ativa=True).count(),
            n_clientes=Cliente.objects.count(), n_ucs=ucs.count(), n_usinas=Usina.objects.count(),
            kwp=Usina.objects.aggregate(s=Sum("potencia_kwp"))["s"] or Decimal(0),
            n_inversores=len(inversores), conectados=conectados,
            n_medidores=len(medidores), esp_online=sum(1 for m in medidores if m.online),
            n_faturas=Fatura.objects.count(), n_faturas_div=Fatura.objects.filter(status=Fatura.Status.DIVERGENTE).count(),
            papeis=[(User.Papel(p).label, papeis.get(p, 0)) for p in User.Papel.values],
        )
        maior_div = max((x["faturas_div"] for x in linhas), default=0) or 1
        for x in linhas:
            x["div_pct"] = int(x["faturas_div"] / maior_div * 100)
        ctx["n_esp"] = sum(1 for m in medidores if m.provedor_api == "esp")
        ctx.update(
            hero_sub=f"{ctx['n_usinas']} usinas de {ctx['n_clientes']} clientes em {ctx['n_integradoras']} "
                     f"integradora{'s' if ctx['n_integradoras'] != 1 else ''}",
            clientes_txt=f"{ctx['n_clientes']} clientes · {ctx['n_ucs']} UCs",
            faturas_txt=f"de {ctx['n_faturas']} faturas lidas",
            inv_txt=f"de {ctx['n_inversores']}",
            esp_txt=f"{ctx['esp_online']} ESP enviando agora",
        )
        if linhas:
            ctx["g_kwp"] = charts.ranking([{"nome": str(x["obj"]), "valor": x["kwp"]} for x in linhas], "kWp", 1)
        if inversores:
            ctx["g_fab"] = g_monit.rosca_fabricantes(Inversor.objects.prefetch_related("usina__inversores"))
        if sub:
            ctx["g_sub"] = charts.ranking([{"nome": k or "sem subgrupo", "valor": v} for k, v in sub.items()], "")
        if enq:
            ctx["g_enq"] = charts.rosca([{"nome": k or "não informado", "valor": v}
                                         for k, v in sorted(enq.items(), key=lambda x: -x[1])], "usinas")
        return ctx


# ---------------------------------------------------------------- integradoras

class IntegradoraListView(AdminGeralMixin, ListView):
    template_name = "plataforma/integradoras.html"

    def get_queryset(self):
        return Integradora.objects.annotate(n_usuarios=Count("usuarios", distinct=True)).order_by("razao_social")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        for i in ctx["object_list"]:
            i.n_clientes = Cliente.objects.filter(integradora=i).count()
            i.n_usinas = Usina.objects.filter(integradora=i).count()
            i.kwp = Usina.objects.filter(integradora=i).aggregate(s=Sum("potencia_kwp"))["s"] or 0
        return ctx


class IntegradoraFormMixin(AdminGeralMixin):
    model = Integradora
    form_class = IntegradoraAdminForm
    template_name = "cadastro/form.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(voltar=reverse("plataforma:integradoras"), voltar_titulo="Integradoras")
        return ctx

    def form_valid(self, form):
        novo = form.instance.pk is None
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object)
        messages.success(self.request, "Integradora salva." + (" Agora crie o usuário gestor dela." if novo else ""))
        return resp

    def get_success_url(self):
        return reverse("plataforma:usuario_novo") + f"?integradora={self.object.pk}&papel=gestor" \
            if self.request.resolver_match.url_name == "integradora_nova" else reverse("plataforma:integradoras")


class IntegradoraCreateView(IntegradoraFormMixin, CreateView):
    extra_context = {"titulo": "Nova integradora", "botao": "Cadastrar e criar o gestor"}


class IntegradoraUpdateView(IntegradoraFormMixin, UpdateView):
    extra_context = {"titulo": "Editar integradora"}


class AtuarView(AdminGeralMixin, View):
    def post(self, request, pk):
        i = get_object_or_404(Integradora, pk=pk)
        request.session[SESSAO_ATUANDO] = i.pk
        request.tenant = i
        registrar(request, LogAuditoria.Acao.ATUAR, i, f"administrador entrou como {i}")
        return redirect(request.POST.get("proximo") or "painel:visao")


class SairAtuacaoView(AdminGeralMixin, View):
    def post(self, request):
        request.session.pop(SESSAO_ATUANDO, None)
        return redirect("plataforma:visao")


# ---------------------------------------------------------------- usuários

class UsuarioListView(AdminGeralMixin, ListView):
    template_name = "accounts/usuarios.html"
    paginate_by = 100

    def get_queryset(self):
        qs = User.objects.select_related("integradora", "cliente").order_by("papel", "integradora__razao_social",
                                                                            "username")
        if self.request.GET.get("papel"):
            qs = qs.filter(papel=self.request.GET["papel"])
        return qs

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(titulo="Usuários", subtitulo="Todos os perfis: administradores gerais, integradoras e clientes.",
                   novo_url=reverse("plataforma:usuario_novo"), editar_rota="plataforma:usuario_editar",
                   mostrar_integradora=True, filtros_papel=User.Papel.choices)
        return ctx


class UsuarioFormMixin(AdminGeralMixin):
    model = User
    form_class = UsuarioForm
    template_name = "cadastro/form.html"

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["admin"] = True
        return kw

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(voltar=reverse("plataforma:usuarios"), voltar_titulo="Usuários")
        return ctx

    def form_valid(self, form):
        novo = form.instance.pk is None
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object,
                  f"usuário {self.object.username} ({self.object.papel})")
        messages.success(self.request, "Usuário salvo.")
        return resp

    def get_success_url(self):
        return reverse("plataforma:usuarios")


class UsuarioCreateView(UsuarioFormMixin, CreateView):
    extra_context = {"titulo": "Novo usuário"}

    def get_initial(self):
        return {"integradora": self.request.GET.get("integradora"), "papel": self.request.GET.get("papel", "gestor")}


class UsuarioUpdateView(UsuarioFormMixin, UpdateView):
    extra_context = {"titulo": "Editar usuário"}


# ---------------------------------------------------------------- integrações

class IntegracoesView(AdminGeralMixin, TemplateView):
    template_name = "plataforma/integracoes.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        inv = (Inversor.objects.select_related("usina__integradora", "usina__uc_geradora__cliente", "status_atual")
               .order_by("usina__integradora__razao_social", "usina__nome"))
        med = Medidor.objects.select_related("uc__integradora", "uc__cliente").order_by("uc__integradora__razao_social")
        prov = self.request.GET.get("provedor")
        if prov:
            inv = inv.filter(provedor_api=prov)
        ctx.update(inversores=inv, medidores=med, provedores=sorted({i.provedor_api for i in Inversor.objects.all()}),
                   provedor=prov)
        return ctx


class TestarConexaoView(AdminGeralMixin, View):
    def post(self, request, pk):
        inv = get_object_or_404(Inversor.objects.select_related("usina"), pk=pk)
        p = provedor_inversor(inv)
        try:
            s = p.status()
            ok, msg = True, (f"{'Online' if s.online else 'Offline'} · {s.potencia_atual_kw} kW agora · "
                             f"{s.energia_hoje_kwh} kWh hoje" + (" (dados de demonstração)" if p.demo else ""))
        except ErroIntegracao as exc:
            ok, msg = False, str(exc)
        return render(request, "plataforma/_teste.html", {"ok": ok, "msg": msg})


class InversorAdminView(AdminGeralMixin, UpdateView):
    model = Inversor
    form_class = InversorForm
    template_name = "cadastro/form.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(titulo=f"Credenciais: {self.object} ({self.object.usina})", voltar=reverse("plataforma:integracoes"),
                   voltar_titulo="Integrações")
        return ctx

    def form_valid(self, form):
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.ALTERAR, self.object, "credenciais/API do inversor")
        messages.success(self.request, "Inversor salvo.")
        return resp

    def get_success_url(self):
        return reverse("plataforma:integracoes")


class MedidorAdminView(InversorAdminView):
    model = Medidor
    form_class = MedidorForm

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["uc"] = self.object.uc
        return kw


# ---------------------------------------------------------------- logs

class LogsView(AdminGeralMixin, ListView):
    template_name = "plataforma/logs.html"
    paginate_by = 100

    def get_queryset(self):
        qs = LogAuditoria.objects.select_related("usuario", "integradora")
        if self.request.GET.get("acao"):
            qs = qs.filter(acao=self.request.GET["acao"])
        return qs

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["acoes"] = LogAuditoria.Acao.choices
        return ctx
