from collections import OrderedDict
from decimal import Decimal

from django.views.generic import TemplateView

from apps.cadastro.models import Usina
from apps.core.mixins import EquipeIntegradoraMixin

from . import services, tasks

FILTROS = OrderedDict([
    ("todas", "Todas"),
    ("atencao", "Precisam de atenção"),
    ("gerando", "Gerando"),
])
ATENCAO = {"parada", "sem_comunicacao", "abaixo", "sem_inversor"}
ORDEM = {"parada": 0, "sem_comunicacao": 1, "abaixo": 2, "sem_inversor": 3, "gerando": 4, "noite": 5}


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
        usinas = (Usina.objects.da_integradora(self.request.tenant).filter(ativa=True)
                  .select_related("uc_geradora__cliente")
                  .prefetch_related("inversores__status_atual"))
        resumos = [services.resumir_usina(u) for u in usinas]

        filtro = self.request.GET.get("filtro", "todas")
        q = self.request.GET.get("q", "").strip().lower()
        visiveis = resumos
        if filtro == "atencao":
            visiveis = [r for r in resumos if r.situacao in ATENCAO]
        elif filtro == "gerando":
            visiveis = [r for r in resumos if r.situacao == "gerando"]
        if q:
            visiveis = [r for r in visiveis if q in r.usina.nome.lower() or q in r.usina.cliente.nome.lower()
                        or any(q in m.lower() for m in r.marcas)]

        grupos = OrderedDict()
        for r in sorted(visiveis, key=lambda r: (r.usina.cliente.nome, ORDEM[r.situacao], r.usina.nome)):
            grupos.setdefault(r.usina.cliente, []).append(r)

        ctx.update(
            grupos=grupos,
            filtros=FILTROS,
            filtro=filtro,
            q=self.request.GET.get("q", ""),
            total=len(resumos),
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
