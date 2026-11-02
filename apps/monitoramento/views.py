import datetime
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone
from django.views.generic import TemplateView

from apps.cadastro.models import Cliente, Inversor, Medidor, Usina
from apps.core.mixins import EquipeIntegradoraMixin
from apps.faturas.models import Fatura

from . import graficos, services, tasks
from .models import GeracaoDiaria
from .services import ATENCAO, ORDEM_SITUACAO

FILTROS = OrderedDict([("todas", "Todas"), ("atencao", "Precisam de atenção"), ("gerando", "Gerando")])


def _usinas(tenant):
    return (Usina.objects.da_integradora(tenant).filter(ativa=True).select_related("uc_geradora__cliente")
            .prefetch_related("inversores__status_atual"))


class VisaoGeralView(EquipeIntegradoraMixin, TemplateView):
    """Painel da integradora: carteira inteira em números e gráficos."""

    template_name = "painel/visao.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        t = self.request.tenant
        usinas = list(_usinas(t))
        resumos = [services.resumir_usina(u, 7) for u in usinas]
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        mes_kwh = GeracaoDiaria.objects.filter(inversor__usina__in=usinas, data__gte=inicio_mes).aggregate(
            s=Sum("kwh"))["s"] or Decimal(0)
        mes_esp = Decimal(0)
        dia = inicio_mes
        while dia <= hoje:
            mes_esp += sum((services.esperado_no_dia(u, dia) or Decimal(0) for u in usinas), Decimal(0))
            dia += datetime.timedelta(days=1)
        faturas = Fatura.objects.da_integradora(t)
        ultimo_mes = faturas.order_by("-mes_referencia").values_list("mes_referencia", flat=True).first()
        ctx.update(
            n_clientes=Cliente.objects.da_integradora(t).filter(ativo=True).count(),
            n_usinas=len(usinas),
            kwp=sum((u.potencia_kwp or 0 for u in usinas), Decimal(0)),
            potencia=sum((r.potencia_kw for r in resumos), Decimal(0)),
            hoje_kwh=sum((r.hoje_kwh for r in resumos), Decimal(0)),
            mes_kwh=mes_kwh, mes_pct=int(mes_kwh / mes_esp * 100) if mes_esp else None,
            atencao=sorted([r for r in resumos if r.situacao in ATENCAO], key=lambda r: ORDEM_SITUACAO[r.situacao]),
            gerando=sum(r.situacao == "gerando" for r in resumos),
            faturas_div=faturas.filter(status=Fatura.Status.DIVERGENTE).select_related("uc__cliente")[:8],
            n_faturas_div=faturas.filter(status=Fatura.Status.DIVERGENTE).count(),
            n_faturas_mes=faturas.filter(mes_referencia=ultimo_mes).count() if ultimo_mes else 0,
            ultimo_mes=ultimo_mes,
            n_medidores=Medidor.objects.filter(uc__integradora=t).count(),
            demo=any(r.demo for r in resumos),
        )
        if usinas:
            ctx["g_diario"] = graficos.geracao_diaria(usinas, 30, por_usina=False)
            ctx["g_mensal"] = graficos.geracao_mensal(usinas)
            ctx["g_curva"] = graficos.curva_hoje(usinas)
            ctx["g_desemp"] = graficos.desempenho_usinas(resumos)
            ctx["g_fab"] = graficos.por_fabricante(Inversor.objects.filter(usina__in=usinas).prefetch_related(
                "usina__inversores"))
        return ctx


class PainelView(EquipeIntegradoraMixin, TemplateView):
    """Todas as usinas da integradora, agrupadas por cliente, de qualquer fabricante."""

    template_name = "monitoramento/painel.html"

    def post(self, request, *args, **kwargs):
        tasks.coletar_status_todos(integradora_id=request.tenant.pk)
        return self.get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.headers.get("HX-Request"):
            return ["monitoramento/_lista.html"]
        return [self.template_name]

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        resumos = [services.resumir_usina(u) for u in _usinas(self.request.tenant)]

        filtro = self.request.GET.get("filtro", "todas")
        q = self.request.GET.get("q", "").strip().lower()
        visiveis = resumos
        if filtro == "atencao":
            visiveis = [r for r in resumos if r.situacao in ATENCAO]
        elif filtro == "gerando":
            visiveis = [r for r in resumos if r.situacao == "gerando"]
        if q:
            visiveis = [r for r in visiveis if q in r.usina.nome.lower() or q in str(r.usina.cliente).lower()
                        or any(q in m.lower() for m in r.marcas)]

        grupos = OrderedDict()
        for r in sorted(visiveis, key=lambda r: (str(r.usina.cliente), ORDEM_SITUACAO[r.situacao], r.usina.nome)):
            grupos.setdefault(r.usina.cliente, []).append(r)

        ctx.update(
            grupos=grupos, filtros=FILTROS, filtro=filtro, q=self.request.GET.get("q", ""), total=len(resumos),
            gerando=sum(r.situacao == "gerando" for r in resumos),
            atencao=sum(r.situacao in ATENCAO for r in resumos),
            paradas=sum(r.situacao in ("parada", "sem_comunicacao") for r in resumos),
            potencia=sum((r.potencia_kw for r in resumos), Decimal(0)),
            energia_hoje=sum((r.hoje_kwh for r in resumos), Decimal(0)),
            kwp=sum((r.usina.potencia_kwp or 0 for r in resumos), Decimal(0)),
            demo=any(r.demo for r in resumos),
            marcas=sorted({m for r in resumos for m in r.marcas}),
        )
        return ctx
