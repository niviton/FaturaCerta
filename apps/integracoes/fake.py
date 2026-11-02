"""Implementações fictícias, realistas e determinísticas (mesma entrada, mesmo resultado).

Cenários de demonstração ficam nas credenciais do equipamento, ex.:
    {"cenario": "parada", "desde": "2026-10-20"}   usina sem geração desde a data
    {"cenario": "baixa", "fator": 0.6}              geração abaixo do esperado
    {"cenario": "offline"}                          sem comunicação (dados param de chegar)
"""

import datetime
import hashlib
import logging
import math
import random
from decimal import Decimal

from django.utils import timezone

from .base import (
    GeracaoDia,
    LeituraMedidorDia,
    Mensagem,
    Notificador,
    PontoCurva,
    ProvedorInversor,
    ProvedorMedidor,
    StatusInversor,
)

log = logging.getLogger(__name__)

# Horas de sol pleno médias em Natal-RN por mês (aprox., só para demonstração).
HSP_NATAL = [5.9, 5.9, 5.7, 5.2, 4.9, 4.6, 4.8, 5.5, 6.0, 6.2, 6.3, 6.1]
PERFORMANCE_RATIO = 0.78
NASCER, POR = 5.5, 17.5  # horas locais aproximadas

# Fração do consumo que acontece enquanto há sol (simultaneidade), por segmento.
SIMULTANEIDADE = {
    "residencial": (0.18, 0.32), "comercial": (0.45, 0.65), "industrial": (0.5, 0.7),
    "rural": (0.35, 0.55), "publico": (0.5, 0.7), "condominio": (0.2, 0.35),
}


def _rng(*partes) -> random.Random:
    return random.Random("|".join(str(p) for p in partes))


def _q(v: float) -> Decimal:
    return Decimal(str(round(v, 2)))


def clima(dia: datetime.date) -> float:
    """Nebulosidade do dia: igual para todas as usinas da região."""
    return _rng("clima-natal", dia.isoformat()).uniform(0.74, 1.22)  # média ~0,98 do esperado


def fracao_solar(h: float) -> tuple[float, float]:
    """(fração da energia diária já gerada até a hora h, potência relativa 0..1)."""
    if h <= NASCER:
        return 0.0, 0.0
    if h >= POR:
        return 1.0, 0.0
    x = (h - NASCER) / (POR - NASCER)
    return (1 - math.cos(math.pi * x)) / 2, math.sin(math.pi * x)


class FakeInversor(ProvedorInversor):
    codigo = "fake"
    nome = "Demonstração"
    demo = True

    @property
    def _semente(self):
        return self.inversor.numero_serie or f"inv{self.inversor.pk}"

    @property
    def _cenario(self):
        return self.credenciais.get("cenario", "normal")

    def _n_inversores(self):
        return max(len(self.inversor.usina.inversores.all()), 1)

    def _parada_em(self, dia: datetime.date) -> bool:
        if self._cenario != "parada":
            return False
        desde = self.credenciais.get("desde")
        return desde is None or dia >= datetime.date.fromisoformat(desde)

    def kwh_do_dia(self, dia: datetime.date) -> float:
        """Energia do dia inteiro (sem cortar no horário atual)."""
        if self._parada_em(dia):
            return 0.0
        usina = self.inversor.usina
        esperada = usina.geracao_esperada_mes(dia.month)
        if esperada is not None:
            base = float(esperada) / 30.4 / self._n_inversores()
        else:
            kwp = float(usina.potencia_kwp or 5) / self._n_inversores()
            base = kwp * HSP_NATAL[dia.month - 1] * PERFORMANCE_RATIO
        ruido = _rng(self._semente, dia.isoformat()).uniform(0.95, 1.03)
        fator = float(self.credenciais.get("fator", 0.6)) if self._cenario == "baixa" else 1.0
        return base * clima(dia) * ruido * fator

    def _pico(self, kwh_dia):
        return kwh_dia / ((POR - NASCER) * 2 / math.pi) if kwh_dia else 0

    def potencia_em(self, momento: datetime.datetime) -> float:
        kwh = self.kwh_do_dia(momento.date())
        h = momento.hour + momento.minute / 60
        nuvem = _rng(self._semente, momento.strftime("%Y%m%d%H"), "nuvem").uniform(0.78, 1.0)
        return self._pico(kwh) * fracao_solar(h)[1] * nuvem

    def status(self) -> StatusInversor:
        agora = timezone.localtime()
        if self._cenario == "offline":
            return StatusInversor(False, Decimal(0), Decimal(0), agora - datetime.timedelta(hours=30), demo=True)
        kwh_dia = self.kwh_do_dia(agora.date())
        fracao = fracao_solar(agora.hour + agora.minute / 60)[0]
        online = not self._parada_em(agora.date())
        return StatusInversor(online, _q(self.potencia_em(agora)), _q(kwh_dia * fracao), agora, demo=True)

    def geracao_diaria(self, inicio, fim):
        if self._cenario == "offline":
            fim = min(fim, timezone.localdate() - datetime.timedelta(days=2))
        hoje = timezone.localdate()
        out, dia = [], inicio
        while dia <= min(fim, hoje):
            kwh = self.kwh_do_dia(dia)
            if dia == hoje:
                agora = timezone.localtime()
                kwh *= fracao_solar(agora.hour + agora.minute / 60)[0]
            out.append(GeracaoDia(dia, _q(kwh)))
            dia += datetime.timedelta(days=1)
        return out

    def curva_do_dia(self, dia):
        if self._cenario == "offline":
            return []
        tz = timezone.get_current_timezone()
        agora = timezone.localtime()
        out = []
        for minuto in range(int(NASCER * 60), int(POR * 60) + 1, 15):
            m = datetime.datetime.combine(dia, datetime.time(minuto // 60, minuto % 60), tzinfo=tz)
            if m > agora:
                break
            out.append(PontoCurva(m, _q(self.potencia_em(m))))
        return out


def energia_fake_da_uc(uc, dia: datetime.date) -> dict:
    """Balanço fictício de um dia numa UC: geração local, carga, simultâneo, importação e exportação.

    Usado pelo medidor fictício e pelas faturas de demonstração, para as três fontes contarem a mesma história.
    """
    geracao = 0.0
    for usina in uc.usinas.all():
        if usina.tipo != "junto_carga":
            continue
        for inv in usina.inversores.all():
            geracao += FakeInversor(inv).kwh_do_dia(dia)
    r = _rng("carga", uc.numero_uc, dia.isoformat())
    if uc.consumo_medio_kwh:
        base = float(uc.consumo_medio_kwh) / 30.4
    else:
        base = 25.0
    fim_de_semana = dia.weekday() >= 5
    segmento = uc.cliente.segmento
    if fim_de_semana and segmento in ("comercial", "industrial", "publico"):
        base *= 0.55 if dia.weekday() == 5 else 0.3
    carga = base * r.uniform(0.85, 1.15)
    lo, hi = SIMULTANEIDADE.get(segmento, (0.3, 0.5))
    simultaneo = min(carga * r.uniform(lo, hi), geracao)
    return {
        "geracao": geracao,
        "carga": carga,
        "simultaneo": simultaneo,
        "importacao": max(carga - simultaneo, 0.0),
        "exportacao": max(geracao - simultaneo, 0.0),
    }


class FakeMedidor(ProvedorMedidor):
    codigo = "fake"
    demo = True

    def leituras_diarias(self, inicio, fim):
        uc = self.medidor.uc
        ponto = self.medidor.ponto_medicao
        out, dia = [], inicio
        while dia <= fim:
            e = energia_fake_da_uc(uc, dia)
            rede = ponto in ("rede", "rede_carga")
            carga = ponto in ("carga", "rede_carga")
            out.append(LeituraMedidorDia(
                dia,
                _q(e["importacao"]) if rede else None,
                _q(e["exportacao"]) if rede else None,
                _q(e["carga"]) if carga else None,
            ))
            dia += datetime.timedelta(days=1)
        return out


class FakeNotificador(Notificador):
    demo = True

    def __init__(self, canal="email"):
        self.canal = canal

    def enviar(self, mensagem: Mensagem) -> str:
        log.info("[notificação fictícia %s] para=%s assunto=%s", self.canal, mensagem.destino, mensagem.assunto)
        chave = hashlib.sha1(f"{mensagem.destino}|{mensagem.assunto}".encode()).hexdigest()[:10]
        return f"fake-{self.canal}-{chave}"
