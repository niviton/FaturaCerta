from celery import shared_task

from apps.cadastro.models import Inversor, Medidor

from . import services


@shared_task
def coletar_status_todos(integradora_id=None):
    qs = Inversor.objects.filter(usina__ativa=True)
    if integradora_id:
        qs = qs.filter(usina__integradora_id=integradora_id)
    for inv in qs.select_related("usina"):
        services.coletar_status(inv)
    return qs.count()


@shared_task
def coletar_geracao_todos(dias=35, integradora_id=None):
    qs = Inversor.objects.filter(usina__ativa=True)
    medidores = Medidor.objects.filter(usina__ativa=True)
    if integradora_id:
        qs = qs.filter(usina__integradora_id=integradora_id)
        medidores = medidores.filter(usina__integradora_id=integradora_id)
    total = sum(services.coletar_geracao(inv, dias) for inv in qs.select_related("usina"))
    for m in medidores.select_related("usina"):
        services.coletar_medidor(m, dias)
    return total
