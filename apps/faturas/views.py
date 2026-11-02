from django.db.models import Q
from django.urls import reverse
from django.views.generic import CreateView, ListView, UpdateView

from apps.cadastro.models import UnidadeConsumidora
from apps.core.mixins import TenantFormMixin, TenantQuerysetMixin

from .forms import FaturaForm
from .models import Fatura


class FaturaListView(TenantQuerysetMixin, ListView):
    model = Fatura
    template_name = "faturas/lista.html"
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset().select_related("uc__cliente")
        st = self.request.GET.get("status")
        if st:
            qs = qs.filter(status=st)
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(Q(uc__numero_uc__icontains=q) | Q(uc__cliente__nome__icontains=q))
        return qs.order_by("-mes_referencia", "uc__cliente__nome")

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        base = Fatura.objects.da_integradora(self.request.tenant)
        ctx["contagem"] = {s: base.filter(status=s).count() for s, _ in Fatura.Status.choices}
        ctx["total"] = base.count()
        ctx["status_choices"] = Fatura.Status.choices
        return ctx


class FaturaFormMixin(TenantFormMixin):
    model = Fatura
    form_class = FaturaForm
    template_name = "cadastro/form.html"

    def get_success_url(self):
        return reverse("cadastro:uc", args=[self.object.uc_id]) + f"?aba=analise&fatura={self.object.pk}"


class FaturaCreateView(FaturaFormMixin, CreateView):
    extra_context = {"titulo": "Lançar fatura", "subtitulo": "Copie os campos da conta de energia. A leitura "
                     "automática do PDF entra na próxima etapa e preenche estes mesmos campos."}

    def get_initial(self):
        uc = UnidadeConsumidora.objects.da_integradora(self.request.tenant).filter(pk=self.request.GET.get("uc")).first()
        ini = {"uc": uc}
        if uc:
            ini.update(constante_medidor=uc.constante_medidor or 1, custo_disponibilidade_kwh=uc.custo_disponibilidade_kwh,
                       demanda_contratada_kw=uc.demanda_contratada_kw)
        return ini

    def form_valid(self, form):
        form.instance.origem = Fatura.Origem.MANUAL
        return super().form_valid(form)


class FaturaUpdateView(FaturaFormMixin, UpdateView):
    extra_context = {"titulo": "Editar fatura"}
