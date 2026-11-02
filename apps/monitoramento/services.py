"""Coleta dos dados dos equipamentos, consolidação do ESP e séries para os gráficos."""

import calendar
import datetime
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db.models import Max, Min, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.integracoes.base import ErroIntegracao
from apps.integracoes.registro import provedor_inversor, provedor_medidor

from .models import AmostraPotencia, GeracaoDiaria, LeituraMedidor, MedicaoBruta, StatusAtual

log = logging.getLogger(__name__)

# Estimativa usada quando a usina não tem geração esperada cadastrada.
HSP_NATAL = [5.9, 5.9, 5.7, 5.2, 4.9, 4.6, 4.8, 5.5, 6.0, 6.2, 6.3, 6.1]


# ---------------------------------------------------------------- coleta

def coletar_status(inversor) -> StatusAtual:
    prov = provedor_inversor(inversor)
    st, _ = StatusAtual.objects.get_or_create(inversor=inversor)
    try:
        s = prov.status()
        st.online, st.potencia_atual_kw, st.energia_hoje_kwh = s.online, s.potencia_atual_kw, s.energia_hoje_kwh
        st.medido_em, st.demo, st.erro = s.medido_em, prov.demo, ""
        if s.online and s.medido_em:
            AmostraPotencia.objects.update_or_create(
                inversor=inversor, momento=s.medido_em.replace(second=0, microsecond=0),
                defaults={"kw": s.potencia_atual_kw})
    except ErroIntegracao as exc:
        st.erro = str(exc)[:255]
        log.warning("Falha no status do inversor %s: %s", inversor.pk, exc)
    st.save()
    return st


def coletar_curva(inversor, dia: datetime.date) -> int:
    pontos = provedor_inversor(inversor).curva_do_dia(dia)
    AmostraPotencia.objects.bulk_create(
        [AmostraPotencia(inversor=inversor, momento=p.momento, kw=p.kw) for p in pontos],
        update_conflicts=True, unique_fields=["inversor", "momento"], update_fields=["kw"])
    return len(pontos)


def coletar_geracao(inversor, dias: int = 35) -> int:
    prov = provedor_inversor(inversor)
    fim = timezone.localdate()
    try:
        itens = prov.geracao_diaria(fim - datetime.timedelta(days=dias - 1), fim)
    except ErroIntegracao as exc:
        log.warning("Falha na geração do inversor %s: %s", inversor.pk, exc)
        return 0
    GeracaoDiaria.objects.bulk_create(
        [GeracaoDiaria(inversor=inversor, data=g.data, kwh=g.kwh, demo=prov.demo) for g in itens],
        update_conflicts=True, unique_fields=["inversor", "data"], update_fields=["kwh", "demo"])
    return len(itens)


def coletar_medidor(medidor, dias: int = 35) -> int:
    prov = provedor_medidor(medidor)
    if prov.codigo == "esp":
        return consolidar_medicoes(medidor, dias)
    fim = timezone.localdate() - datetime.timedelta(days=1)
    try:
        itens = prov.leituras_diarias(fim - datetime.timedelta(days=dias - 1), fim)
    except ErroIntegracao as exc:
        log.warning("Falha no medidor %s: %s", medidor.pk, exc)
        return 0
    LeituraMedidor.objects.bulk_create(
        [LeituraMedidor(medidor=medidor, data=x.data, importacao_kwh=x.importacao_kwh,
                        exportacao_kwh=x.exportacao_kwh, carga_kwh=x.carga_kwh, demo=prov.demo) for x in itens],
        update_conflicts=True, unique_fields=["medidor", "data"],
        update_fields=["importacao_kwh", "exportacao_kwh", "carga_kwh", "demo"])
    return len(itens)


def consolidar_medicoes(medidor, dias: int = 3) -> int:
    """Transforma os contadores acumulados enviados pelo ESP em energia por dia (máximo − mínimo do dia)."""
    hoje = timezone.localdate()
    n = 0
    for k in range(dias):
        dia = hoje - datetime.timedelta(days=k)
        qs = MedicaoBruta.objects.filter(medidor=medidor, momento__date=dia)
        agg = qs.aggregate(imin=Min("importacao_kwh"), imax=Max("importacao_kwh"), emin=Min("exportacao_kwh"),
                           emax=Max("exportacao_kwh"), cmin=Min("carga_kwh"), cmax=Max("carga_kwh"))
        if not qs.exists():
            continue

        def delta(a, b):
            return None if a is None or b is None else (b - a).quantize(Decimal("0.01"))

        LeituraMedidor.objects.update_or_create(medidor=medidor, data=dia, defaults={
            "importacao_kwh": delta(agg["imin"], agg["imax"]),
            "exportacao_kwh": delta(agg["emin"], agg["emax"]),
            "carga_kwh": delta(agg["cmin"], agg["cmax"]),
            "demo": False,
        })
        n += 1
    return n


# ---------------------------------------------------------------- séries

def geracao_no_periodo(usina, inicio: datetime.date, fim: datetime.date) -> Decimal:
    """Soma da geração entre duas datas (inclusive). Usado para cruzar com a janela de leitura da fatura."""
    total = GeracaoDiaria.objects.filter(inversor__usina=usina, data__range=(inicio, fim)).aggregate(s=Sum("kwh"))["s"]
    return total or Decimal(0)


def esperado_no_dia(usina, dia: datetime.date) -> Decimal | None:
    mensal = usina.geracao_esperada_mes(dia.month)
    if mensal is not None:
        return (mensal / calendar.monthrange(dia.year, dia.month)[1]).quantize(Decimal("0.1"))
    if usina.potencia_kwp:
        return (usina.potencia_kwp * Decimal(str(HSP_NATAL[dia.month - 1])) * usina.performance_ratio
                ).quantize(Decimal("0.1"))
    return None


def esperado_no_mes(usina, mes: datetime.date) -> Decimal | None:
    v = usina.geracao_esperada_mes(mes.month)
    if v is not None:
        return v
    d = esperado_no_dia(usina, mes)
    return d * calendar.monthrange(mes.year, mes.month)[1] if d is not None else None


def serie_diaria(usinas, inicio: datetime.date, fim: datetime.date, por_usina=False):
    """{data: kWh} (ou {usina_id: {data: kWh}})."""
    qs = (GeracaoDiaria.objects.filter(inversor__usina__in=usinas, data__range=(inicio, fim))
          .values("inversor__usina_id", "data").annotate(s=Sum("kwh")))
    if por_usina:
        out = defaultdict(dict)
        for r in qs:
            out[r["inversor__usina_id"]][r["data"]] = r["s"]
        return out
    out = defaultdict(Decimal)
    for r in qs:
        out[r["data"]] += r["s"]
    return out


def ultimos_meses(n: int, ate: datetime.date | None = None) -> list[datetime.date]:
    ate = (ate or timezone.localdate()).replace(day=1)
    meses = []
    for _ in range(n):
        meses.append(ate)
        ate = (ate - datetime.timedelta(days=1)).replace(day=1)
    return list(reversed(meses))


def serie_mensal(usinas, meses: list[datetime.date]):
    """[(mês, gerado, esperado)] somando as usinas."""
    qs = (GeracaoDiaria.objects.filter(inversor__usina__in=usinas, data__gte=meses[0])
          .annotate(m=TruncMonth("data")).values("m").annotate(s=Sum("kwh")))
    por_mes = {r["m"]: r["s"] for r in qs}
    out = []
    for m in meses:
        esp = [esperado_no_mes(u, m) for u in usinas]
        esp_total = sum((e for e in esp if e is not None), Decimal(0)) if any(e is not None for e in esp) else None
        out.append((m, por_mes.get(m, Decimal(0)), esp_total))
    return out


def curva_do_dia(usinas, dia: datetime.date):
    """[(HH:MM, kW)] somando as usinas, em intervalos de 15 min."""
    tz = timezone.get_current_timezone()
    inicio = datetime.datetime.combine(dia, datetime.time(0), tzinfo=tz)
    qs = AmostraPotencia.objects.filter(inversor__usina__in=usinas, momento__range=(
        inicio, inicio + datetime.timedelta(days=1)))
    por_slot = defaultdict(Decimal)
    for a in qs.only("momento", "kw"):
        m = timezone.localtime(a.momento)
        por_slot[f"{m.hour:02d}:{m.minute // 15 * 15:02d}"] += a.kw
    return sorted(por_slot.items())


# ---------------------------------------------------------------- situação

@dataclass
class ResumoUsina:
    usina: object
    situacao: str  # gerando | parada | sem_comunicacao | abaixo | noite | sem_inversor
    online: bool
    potencia_kw: Decimal
    hoje_kwh: Decimal
    esperado_hoje_kwh: Decimal | None
    marcas: list[str]
    demo: bool
    ultimos_dias: list[tuple[datetime.date, Decimal, Decimal | None]] = field(default_factory=list)
    desempenho_7d: Decimal | None = None
    atualizado_em: datetime.datetime | None = None

    @property
    def rotulo(self):
        return ROTULOS[self.situacao]

    @property
    def pct_hoje(self):
        if not self.esperado_hoje_kwh:
            return None
        return min(int(self.hoje_kwh / self.esperado_hoje_kwh * 100), 999)

    @property
    def pct_7d(self):
        return None if self.desempenho_7d is None else int(self.desempenho_7d * 100)

    @property
    def precisa_atencao(self):
        return self.situacao in ATENCAO


ROTULOS = {
    "gerando": "Gerando",
    "noite": "Sem sol agora",
    "abaixo": "Abaixo do esperado",
    "parada": "Parada",
    "sem_comunicacao": "Sem comunicação",
    "sem_inversor": "Sem inversor",
}
ATENCAO = {"parada", "sem_comunicacao", "abaixo", "sem_inversor"}
ORDEM_SITUACAO = {"parada": 0, "sem_comunicacao": 1, "abaixo": 2, "sem_inversor": 3, "gerando": 4, "noite": 5}


def resumir_usina(usina, dias_grafico: int = 14) -> ResumoUsina:
    agora = timezone.localtime()
    hoje = agora.date()
    inversores = list(usina.inversores.all())
    if not inversores:
        return ResumoUsina(usina, "sem_inversor", False, Decimal(0), Decimal(0), esperado_no_dia(usina, hoje), [],
                           False)

    status = [getattr(i, "status_atual", None) for i in inversores]
    limite = datetime.timedelta(hours=settings.MONITOR_HORAS_SEM_COMUNICACAO)
    comunicando = all(s and s.medido_em and agora - s.medido_em < limite for s in status)
    reportou_online = all(s and s.online for s in status)
    online = comunicando and reportou_online
    potencia = sum((s.potencia_atual_kw for s in status if s), Decimal(0))
    hoje_kwh = sum((s.energia_hoje_kwh for s in status if s), Decimal(0))
    demo = any(s.demo for s in status if s)
    atualizado = max((s.coletado_em for s in status if s), default=None)

    inicio = hoje - datetime.timedelta(days=dias_grafico)
    por_dia = serie_diaria([usina], inicio, hoje - datetime.timedelta(days=1))
    ultimos = []
    for n in range(dias_grafico, 0, -1):
        dia = hoje - datetime.timedelta(days=n)
        ultimos.append((dia, por_dia.get(dia, Decimal(0)), esperado_no_dia(usina, dia)))

    sete = ultimos[-7:]
    esp7 = sum((e or 0 for _, _, e in sete), Decimal(0))
    desempenho = (sum((g for _, g, _ in sete), Decimal(0)) / esp7).quantize(Decimal("0.01")) if esp7 else None

    eh_dia = settings.MONITOR_HORA_INICIO <= agora.hour < settings.MONITOR_HORA_FIM
    if not comunicando:
        situacao = "sem_comunicacao"
    elif not reportou_online or (eh_dia and potencia == 0 and hoje_kwh == 0):
        situacao = "parada"
    elif desempenho is not None and desempenho < Decimal(str(settings.MONITOR_LIMIAR_ABAIXO)):
        situacao = "abaixo"
    elif not eh_dia and potencia == 0:
        situacao = "noite"
    else:
        situacao = "gerando"

    marcas = sorted({i.marca for i in inversores})
    return ResumoUsina(usina, situacao, online, potencia, hoje_kwh, esperado_no_dia(usina, hoje), marcas, demo,
                       ultimos, desempenho, atualizado)
