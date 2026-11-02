from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Prefetch, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from apps.accounts.forms import AcessoPortalForm
from apps.accounts.models import User
from apps.analise import graficos as g_analise
from apps.analise.services import balancos_uc, fontes_disponiveis
from apps.core.audit import ip_do_request, registrar
from apps.core.mixins import (
    AuditarVisualizacaoMixin,
    EquipeIntegradoraMixin,
    TenantFormMixin,
    TenantQuerysetMixin,
)
from apps.core.models import LogAuditoria
from apps.faturas.models import Fatura
from apps.monitoramento import graficos as g_monit
from apps.monitoramento.services import ORDEM_SITUACAO, resumir_usina

from .forms import (
    ArranjoForm,
    ClienteForm,
    ConsentimentoForm,
    IntegradoraForm,
    InversorForm,
    LoteCreditoForm,
    MedidorForm,
    RateioFormSet,
    UCForm,
    UsinaForm,
)
from .models import ArranjoModulos, Cliente, ConsentimentoLGPD, Inversor, Medidor, UnidadeConsumidora, Usina
from .requisitos import pendencias_cadastro_uc, status_regras

FORM_TEMPLATE = "cadastro/form.html"


def usinas_com_status(qs):
    return qs.select_related("uc_geradora__cliente").prefetch_related("inversores__status_atual")


# ================================================================ clientes

class ClienteListView(TenantQuerysetMixin, ListView):
    model = Cliente
    template_name = "cadastro/clientes.html"
    paginate_by = 50

    def get_queryset(self):
        qs = (super().get_queryset()
              .annotate(n_ucs=Count("ucs", distinct=True), n_usinas=Count("ucs__usinas", distinct=True),
                        kwp=Sum("ucs__usinas__potencia_kwp"))
              .prefetch_related("consentimentos", Prefetch("ucs", queryset=UnidadeConsumidora.objects.only(
                  "id", "cliente_id", "grupo", "subgrupo", "numero_uc"))))
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(documento__icontains=q) | Q(ucs__numero_uc__icontains=q)
                           | Q(nome_fantasia__icontains=q))
        seg = self.request.GET.get("segmento")
        if seg:
            qs = qs.filter(segmento=seg)
        return qs.distinct().order_by("nome")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["segmentos"] = Cliente.Segmento.choices
        ctx["usinas_por_cliente"] = {}
        usinas = usinas_com_status(Usina.objects.da_integradora(self.request.tenant).filter(
            uc_geradora__cliente__in=list(ctx["object_list"])))
        for u in usinas:
            ctx["usinas_por_cliente"].setdefault(u.uc_geradora.cliente_id, []).append(resumir_usina(u, 7))
        for c in ctx["object_list"]:
            c.resumos = sorted(ctx["usinas_por_cliente"].get(c.pk, []), key=lambda r: ORDEM_SITUACAO[r.situacao])
            c.marcas = sorted({m for r in c.resumos for m in r.marcas})
        return ctx


class ClienteFormMixin(TenantFormMixin):
    model = Cliente
    form_class = ClienteForm
    template_name = FORM_TEMPLATE

    def get_success_url(self):
        return reverse("cadastro:cliente", args=[self.object.pk])


class ClienteCreateView(ClienteFormMixin, CreateView):
    extra_context = {"titulo": "Novo cliente", "botao": "Cadastrar e continuar",
                     "subtitulo": "Depois do titular, você cadastra as unidades consumidoras, as usinas e os "
                                  "equipamentos na ficha do cliente."}


class ClienteUpdateView(ClienteFormMixin, UpdateView):
    extra_context = {"titulo": "Editar cliente"}


def passos_cadastro(cliente, ucs, usinas, medidores, n_faturas, n_acessos):
    inversores = [i for u in usinas for i in u.inversores.all()]
    return [
        ("Titular completo", "CPF/CNPJ, segmento e contato", bool(cliente.documento and cliente.contato_nome
                                                                   and (cliente.email or cliente.telefone))),
        ("Consentimento LGPD", "Autoriza receber e processar as faturas", cliente.consentimento_vigente is not None),
        ("Unidade consumidora", "Número da UC, código do cliente e perfil tarifário",
         any(uc.codigo_cliente and uc.subgrupo for uc in ucs)),
        ("Usina com data do protocolo", "Define GD1/GD2 e a regra do Fio B", any(u.data_protocolo for u in usinas)),
        ("Inversor com API do fabricante", "Fonte 1: geração", any(i.credenciais_configuradas for i in inversores)),
        ("Medidor próprio (ESP)", "Fonte 2: o que entra e sai da rede", bool(medidores)),
        ("12 faturas no histórico", "Fonte 3 e linha de base da economia", n_faturas >= 12),
        ("Acesso ao portal", "O cliente acompanha as usinas e a economia", n_acessos > 0),
    ]


class ClienteDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    """Ficha do cliente: tudo o que a auditoria precisa, em abas."""

    model = Cliente
    template_name = "cadastro/cliente.html"
    ABAS = [("resumo", "Resumo"), ("ucs", "Unidades consumidoras"), ("usinas", "Usinas"),
            ("equipamentos", "Equipamentos"), ("faturas", "Faturas"), ("acesso", "Acesso e LGPD")]

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        c = self.object
        aba = self.request.GET.get("aba", "resumo")
        ucs = list(c.ucs.select_related("concessionaria").prefetch_related("usinas__inversores", "medidores"))
        usinas = list(usinas_com_status(Usina.objects.filter(uc_geradora__cliente=c)).prefetch_related("arranjos"))
        medidores = list(Medidor.objects.filter(uc__cliente=c).select_related("uc", "usina"))
        faturas = Fatura.objects.filter(uc__cliente=c).select_related("uc")
        acessos = list(User.objects.filter(cliente=c))
        resumos = [resumir_usina(u) for u in usinas]
        passos = passos_cadastro(c, ucs, usinas, medidores, faturas.count(), len(acessos))
        ctx.update(
            aba=aba, abas=self.ABAS, ucs=ucs, usinas=usinas, resumos=resumos, medidores=medidores,
            acessos=acessos, passos=passos, pct_cadastro=int(sum(p[2] for p in passos) / len(passos) * 100),
            n_faturas=faturas.count(), kwp=sum(u.potencia_kwp or 0 for u in usinas),
            marcas=sorted({m for r in resumos for m in r.marcas}),
            atencao=[r for r in resumos if r.precisa_atencao],
        )
        if aba == "resumo" and usinas:
            ctx["g_diario"] = g_monit.geracao_diaria(usinas, 30)
            ctx["g_mensal"] = g_monit.geracao_mensal(usinas)
            ctx["g_curva"] = g_monit.curva_hoje(usinas)
        if aba == "resumo" and ucs:
            uc_sel = next((u for u in ucs if str(u.pk) == self.request.GET.get("uc")), ucs[0])
            bal = balancos_uc(uc_sel)
            ctx.update(uc_sel=uc_sel, g_balanco=g_analise.balanco_energetico(bal),
                       g_inj=g_analise.injetado_compensado(bal), indicios_recentes=bal[-1].indicios if bal else [])
        if aba == "faturas":
            ctx["faturas"] = faturas[:60]
        if aba == "acesso":
            ctx["form_consentimento"] = ConsentimentoForm()
            ctx["form_acesso"] = AcessoPortalForm(initial={"email": c.email})
            ctx["consentimentos"] = c.consentimentos.all()
        return ctx


class ConsentimentoView(EquipeIntegradoraMixin, View):
    def post(self, request, pk):
        cliente = get_object_or_404(Cliente.objects.da_integradora(request.tenant), pk=pk)
        form = ConsentimentoForm(request.POST)
        if form.is_valid():
            c = ConsentimentoLGPD.objects.create(
                cliente=cliente, data=timezone.now(), versao_termo=form.cleaned_data["versao_termo"],
                ip=ip_do_request(request), registrado_por=request.user,
            )
            registrar(request, LogAuditoria.Acao.CRIAR, c, f"consentimento LGPD de {cliente}")
            messages.success(request, "Consentimento registrado.")
        else:
            messages.error(request, "Marque o aceite do termo para registrar o consentimento.")
        return redirect(reverse("cadastro:cliente", args=[pk]) + "?aba=acesso")


class AcessoPortalView(EquipeIntegradoraMixin, View):
    def post(self, request, pk):
        cliente = get_object_or_404(Cliente.objects.da_integradora(request.tenant), pk=pk)
        form = AcessoPortalForm(request.POST)
        if form.is_valid():
            u = User.objects.create_user(
                username=form.cleaned_data["username"], email=form.cleaned_data["email"],
                password=form.cleaned_data["senha"], papel=User.Papel.CLIENTE, integradora=request.tenant,
                cliente=cliente, first_name=str(cliente)[:150])
            registrar(request, LogAuditoria.Acao.CRIAR, u, f"acesso ao portal para {cliente}")
            messages.success(request, f"Acesso criado. O cliente entra com o usuário {u.username}.")
        else:
            messages.error(request, "Não foi possível criar o acesso: " + "; ".join(
                e for erros in form.errors.values() for e in erros))
        return redirect(reverse("cadastro:cliente", args=[pk]) + "?aba=acesso")


# ================================================================ unidades consumidoras

class UCFormMixin(TenantFormMixin):
    model = UnidadeConsumidora
    form_class = UCForm
    template_name = FORM_TEMPLATE

    def get_success_url(self):
        return reverse("cadastro:uc", args=[self.object.pk])


class UCCreateView(UCFormMixin, CreateView):
    extra_context = {"titulo": "Nova unidade consumidora",
                     "subtitulo": "Copie os dados da fatura de energia. O perfil tarifário define as regras da auditoria."}

    def get_initial(self):
        cliente = Cliente.objects.da_integradora(self.request.tenant).filter(pk=self.request.GET.get("cliente")).first()
        ini = {"cliente": cliente}
        if cliente:
            ini.update({k: getattr(cliente, k) for k in ("cep", "logradouro", "numero", "bairro", "municipio", "uf")})
        return ini


class UCUpdateView(UCFormMixin, UpdateView):
    extra_context = {"titulo": "Editar unidade consumidora"}


class UCDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    """Análise da conta: as três fontes lado a lado, por janela de leitura."""

    model = UnidadeConsumidora
    template_name = "cadastro/uc.html"
    ABAS = [("analise", "Análise da conta"), ("faturas", "Faturas"), ("perfil", "Perfil e regras"),
            ("creditos", "Créditos")]

    def get_queryset(self):
        return super().get_queryset().select_related("cliente", "concessionaria").prefetch_related(
            "usinas__inversores", "medidores")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        uc = self.object
        aba = self.request.GET.get("aba", "analise")
        ctx.update(aba=aba, abas=self.ABAS, fontes=fontes_disponiveis(uc), pendencias=pendencias_cadastro_uc(uc),
                   medidores=list(uc.medidores.all()), usinas=list(uc.usinas.all()))
        if aba == "analise":
            bal = balancos_uc(uc)
            sel = None
            if self.request.GET.get("fatura"):
                sel = next((b for b in bal if b.fatura and str(b.fatura.pk) == self.request.GET["fatura"]), None)
            sel = sel or (bal[-1] if bal else None)
            ctx.update(balancos=bal, sel=sel, g_balanco=g_analise.balanco_energetico(bal),
                       g_inj=g_analise.injetado_compensado(bal), g_consumo=g_analise.consumo_tres_fontes(bal),
                       g_custo=g_analise.custo(bal))
        elif aba == "faturas":
            ctx["faturas"] = uc.faturas.all()
        elif aba == "perfil":
            ctx["regras"] = status_regras(uc)
        elif aba == "creditos":
            ctx["lotes"] = uc.lotes_credito.all()
            ctx["form_lote"] = LoteCreditoForm()
        return ctx


class LoteCreditoCreateView(EquipeIntegradoraMixin, View):
    def post(self, request, pk):
        uc = get_object_or_404(UnidadeConsumidora.objects.da_integradora(request.tenant), pk=pk)
        form = LoteCreditoForm(request.POST)
        if form.is_valid():
            form.instance.uc = uc
            lote = form.save()
            registrar(request, LogAuditoria.Acao.CRIAR, lote)
            messages.success(request, "Lote de créditos adicionado.")
        else:
            messages.error(request, "Revise os dados do lote: " + "; ".join(
                e for erros in form.errors.values() for e in erros))
        return redirect(reverse("cadastro:uc", args=[pk]) + "?aba=creditos")


# ================================================================ usinas

class UsinaFormMixin(TenantFormMixin):
    model = Usina
    form_class = UsinaForm
    template_name = "cadastro/usina_form.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        if "rateios" not in kw:
            ctx["rateios"] = RateioFormSet(instance=self.object or Usina(), integradora=self.request.tenant)
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object() if "pk" in kwargs else None
        form = self.get_form()
        rateios = RateioFormSet(request.POST, instance=self.object or Usina(), integradora=request.tenant)
        if form.is_valid() and rateios.is_valid():
            with transaction.atomic():
                resp = self.form_valid(form)
                rateios.instance = self.object
                rateios.save()
            return resp
        return self.render_to_response(self.get_context_data(form=form, rateios=rateios))

    def get_success_url(self):
        return reverse("cadastro:usina", args=[self.object.pk])


class UsinaCreateView(UsinaFormMixin, CreateView):
    extra_context = {"titulo": "Nova usina",
                     "subtitulo": "Depois de salvar, cadastre os módulos e vincule o inversor para começar a monitorar."}

    def _cliente(self):
        return Cliente.objects.da_integradora(self.request.tenant).filter(pk=self.request.GET.get("cliente")).first()

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["cliente"] = self._cliente()
        return kw

    def get_initial(self):
        uc = self.request.GET.get("uc")
        if not uc and self._cliente():
            primeira = self._cliente().ucs.first()
            uc = primeira.pk if primeira else None
        return {"uc_geradora": uc}


class UsinaUpdateView(UsinaFormMixin, UpdateView):
    extra_context = {"titulo": "Editar usina"}


class UsinaDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    model = Usina
    template_name = "cadastro/usina.html"

    def get_queryset(self):
        return super().get_queryset().select_related("uc_geradora__cliente").prefetch_related(
            "inversores__status_atual", "arranjos", "rateios__uc")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        u = self.object
        r = resumir_usina(u, dias_grafico=30)
        mensal = g_monit.geracao_mensal([u])
        ctx.update(
            resumo=r, inversores=list(u.inversores.all()), arranjos=list(u.arranjos.all()),
            rateios=list(u.rateios.all()), medidores=list(u.medidores.all()),
            g_curva=g_monit.curva_hoje([u]), g_diario=g_monit.geracao_diaria([u], 30), g_mensal=mensal,
            total_12m=sum(v for v in mensal["series"][0]["valores"] if v),
            esperado_12m=sum(v for v in (mensal["series"][1]["valores"] if len(mensal["series"]) > 1 else []) if v),
            form_arranjo=ArranjoForm(),
        )
        return ctx


class ArranjoCreateView(EquipeIntegradoraMixin, View):
    def post(self, request, usina_pk):
        usina = get_object_or_404(Usina.objects.da_integradora(request.tenant), pk=usina_pk)
        form = ArranjoForm(request.POST)
        if form.is_valid():
            form.instance.usina = usina
            form.save()
            usina.recalcular_potencia()
            messages.success(request, "Arranjo adicionado. A potência da usina foi recalculada.")
        else:
            messages.error(request, "Revise o arranjo: " + "; ".join(e for es in form.errors.values() for e in es))
        return redirect("cadastro:usina", pk=usina.pk)


class ArranjoDeleteView(EquipeIntegradoraMixin, View):
    def post(self, request, usina_pk, pk):
        a = get_object_or_404(ArranjoModulos, pk=pk, usina_id=usina_pk, usina__integradora=request.tenant)
        usina = a.usina
        a.delete()
        usina.recalcular_potencia()
        return redirect("cadastro:usina", pk=usina_pk)


class InversorMixin(EquipeIntegradoraMixin):
    model = Inversor
    form_class = InversorForm
    template_name = FORM_TEMPLATE

    def get_usina(self):
        return get_object_or_404(Usina.objects.da_integradora(self.request.tenant), pk=self.kwargs["usina_pk"])

    def get_queryset(self):
        return Inversor.objects.filter(usina__integradora=self.request.tenant, usina_id=self.kwargs["usina_pk"])

    def get_form_kwargs(self):
        self.usina = self.get_usina()  # 404 se a usina for de outra integradora
        return super().get_form_kwargs()

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(voltar=reverse("cadastro:usina", args=[self.usina.pk]), voltar_titulo=self.usina.nome)
        return ctx

    def form_valid(self, form):
        novo = form.instance.pk is None
        form.instance.usina = self.usina
        resp = super().form_valid(form)
        self.usina.recalcular_potencia()
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object)
        messages.success(self.request, "Inversor salvo.")
        return resp

    def get_success_url(self):
        return reverse("cadastro:usina", args=[self.kwargs["usina_pk"]])


class InversorCreateView(InversorMixin, CreateView):
    extra_context = {"titulo": "Vincular inversor"}


class InversorUpdateView(InversorMixin, UpdateView):
    extra_context = {"titulo": "Editar inversor"}


class MedidorMixin(EquipeIntegradoraMixin):
    model = Medidor
    form_class = MedidorForm
    template_name = FORM_TEMPLATE

    def get_uc(self):
        return get_object_or_404(UnidadeConsumidora.objects.da_integradora(self.request.tenant), pk=self.kwargs["uc_pk"])

    def get_queryset(self):
        return Medidor.objects.filter(uc__integradora=self.request.tenant, uc_id=self.kwargs["uc_pk"])

    def get_form_kwargs(self):
        self.uc = self.get_uc()
        kw = super().get_form_kwargs()
        kw["uc"] = self.uc
        return kw

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx.update(voltar=reverse("cadastro:uc", args=[self.uc.pk]), voltar_titulo=str(self.uc),
                   subtitulo="Fonte 2 da auditoria. Com ele dá para provar quanto entrou e saiu da rede.")
        return ctx

    def form_valid(self, form):
        novo = form.instance.pk is None
        form.instance.uc = self.uc
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object)
        if self.object.provedor_api == "esp" and not self.object.token_hash:
            return redirect("cadastro:medidor_token", uc_pk=self.uc.pk, pk=self.object.pk)
        messages.success(self.request, "Medidor salvo.")
        return resp

    def get_success_url(self):
        return reverse("cadastro:uc", args=[self.kwargs["uc_pk"]])


class MedidorCreateView(MedidorMixin, CreateView):
    extra_context = {"titulo": "Novo medidor próprio"}


class MedidorUpdateView(MedidorMixin, UpdateView):
    extra_context = {"titulo": "Editar medidor próprio"}


class MedidorTokenView(EquipeIntegradoraMixin, TemplateView):
    """Gera (ou regenera) o token do ESP e mostra uma única vez, com as instruções de envio."""

    template_name = "cadastro/medidor_token.html"

    def _medidor(self):
        return get_object_or_404(Medidor, pk=self.kwargs["pk"], uc_id=self.kwargs["uc_pk"],
                                 uc__integradora=self.request.tenant)

    def get(self, request, *args, **kwargs):
        m = self._medidor()
        if m.token_hash:
            return self.render_to_response({"medidor": m, "token": None})
        return self._gerar(m)

    def post(self, request, *args, **kwargs):
        return self._gerar(self._medidor())

    def _gerar(self, m):
        token = m.gerar_token()
        registrar(self.request, LogAuditoria.Acao.ALTERAR, m, "token do dispositivo gerado")
        url = self.request.build_absolute_uri(reverse("api_medicoes"))
        return self.render_to_response({"medidor": m, "token": token, "url_api": url})


# ================================================================ integradora

class IntegradoraUpdateView(EquipeIntegradoraMixin, UpdateView):
    apenas_gestor = True
    form_class = IntegradoraForm
    template_name = FORM_TEMPLATE
    extra_context = {"titulo": "Configurações da integradora"}

    def get_object(self, queryset=None):
        return self.request.tenant

    def form_valid(self, form):
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.ALTERAR, self.object)
        messages.success(self.request, "Dados da integradora salvos.")
        return resp

    def get_success_url(self):
        return reverse("cadastro:integradora")
