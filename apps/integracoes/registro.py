"""Escolhe a implementação de cada integração.

Regra: usa a real quando o equipamento pede um provedor real E as credenciais estão completas.
Caso contrário cai no Fake (e a tela mostra o selo "dados de demonstração").
"""

import logging

from django.conf import settings

from .base import IntegracaoNaoConfigurada, Notificador, ProvedorInversor, ProvedorMedidor
from .fake import FakeInversor, FakeMedidor, FakeNotificador
from .inversores_reais import PROVEDORES_REAIS
from .outros_reais import EmailDjango, MedidorHTTP, MedidorMQTT, WhatsAppCloud

log = logging.getLogger(__name__)

MEDIDORES_REAIS = {"http": MedidorHTTP, "mqtt": MedidorMQTT}


def provedor_inversor(inversor) -> ProvedorInversor:
    codigo = inversor.provedor_api or settings.INVERTER_PROVIDER
    classe = PROVEDORES_REAIS.get(codigo)
    if classe is not None:
        try:
            return classe(inversor)
        except IntegracaoNaoConfigurada as exc:
            log.info("Inversor %s usando dados fictícios: %s", inversor.pk, exc)
    return FakeInversor(inversor)


def provedor_medidor(medidor) -> ProvedorMedidor:
    codigo = medidor.provedor_api or settings.METER_PROVIDER
    classe = MEDIDORES_REAIS.get(codigo)
    if classe is not None:
        try:
            return classe(medidor)
        except IntegracaoNaoConfigurada as exc:
            log.info("Medidor %s usando dados fictícios: %s", medidor.pk, exc)
    return FakeMedidor(medidor)


def notificador(canal: str) -> Notificador:
    escolha = getattr(settings, f"NOTIFY_{canal.upper()}_PROVIDER", "fake")
    try:
        if canal == "email" and escolha == "smtp":
            return EmailDjango()
        if canal == "whatsapp" and escolha == "cloud":
            return WhatsAppCloud()
    except IntegracaoNaoConfigurada as exc:
        log.info("Notificação %s fictícia: %s", canal, exc)
    return FakeNotificador(canal)
