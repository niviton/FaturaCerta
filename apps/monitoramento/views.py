import datetime
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format
from django.views.generic import TemplateView

from apps.analise import graficos as g_analise
from apps.cadastro.models import Cliente, Inversor, UnidadeConsumidora, Usina
from apps.core.mixins import EquipeIntegradoraMixin
from apps.faturas.models import Fatura

from . import graficos, services, tasks
from .models import GeracaoDiaria
from .services import ATENCAO, ORDEM_SITUACAO

# filtros da lista de usinas: chave -> (rótulo, situações, tom do contador)
FILTROS = {
    "todas": ("Todas", None, None),
    "ok": ("Normal", {"gerando", "noite"}, "ok"),
    "abaixo": ("Abaixo do esperado", {"abaixo"}, "solar"),
    "critico": ("Parada ou sem comunicação", {"parada", "sem_comunicacao"}, "danger"),
    "atencao": ("Precisam de atenção", ATENCAO, None),  # usado pelos links da visão geral
}


def _usinas(tenant):
    return (Usina.objects.da_integradora(tenant).filter(ativa=True).select_related("uc_geradora__cliente")
            .prefetch_related("inversores__status_atual"))


def _pct(g, e):
    return None if not e else int(g / e * 100)


class VisaoGeralView(EquipeIntegradoraMixin, TemplateView):
    """Painel da integradora: o que importa primeiro (energia não compensada e usinas com problema)."""

    template_name = "painel/visao.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        t = self.request.tenant
        usinas = list(_usinas(t))
        resumos = [services.resumir_usina(u, 30) for u in usinas]
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)

        # séries diárias da carteira (30 dias) para as sparklines
        d30 = services.serie_diaria(usinas, hoje - datetime.timedelta(days=30), hoje - datetime.timedelta(days=1))
        serie_30 = [d30.get(hoje - datetime.timedelta(days=k), 0) for k in range(30, 0, -1)]
        curva = services.curva_do_dia(usinas, hoje)
        mes_kwh = GeracaoDiaria.objects.filter(inversor__usina__in=usinas, data__gte=inicio_mes).aggregate(
            s=Sum("kwh"))["s"] or Decimal(0)
        mes_esp = Decimal(0)
        dia = inicio_mes
        while dia <= hoje:
            mes_esp += sum((services.esperado_no_dia(u, dia) or Decimal(0) for u in usinas), Decimal(0))
            dia += datetime.timedelta(days=1)

        faturas = Fatura.objects.da_integradora(t)
        div_por_mes = dict(faturas.filter(status=Fatura.Status.DIVERGENTE).annotate(m=TruncMonth("mes_referencia"))
                           .values("m").annotate(n=Count("id")).values_list("m", "n"))
        meses = services.ultimos_meses(12)
        ucs = UnidadeConsumidora.objects.da_integradora(t).select_related("concessionaria", "cliente").prefetch_related(
            "usinas__inversores", "medidores")
        cart = g_analise.carteira(list(ucs))
        perdido = cart["perdido_kwh"]

        contagem = {k: sum(1 for r in resumos if (s is None or r.situacao in s)) for k, (_, s, _) in FILTROS.items()}
        ctx.update(
            n_clientes=Cliente.objects.da_integradora(t).filter(ativo=True).count(),
            n_usinas=len(usinas), kwp=sum((u.potencia_kwp or 0 for u in usinas), Decimal(0)),
            potencia=sum((r.potencia_kw for r in resumos), Decimal(0)),
            hoje_kwh=sum((r.hoje_kwh for r in resumos), Decimal(0)),
            mes_kwh=mes_kwh, mes_pct=_pct(mes_kwh, mes_esp),
            serie_30=serie_30, serie_curva=[kw for _, kw in curva][-24:],
            serie_div=[div_por_mes.get(m, 0) for m in meses],
            atencao=sorted([r for r in resumos if r.situacao in ATENCAO], key=lambda r: ORDEM_SITUACAO[r.situacao]),
            faturas_div=faturas.filter(status=Fatura.Status.DIVERGENTE).select_related("uc__cliente")
            .order_by("-mes_referencia")[:6],
            n_faturas_div=faturas.filter(status=Fatura.Status.DIVERGENTE).count(),
            perdido_kwh=perdido, perdido_rs=(perdido * cart["tarifa"]) if cart["tarifa"] else None,
            n_ucs_div=sum(1 for b in cart["ultimos"] if g_analise.partes_injecao(b)[2] > 0),
            filtros=[{"rotulo": FILTROS[k][0], "valor": k, "contador": contagem[k], "tom": FILTROS[k][2],
                      "url": reverse("monitoramento:painel") + f"?filtro={k}"}
                     for k in ("todas", "ok", "abaixo", "critico")],
            demo=any(r.demo for r in resumos),
            g_sankey=cart["sankey"], g_injetado=cart["injetado"], g_mapa=graficos.mapa_usinas(resumos),
        )
        n_div = ctx["n_ucs_div"]
        ctx.update(
            hero_sub=f"{number_format(perdido, 0, force_grouping=True)} kWh sem compensação em {n_div} "
                     f"UC{'s' if n_div != 1 else ''}. Estimativa pela tarifa de referência.",
            hero_url=reverse("faturas:lista") + "?status=divergente",
            mes_pct_txt=f"{ctx['mes_pct']}%" if ctx["mes_pct"] is not None else "",
        )
        if usinas:
            ctx["g_geracao"] = graficos.geracao_x_esperado(usinas)
            ctx["g_fab"] = graficos.rosca_fabricantes(Inversor.objects.filter(usina__in=usinas).prefetch_related(
                "usina__inversores"))
        return ctx


class PainelView(EquipeIntegradoraMixin, TemplateView):
    """Lista de usinas: todas as marcas, situação, potência agora e desempenho, com filtro por situação."""

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
        resumos = []
        for u in _usinas(self.request.tenant):
            r = services.resumir_usina(u, 30)
            gerado = sum((g for _, g, _ in r.ultimos_dias), Decimal(0))
            esperado = sum((e or 0 for _, _, e in r.ultimos_dias), Decimal(0))
            r.pct_30 = _pct(gerado, esperado)
            r.serie_14 = [g for _, g, _ in r.ultimos_dias[-14:]]
            resumos.append(r)

        filtro = self.request.GET.get("filtro", "todas")
        if filtro not in FILTROS:
            filtro = "todas"
        situacoes = FILTROS[filtro][1]
        q = self.request.GET.get("q", "").strip().lower()
        visiveis = [r for r in resumos if situacoes is None or r.situacao in situacoes]
        if q:
            visiveis = [r for r in visiveis if q in r.usina.nome.lower() or q in str(r.usina.cliente).lower()
                        or any(q in m.lower() for m in r.marcas)]
        visiveis.sort(key=lambda r: (ORDEM_SITUACAO[r.situacao], str(r.usina.cliente), r.usina.nome))

        contagem = {k: sum(1 for r in resumos if (s is None or r.situacao in s)) for k, (_, s, _) in FILTROS.items()}
        ctx.update(
            linhas=visiveis, filtro=filtro, q=self.request.GET.get("q", ""), total=len(resumos),
            filtros=[{"rotulo": FILTROS[k][0], "valor": k, "contador": contagem[k], "tom": FILTROS[k][2]}
                     for k in ("todas", "ok", "abaixo", "critico")],
            potencia=sum((r.potencia_kw for r in resumos), Decimal(0)),
            energia_hoje=sum((r.hoje_kwh for r in resumos), Decimal(0)),
            kwp=sum((r.usina.potencia_kwp or 0 for r in resumos), Decimal(0)),
            demo=any(r.demo for r in resumos),
            marcas=sorted({m for r in resumos for m in r.marcas}),
            n_clientes=len({r.usina.uc_geradora.cliente_id for r in resumos}),
        )
        ctx["kwp_txt"] = f"de {number_format(ctx['kwp'], 1, force_grouping=True)} kWp instalados"
        return ctx
