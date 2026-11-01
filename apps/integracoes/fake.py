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
    ProvedorInversor,
    ProvedorMedidor,
    StatusInversor,
)

log = logging.getLogger(__name__)

# Horas de sol pleno médias em Natal-RN por mês (aprox., só para demonstração).
HSP_NATAL = [5.9, 5.9, 5.7, 5.2, 4.9, 4.6, 4.8, 5.5, 6.0, 6.2, 6.3, 6.1]
PERFORMANCE_RATIO = 0.78
NASCER, POR = 5.5, 17.5  # horas locais aproximadas


def _rng(*partes) -> random.Random:
    return random.Random("|".join(str(p) for p in partes))


def _q(v: float) -> Decimal:
    return Decimal(str(round(v, 2)))


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

    def _kwp(self) -> float:
        usina = self.inversor.usina
        n = max(usina.inversores.count(), 1)
        return float(usina.potencia_kwp or 5) / n

    def _parada_em(self, dia: datetime.date) -> bool:
        if self._cenario != "parada":
            return False
        desde = self.credenciais.get("desde")
        return desde is None or dia >= datetime.date.fromisoformat(desde)

    def _clima(self, dia: datetime.date) -> float:
        # nebulosidade do dia: igual para todas as usinas da região
        return _rng("clima-natal", dia.isoformat()).uniform(0.62, 1.08)

    def _kwh_do_dia(self, dia: datetime.date) -> float:
        if self._parada_em(dia):
            return 0.0
        esperada = self.inversor.usina.geracao_esperada_mes(dia.month)
        if esperada is not None:
            n_inv = max(self.inversor.usina.inversores.count(), 1)
            base = float(esperada) / 30.4 / n_inv
        else:
            base = self._kwp() * HSP_NATAL[dia.month - 1] * PERFORMANCE_RATIO
        ruido = _rng(self._semente, dia.isoformat()).uniform(0.95, 1.03)
        fator = float(self.credenciais.get("fator", 0.6)) if self._cenario == "baixa" else 1.0
        return base * self._clima(dia) * ruido * fator

    def _fracao_do_dia(self, agora: datetime.datetime) -> tuple[float, float]:
        """(fração da energia diária já gerada, fator de potência instantânea 0..1)."""
        h = agora.hour + agora.minute / 60
        if h <= NASCER:
            return 0.0, 0.0
        if h >= POR:
            return 1.0, 0.0
        x = (h - NASCER) / (POR - NASCER)
        return (1 - math.cos(math.pi * x)) / 2, math.sin(math.pi * x)

    def status(self) -> StatusInversor:
        agora = timezone.localtime()
        if self._cenario == "offline":
            return StatusInversor(False, Decimal(0), Decimal(0), agora - datetime.timedelta(hours=30), demo=True)
        kwh_dia = self._kwh_do_dia(agora.date())
        fracao, sino = self._fracao_do_dia(agora)
        # potência de pico ~ energia diária / (horas de sol * 2/pi)
        pico = kwh_dia / ((POR - NASCER) * 2 / math.pi) if kwh_dia else 0
        online = not self._parada_em(agora.date())
        return StatusInversor(online, _q(pico * sino), _q(kwh_dia * fracao), agora, demo=True)

    def geracao_diaria(self, inicio, fim):
        hoje = timezone.localdate()
        out, dia = [], inicio
        while dia <= min(fim, hoje):
            kwh = self._kwh_do_dia(dia)
            if dia == hoje:
                kwh *= self._fracao_do_dia(timezone.localtime())[0]
            if self._cenario != "offline":
                out.append(GeracaoDia(dia, _q(kwh)))
            dia += datetime.timedelta(days=1)
        return out


class FakeMedidor(ProvedorMedidor):
    codigo = "fake"
    demo = True

    def leituras_diarias(self, inicio, fim):
        usina = self.medidor.usina
        fator_constante = float(self.credenciais.get("fator_constante", 1.0))
        consumo_base = float(self.credenciais.get("consumo_diario_kwh", 25))
        out, dia = [], inicio
        while dia <= fim:
            r = _rng(self.medidor.numero_serie or self.medidor.pk, dia.isoformat())
            gerado = sum(
                float(FakeInversor(inv)._kwh_do_dia(dia)) for inv in usina.inversores.all()
            )
            consumo = consumo_base * r.uniform(0.8, 1.2)
            simultaneo = min(consumo * r.uniform(0.25, 0.45), gerado)
            injecao = max(gerado - simultaneo, 0)
            da_rede = max(consumo - simultaneo, 0)
            out.append(LeituraMedidorDia(dia, _q(da_rede * fator_constante), _q(injecao * fator_constante)))
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
