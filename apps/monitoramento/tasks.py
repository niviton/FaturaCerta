from celery import shared_task
from django.utils import timezone

from apps.cadastro.models import Inversor, Medidor

from . import services


def _inversores(integradora_id):
    qs = Inversor.objects.filter(usina__ativa=True).select_related("usina").prefetch_related("usina__inversores")
    return qs.filter(usina__integradora_id=integradora_id) if integradora_id else qs


@shared_task
def coletar_status_todos(integradora_id=None):
    qs = _inversores(integradora_id)
    for inv in qs:
        services.coletar_status(inv)
    return len(qs)


@shared_task
def coletar_geracao_todos(dias=35, integradora_id=None):
    total = sum(services.coletar_geracao(inv, dias) for inv in _inversores(integradora_id))
    medidores = Medidor.objects.select_related("uc__cliente")
    if integradora_id:
        medidores = medidores.filter(uc__integradora_id=integradora_id)
    for m in medidores:
        services.coletar_medidor(m, dias)
    return total


@shared_task
def coletar_curvas_hoje(integradora_id=None):
    hoje = timezone.localdate()
    return sum(services.coletar_curva(inv, hoje) for inv in _inversores(integradora_id))


@shared_task
def atualizar_clima(dias=3):
    """Clima real (Open-Meteo) das regiões com usinas; depois refaz o status e a curva de hoje."""
    from apps.integracoes import clima

    if not clima.ativo():
        return {}
    resultado = clima.atualizar_todas(dias)
    coletar_curvas_hoje()
    coletar_status_todos()
    return {f"{k[0]},{k[1]}": v for k, v in resultado.items()}


@shared_task
def consolidar_medicoes_esp():
    n = 0
    for m in Medidor.objects.filter(provedor_api="esp").exclude(token_hash=""):
        n += services.consolidar_medicoes(m, dias=2)
    return n
