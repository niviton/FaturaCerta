"""Interfaces das integrações externas.

Cada tipo de integração tem uma classe base abstrata, uma implementação Fake (dados fictícios
determinísticos) e implementações reais. O resto do sistema só conhece estas interfaces e os
formatos internos abaixo; nunca sabe se o dado é fictício ou real (exceto pelo campo `demo`,
usado só para mostrar o selo "dados de demonstração").
"""

import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


class IntegracaoNaoConfigurada(Exception):
    """Faltam credenciais ou variáveis de ambiente para usar a implementação real."""


class ErroIntegracao(Exception):
    """Falha ao falar com o serviço externo."""


# ---------- formatos internos ----------

@dataclass(frozen=True)
class StatusInversor:
    online: bool
    potencia_atual_kw: Decimal
    energia_hoje_kwh: Decimal
    medido_em: datetime.datetime
    demo: bool = False


@dataclass(frozen=True)
class GeracaoDia:
    data: datetime.date
    kwh: Decimal


@dataclass(frozen=True)
class LeituraMedidorDia:
    data: datetime.date
    consumo_kwh: Decimal
    injecao_kwh: Decimal


@dataclass(frozen=True)
class Mensagem:
    destino: str
    assunto: str
    texto: str


# ---------- interfaces ----------

class ProvedorInversor(ABC):
    codigo: str = ""
    nome: str = ""
    demo: bool = False

    def __init__(self, inversor):
        self.inversor = inversor
        self.credenciais = inversor.credenciais or {}

    @abstractmethod
    def status(self) -> StatusInversor:
        """Situação instantânea: online, potência agora e energia acumulada no dia."""

    @abstractmethod
    def geracao_diaria(self, inicio: datetime.date, fim: datetime.date) -> list[GeracaoDia]:
        """Energia gerada por dia, de `inicio` a `fim` (inclusive)."""


class ProvedorMedidor(ABC):
    codigo: str = ""
    demo: bool = False

    def __init__(self, medidor):
        self.medidor = medidor
        self.credenciais = medidor.credenciais or {}

    @abstractmethod
    def leituras_diarias(self, inicio: datetime.date, fim: datetime.date) -> list[LeituraMedidorDia]:
        """Consumo da rede e injeção na rede por dia."""


class Notificador(ABC):
    canal: str = ""
    demo: bool = False

    @abstractmethod
    def enviar(self, mensagem: Mensagem) -> str:
        """Envia e devolve um identificador do envio."""
