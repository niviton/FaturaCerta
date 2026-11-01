from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.audit import ip_do_request, registrar
from apps.core.mixins import (
    AuditarVisualizacaoMixin,
    EquipeIntegradoraMixin,
    TenantFormMixin,
    TenantQuerysetMixin,
)
from apps.core.models import LogAuditoria
from apps.monitoramento.services import resumir_usina

from .forms import (
    MESES,
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
from .models import Cliente, ConsentimentoLGPD, Inversor, Medidor, UnidadeConsumidora, Usina
from .requisitos import pendencias_cadastro_uc, status_regras

FORM_TEMPLATE = "cadastro/form.html"


# ---------- clientes ----------

class ClienteListView(TenantQuerysetMixin, ListView):
    model = Cliente
    template_name = "cadastro/clientes.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().annotate(n_ucs=Count("ucs", distinct=True))
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(nome__icontains=q) | Q(documento__icontains=q) | Q(ucs__numero_uc__icontains=q))
        return qs.distinct().order_by("nome")


class ClienteFormMixin(TenantFormMixin):
    model = Cliente
    form_class = ClienteForm
    template_name = FORM_TEMPLATE

    def get_success_url(self):
        return reverse("cadastro:cliente", args=[self.object.pk])


class ClienteCreateView(ClienteFormMixin, CreateView):
    extra_context = {"titulo": "Novo cliente"}


class ClienteUpdateView(ClienteFormMixin, UpdateView):
    extra_context = {"titulo": "Editar cliente"}


class ClienteDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    model = Cliente
    template_name = "cadastro/cliente.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["ucs"] = self.object.ucs.select_related("concessionaria")
        usinas = (Usina.objects.filter(uc_geradora__cliente=self.object).select_related("uc_geradora")
                  .prefetch_related("inversores__status_atual"))
        ctx["resumos"] = [resumir_usina(u) for u in usinas]
        ctx["form_consentimento"] = ConsentimentoForm()
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
        return redirect("cadastro:cliente", pk=pk)


# ---------- unidades consumidoras ----------

class UCFormMixin(TenantFormMixin):
    model = UnidadeConsumidora
    form_class = UCForm
    template_name = FORM_TEMPLATE

    def get_success_url(self):
        return reverse("cadastro:uc", args=[self.object.pk])


class UCCreateView(UCFormMixin, CreateView):
    extra_context = {"titulo": "Nova unidade consumidora"}

    def get_initial(self):
        return {"cliente": self.request.GET.get("cliente")}


class UCUpdateView(UCFormMixin, UpdateView):
    extra_context = {"titulo": "Editar unidade consumidora"}


class UCDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    model = UnidadeConsumidora
    template_name = "cadastro/uc.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["regras"] = status_regras(self.object)
        ctx["pendencias"] = pendencias_cadastro_uc(self.object)
        ctx["lotes"] = self.object.lotes_credito.all()
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
        return redirect("cadastro:uc", pk=pk)


# ---------- usinas ----------

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
    extra_context = {"titulo": "Nova usina"}

    def get_initial(self):
        return {"uc_geradora": self.request.GET.get("uc")}


class UsinaUpdateView(UsinaFormMixin, UpdateView):
    extra_context = {"titulo": "Editar usina"}


class UsinaDetailView(TenantQuerysetMixin, AuditarVisualizacaoMixin, DetailView):
    model = Usina
    template_name = "cadastro/usina.html"

    def get_queryset(self):
        return super().get_queryset().select_related("uc_geradora__cliente").prefetch_related("inversores__status_atual")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["rateios"] = self.object.rateios.select_related("uc")
        ctx["inversores"] = self.object.inversores.all()
        ctx["medidor"] = getattr(self.object, "medidor", None)
        ctx["esperada"] = list(zip(MESES, self.object.geracao_esperada_kwh, strict=False))
        ctx["resumo"] = resumir_usina(self.object, dias_grafico=30)
        return ctx


class EquipamentoMixin(EquipeIntegradoraMixin):
    """Inversor e medidor pertencem à usina; o tenant vem por ela."""

    template_name = FORM_TEMPLATE

    def get_usina(self):
        return get_object_or_404(Usina.objects.da_integradora(self.request.tenant), pk=self.kwargs["usina_pk"])

    def get_queryset(self):
        return self.model.objects.filter(usina__integradora=self.request.tenant, usina_id=self.kwargs["usina_pk"])

    def get_form_kwargs(self):
        self.usina = self.get_usina()  # 404 se a usina for de outra integradora
        return super().get_form_kwargs()

    def form_valid(self, form):
        novo = form.instance.pk is None
        form.instance.usina = self.usina
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.CRIAR if novo else LogAuditoria.Acao.ALTERAR, self.object)
        return resp

    def get_success_url(self):
        return reverse("cadastro:usina", args=[self.kwargs["usina_pk"]])


class InversorCreateView(EquipamentoMixin, CreateView):
    model = Inversor
    form_class = InversorForm
    extra_context = {"titulo": "Vincular inversor"}


class InversorUpdateView(EquipamentoMixin, UpdateView):
    model = Inversor
    form_class = InversorForm
    extra_context = {"titulo": "Editar inversor"}


class MedidorCreateView(EquipamentoMixin, CreateView):
    model = Medidor
    form_class = MedidorForm
    extra_context = {"titulo": "Vincular medidor próprio"}

    def dispatch(self, request, *args, **kwargs):
        usina = Usina.objects.filter(pk=kwargs["usina_pk"], integradora=getattr(request, "tenant", None)).first()
        if usina is not None and hasattr(usina, "medidor"):
            return redirect("cadastro:medidor_editar", usina_pk=usina.pk, pk=usina.medidor.pk)
        return super().dispatch(request, *args, **kwargs)


class MedidorUpdateView(EquipamentoMixin, UpdateView):
    model = Medidor
    form_class = MedidorForm
    extra_context = {"titulo": "Editar medidor próprio"}


# ---------- integradora ----------

class IntegradoraUpdateView(EquipeIntegradoraMixin, UpdateView):
    apenas_gestor = True
    form_class = IntegradoraForm
    template_name = FORM_TEMPLATE
    extra_context = {"titulo": "Dados da integradora"}

    def get_object(self, queryset=None):
        return self.request.tenant

    def form_valid(self, form):
        resp = super().form_valid(form)
        registrar(self.request, LogAuditoria.Acao.ALTERAR, self.object)
        messages.success(self.request, "Dados da integradora salvos.")
        return resp

    def get_success_url(self):
        return reverse("cadastro:integradora")
