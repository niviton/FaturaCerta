"""Cruzamento das três fontes da auditoria, na janela de leitura de cada fatura.

    1. Inversor (API do fabricante) ......... quanto a usina GEROU
    2. Medidor próprio (ESP / sensores) ...... quanto entrou da rede, quanto saiu e quanto a casa consumiu
    3. Concessionária (fatura) ............... o que ela MEDIU e COBROU

Daqui saem o balanço energético (autoconsumo, consumo real) e os indícios que a auditoria
deve investigar. São balanços em kWh, reproduzíveis. Valores regulatórios em R$ (compensação,
Fio B, diferença a recuperar) ficam com o motor de regras e as tabelas com vigência; aqui o R$
é só estimativa de economia, marcada como tal.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Count, Sum

from apps.faturas.models import Fatura
from apps.monitoramento.models import LeituraMedidor
from apps.monitoramento.services import esperado_no_dia, geracao_no_periodo, ultimos_meses

LIMIAR_DIVERGENCIA = Decimal("0.05")  # 5% entre fontes
CONSTANTES_COMUNS = [Decimal(x) for x in ("1.2", "1.25", "1.5", "2", "0.8", "0.5")]
D0 = Decimal(0)


def _q(v):
    return None if v is None else Decimal(v).quantize(Decimal("0.1"))


@dataclass
class Indicio:
    codigo: str
    gravidade: str  # alta | media | baixa
    titulo: str
    detalhe: str


@dataclass
class Balanco:
    uc: object
    inicio: datetime.date
    fim: datetime.date
    fatura: Fatura | None = None
    # fonte 1: inversor
    geracao_kwh: Decimal | None = None
    geracao_esperada_kwh: Decimal | None = None
    # fonte 2: medidor próprio
    esp_importacao_kwh: Decimal | None = None
    esp_exportacao_kwh: Decimal | None = None
    esp_carga_kwh: Decimal | None = None
    esp_cobertura: Decimal | None = None  # fração dos dias com leitura
    indicios: list[Indicio] = field(default_factory=list)
    tarifa: Decimal | None = None

    # ---- fonte 3: fatura
    @property
    def fat_consumo(self):
        return self.fatura.consumo_kwh if self.fatura else None

    @property
    def fat_injetada(self):
        return self.fatura.energia_injetada_kwh if self.fatura else None

    @property
    def fat_compensada(self):
        return self.fatura.energia_compensada_kwh if self.fatura else None

    @property
    def fat_total(self):
        return self.fatura.valor_total if self.fatura else None

    @property
    def dias(self):
        return (self.fim - self.inicio).days + 1

    @property
    def rotulo(self):
        if self.fatura:
            return f"{self.fatura.mes_referencia:%m/%Y}"
        return f"{self.inicio:%m/%Y}"

    # ---- referências: a fatura manda; sem fatura, o medidor próprio
    @property
    def injetada_ref(self):
        return self.fat_injetada if self.fatura else self.esp_exportacao_kwh

    @property
    def importacao_ref(self):
        return self.fat_consumo if self.fatura else self.esp_importacao_kwh

    # ---- derivados
    @property
    def autoconsumo_kwh(self):
        """Geração consumida na hora (não passa pelo medidor da concessionária e não paga tarifa)."""
        if self.geracao_kwh is None or self.injetada_ref is None:
            return None
        return _q(self.geracao_kwh - self.injetada_ref)

    @property
    def consumo_real_kwh(self):
        if self.esp_carga_kwh is not None:
            return _q(self.esp_carga_kwh)
        if self.importacao_ref is None:
            return None
        return _q(self.importacao_ref + max(self.autoconsumo_kwh or D0, D0))

    @property
    def pct_atendido_solar(self):
        """Quanto do consumo real foi atendido pelo sol (autoconsumo + compensação)."""
        real = self.consumo_real_kwh
        if not real:
            return None
        solar = max(self.autoconsumo_kwh or D0, D0) + (self.fat_compensada or D0)
        return min(int(solar / real * 100), 100)

    @property
    def custo_sem_solar_estimado(self):
        if self.tarifa is None or self.consumo_real_kwh is None:
            return None
        return (self.consumo_real_kwh * self.tarifa).quantize(Decimal("0.01"))

    @property
    def economia_estimada(self):
        sem = self.custo_sem_solar_estimado
        if sem is None or self.fat_total is None:
            return None
        return (sem - self.fat_total).quantize(Decimal("0.01"))

    @property
    def desempenho(self):
        if not self.geracao_esperada_kwh or self.geracao_kwh is None:
            return None
        return int(self.geracao_kwh / self.geracao_esperada_kwh * 100)

    @property
    def tem_alta(self):
        return any(i.gravidade == "alta" for i in self.indicios)


def _usinas_locais(uc):
    return [u for u in uc.usinas.all() if u.tipo == "junto_carga" and u.ativa]


def _pct(a, b):
    return abs(a - b) / b if b else (D0 if a == b else Decimal(1))


def balanco_periodo(uc, inicio, fim, fatura=None) -> Balanco:
    b = Balanco(uc=uc, inicio=inicio, fim=fim, fatura=fatura, tarifa=uc.concessionaria.tarifa_referencia_kwh)
    usinas = _usinas_locais(uc)
    if usinas and any(u.inversores.all() for u in usinas):
        b.geracao_kwh = _q(sum((geracao_no_periodo(u, inicio, fim) for u in usinas), D0))
        esp = D0
        dia = inicio
        while dia <= fim:
            for u in usinas:
                esp += esperado_no_dia(u, dia) or D0
            dia += datetime.timedelta(days=1)
        b.geracao_esperada_kwh = _q(esp) if esp else None

    medidores = list(uc.medidores.all())
    if medidores:
        agg = LeituraMedidor.objects.filter(medidor__in=medidores, data__range=(inicio, fim)).aggregate(
            i=Sum("importacao_kwh"), e=Sum("exportacao_kwh"), c=Sum("carga_kwh"), n=Count("data", distinct=True))
        b.esp_importacao_kwh, b.esp_exportacao_kwh, b.esp_carga_kwh = _q(agg["i"]), _q(agg["e"]), _q(agg["c"])
        b.esp_cobertura = Decimal(agg["n"]) / b.dias if b.dias else None

    b.indicios = _indicios(b)
    return b


def _indicios(b: Balanco) -> list[Indicio]:
    out = []
    f = b.fatura
    esp_ok = b.esp_cobertura is not None and b.esp_cobertura >= Decimal("0.9")

    if b.autoconsumo_kwh is not None and b.autoconsumo_kwh < -Decimal(5):
        out.append(Indicio("injecao_maior_que_geracao", "alta", "Injeção maior que a geração do inversor",
                           f"A fatura registra {b.injetada_ref} kWh injetados, mas o inversor gerou {b.geracao_kwh} kWh "
                           "no mesmo período. Confira a leitura da concessionária e a API do inversor."))

    if f and esp_ok and b.esp_exportacao_kwh is not None and b.esp_exportacao_kwh > 0:
        dif = _pct(f.energia_injetada_kwh, b.esp_exportacao_kwh)
        if dif > LIMIAR_DIVERGENCIA:
            out.append(Indicio("injecao_diverge_medidor", "media", "Injeção da fatura diverge do medidor próprio",
                               f"Fatura: {f.energia_injetada_kwh} kWh. Medidor próprio: {b.esp_exportacao_kwh} kWh "
                               f"({int(dif * 100)}% de diferença)."))

    if f and esp_ok and b.esp_importacao_kwh:
        razao = f.consumo_kwh / b.esp_importacao_kwh
        if abs(razao - 1) > LIMIAR_DIVERGENCIA:
            perto = min(CONSTANTES_COMUNS, key=lambda c: abs(c - razao))
            sufixo = (f" A razão é quase constante ({razao:.2f}): suspeita de constante do medidor errada."
                      if abs(perto - razao) < Decimal("0.03") else "")
            out.append(Indicio("consumo_diverge_medidor", "alta",
                               f"Consumo faturado {int(abs(razao - 1) * 100)}% "
                               f"{'acima' if razao > 1 else 'abaixo'} do medido",
                               f"Fatura: {f.consumo_kwh} kWh. Medidor próprio: {b.esp_importacao_kwh} kWh.{sufixo}"))

    if f and f.energia_injetada_kwh > 0:
        disp = Decimal(f.custo_disponibilidade_kwh or b.uc.custo_disponibilidade_kwh or 0)
        compensavel = max(f.consumo_kwh - disp, D0)
        esperado = min(f.energia_injetada_kwh + (f.saldo_creditos_kwh or D0), compensavel)
        if f.energia_compensada_kwh + Decimal(5) < min(f.energia_injetada_kwh, compensavel):
            out.append(Indicio("injecao_nao_compensada", "alta", "Injeção não compensada",
                               f"Injetado {f.energia_injetada_kwh} kWh, compensado {f.energia_compensada_kwh} kWh, "
                               f"consumo compensável {compensavel} kWh. Esperado compensar ~{esperado} kWh."))

    if f and b.uc.constante_medidor and f.constante_medidor != b.uc.constante_medidor:
        out.append(Indicio("constante_diferente", "alta", "Constante do medidor na fatura difere do cadastro",
                           f"A fatura usa constante {f.constante_medidor:g}; o medidor instalado tem "
                           f"{b.uc.constante_medidor:g}. Isso multiplica o consumo cobrado."))

    if f and f.leitura_confere is False:
        out.append(Indicio("leitura_nao_fecha", "media", "Leitura × constante não fecha com o consumo",
                           f"({f.leitura_atual} − {f.leitura_anterior}) × {f.constante_medidor} = "
                           f"{f.consumo_pela_leitura} kWh, mas a fatura cobra {f.consumo_kwh} kWh."))

    if f and f.demanda_medida_kw and f.demanda_contratada_kw and f.demanda_medida_kw > f.demanda_contratada_kw:
        out.append(Indicio("ultrapassagem", "media", "Ultrapassagem de demanda",
                           f"Medida {f.demanda_medida_kw} kW para {f.demanda_contratada_kw} kW contratados"
                           + (f"; cobrado R$ {f.valor_ultrapassagem}." if f.valor_ultrapassagem else ".")))
    if f and f.valor_reativo:
        out.append(Indicio("reativo", "baixa", "Cobrança de energia reativa",
                           f"R$ {f.valor_reativo} de reativo: fator de potência abaixo de 0,92. Avaliar capacitores."))

    if b.desempenho is not None and b.desempenho < 80:
        out.append(Indicio("geracao_baixa", "media", "Geração abaixo do esperado no período",
                           f"{b.geracao_kwh} kWh gerados de {b.geracao_esperada_kwh} kWh esperados ({b.desempenho}%)."))
    return out


def balancos_uc(uc, n: int = 12) -> list[Balanco]:
    """Um balanço por fatura (janela de leitura). Sem faturas, usa meses civis com inversor e medidor próprio."""
    faturas = list(Fatura.objects.filter(uc=uc).order_by("-mes_referencia")[:n])
    if faturas:
        return [balanco_periodo(uc, f.data_leitura_anterior + datetime.timedelta(days=1), f.data_leitura_atual, f)
                for f in reversed(faturas)]
    out = []
    for m in ultimos_meses(n + 1)[:-1]:
        fim = (m + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        out.append(balanco_periodo(uc, m, fim))
    return out


def fontes_disponiveis(uc) -> dict:
    usinas = _usinas_locais(uc)
    return {
        "inversor": any(u.inversores.all() for u in usinas),
        "medidor": bool(list(uc.medidores.all())),
        "fatura": Fatura.objects.filter(uc=uc).exists(),
    }
