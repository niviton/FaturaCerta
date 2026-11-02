"""Portal do cliente final: só leitura, só os dados do próprio cliente, com a marca da integradora."""

from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.formats import number_format
from django.views.generic import TemplateView

from apps.analise import graficos as g_analise
from apps.analise.services import balancos_uc
from apps.cadastro.models import Usina
from apps.core import charts
from apps.core.mixins import ClienteFinalMixin
from apps.monitoramento import graficos as g_monit
from apps.monitoramento.models import GeracaoDiaria
from apps.monitoramento.services import resumir_usina


def _usinas_do_cliente(user):
    return (Usina.objects.filter(uc_geradora__cliente=user.cliente, ativa=True)
            .select_related("uc_geradora").prefetch_related("inversores__status_atual"))


def _nav(ativo):
    return [{"titulo": "Início", "url": "#inicio", "icone": "house", "ativo": ativo == "inicio"},
            {"titulo": "Usinas", "url": "#usinas", "icone": "sun", "ativo": ativo == "usinas"},
            {"titulo": "Conta", "url": "#conta", "icone": "receipt", "ativo": ativo == "conta"},
            {"titulo": "Ajuda", "url": "#ajuda", "icone": "info", "ativo": ativo == "ajuda"}]


class InicioView(ClienteFinalMixin, TemplateView):
    template_name = "portal/inicio.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        cliente = self.request.user.cliente
        usinas = list(_usinas_do_cliente(self.request.user))
        resumos = [resumir_usina(u) for u in usinas]
        hoje = timezone.localdate()
        mes = GeracaoDiaria.objects.filter(inversor__usina__in=usinas, data__gte=hoje.replace(day=1))
        ctx.update(cliente=cliente, resumos=resumos, nav=_nav("inicio"),
                   hoje_kwh=sum((r.hoje_kwh for r in resumos), Decimal(0)),
                   potencia=sum((r.potencia_kw for r in resumos), Decimal(0)),
                   mes_kwh=sum((g.kwh for g in mes), Decimal(0)),
                   tudo_ok=all(not r.precisa_atencao for r in resumos))
        if usinas:
            ctx["g_curva"] = g_monit.curva_hoje(usinas)
            ctx["g_mensal"] = g_monit.geracao_mensal(usinas)
        uc = cliente.ucs.select_related("concessionaria").prefetch_related("usinas__inversores", "medidores").first()
        if uc:
            bal = balancos_uc(uc)
            ultimo = next((b for b in reversed(bal) if b.fatura), None)
            com_fatura = [b for b in bal if b.fatura and b.economia_estimada is not None]
            do_ano = [b for b in com_fatura if b.fatura.mes_referencia.year == hoje.year]
            economia_ano = sum((b.economia_estimada for b in do_ano), Decimal(0))
            media = (sum((b.economia_estimada for b in com_fatura), Decimal(0)) / len(com_fatura)) if com_fatura else 0
            ctx.update(uc=uc, ultimo=ultimo, g_custo=g_analise.custo(bal),
                       g_cascata=g_analise.cascata_balanco(ultimo),
                       economia_12m=sum((b.economia_estimada for b in com_fatura), Decimal(0)),
                       g_gauge=charts.gauge(economia_ano, media * 12, "Economia no ano") if com_fatura else None)
            if ultimo and ultimo.custo_sem_solar_estimado:
                def brl(v):
                    return "R$ " + number_format(v, 2, force_grouping=True)
                ctx["hero_sub"] = (f"Conta de {ultimo.rotulo}: pagou {brl(ultimo.fat_total)} "
                                   f"em vez de {brl(ultimo.custo_sem_solar_estimado)}")
        return ctx


class UsinaView(ClienteFinalMixin, TemplateView):
    template_name = "portal/usina.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        u = get_object_or_404(_usinas_do_cliente(self.request.user), pk=self.kwargs["pk"])
        ctx.update(usina=u, resumo=resumir_usina(u, 30), g_curva=g_monit.curva_hoje([u]), nav=_nav("usinas"),
                   g_geracao=g_monit.geracao_x_esperado([u]), g_aneis=g_monit.aneis_usina([u]))
        return ctx
