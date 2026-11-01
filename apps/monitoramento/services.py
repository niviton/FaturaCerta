"""Coleta dos dados dos equipamentos e resumo do estado de cada usina."""

import calendar
import datetime
import logging
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.integracoes.base import ErroIntegracao
from apps.integracoes.registro import provedor_inversor, provedor_medidor

from .models import GeracaoDiaria, LeituraMedidor, StatusAtual

log = logging.getLogger(__name__)

# Estimativa usada quando a usina não tem geração esperada cadastrada.
HSP_NATAL = [5.9, 5.9, 5.7, 5.2, 4.9, 4.6, 4.8, 5.5, 6.0, 6.2, 6.3, 6.1]
PR_PADRAO = Decimal("0.78")


def coletar_status(inversor) -> StatusAtual:
    prov = provedor_inversor(inversor)
    st, _ = StatusAtual.objects.get_or_create(inversor=inversor)
    try:
        s = prov.status()
        st.online, st.potencia_atual_kw, st.energia_hoje_kwh = s.online, s.potencia_atual_kw, s.energia_hoje_kwh
        st.medido_em, st.demo, st.erro = s.medido_em, prov.demo, ""
    except ErroIntegracao as exc:
        st.erro = str(exc)[:255]
        log.warning("Falha no status do inversor %s: %s", inversor.pk, exc)
    st.save()
    return st


def coletar_geracao(inversor, dias: int = 35) -> int:
    prov = provedor_inversor(inversor)
    fim = timezone.localdate()
    try:
        itens = prov.geracao_diaria(fim - datetime.timedelta(days=dias - 1), fim)
    except ErroIntegracao as exc:
        log.warning("Falha na geração do inversor %s: %s", inversor.pk, exc)
        return 0
    for g in itens:
        GeracaoDiaria.objects.update_or_create(inversor=inversor, data=g.data,
                                               defaults={"kwh": g.kwh, "demo": prov.demo})
    return len(itens)


def coletar_medidor(medidor, dias: int = 35) -> int:
    prov = provedor_medidor(medidor)
    fim = timezone.localdate()
    try:
        itens = prov.leituras_diarias(fim - datetime.timedelta(days=dias - 1), fim - datetime.timedelta(days=1))
    except ErroIntegracao as exc:
        log.warning("Falha no medidor %s: %s", medidor.pk, exc)
        return 0
    for x in itens:
        LeituraMedidor.objects.update_or_create(
            medidor=medidor, data=x.data,
            defaults={"consumo_kwh": x.consumo_kwh, "injecao_kwh": x.injecao_kwh, "demo": prov.demo})
    return len(itens)


def geracao_no_periodo(usina, inicio: datetime.date, fim: datetime.date) -> Decimal:
    """Soma da geração entre duas datas (inclusive). Usado para cruzar com a janela de leitura da fatura."""
    total = GeracaoDiaria.objects.filter(inversor__usina=usina, data__range=(inicio, fim)).aggregate(s=Sum("kwh"))["s"]
    return total or Decimal(0)


def esperado_no_dia(usina, dia: datetime.date) -> Decimal | None:
    mensal = usina.geracao_esperada_mes(dia.month)
    if mensal is not None:
        return (mensal / calendar.monthrange(dia.year, dia.month)[1]).quantize(Decimal("0.1"))
    if usina.potencia_kwp:
        return (usina.potencia_kwp * Decimal(str(HSP_NATAL[dia.month - 1])) * PR_PADRAO).quantize(Decimal("0.1"))
    return None


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


ROTULOS = {
    "gerando": "Gerando",
    "noite": "Sem sol agora",
    "abaixo": "Abaixo do esperado",
    "parada": "Parada",
    "sem_comunicacao": "Sem comunicação",
    "sem_inversor": "Sem inversor",
}


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
    por_dia = dict(
        GeracaoDiaria.objects.filter(inversor__usina=usina, data__range=(inicio, hoje - datetime.timedelta(days=1)))
        .values("data").annotate(s=Sum("kwh")).values_list("data", "s")
    )
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
