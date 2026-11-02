"""API que recebe medições do ESP32 (ou de qualquer dispositivo próprio).

POST /api/medidores/medicoes
Authorization: Bearer <token do dispositivo>
Content-Type: application/json

Um objeto ou uma lista (para enviar o que ficou guardado sem conexão):
{
  "momento": "2026-11-01T14:30:00-03:00",   opcional; sem ele usamos a hora do servidor
  "potencia_w": -1830.5,                     + importando da rede / − injetando
  "importacao_kwh": 15234.120,               contadores ACUMULADOS (não zere a cada envio)
  "exportacao_kwh": 9012.450,
  "carga_kwh": 20110.300,                    se houver sensor na carga
  "tensao_v": 221.4, "corrente_a": 8.3, "fator_potencia": 0.97
}
"""

import datetime
import json
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.cadastro.models import Medidor

from .models import MedicaoBruta

CAMPOS = ["potencia_w", "importacao_kwh", "exportacao_kwh", "carga_kwh", "tensao_v", "corrente_a",
          "fator_potencia"]
MAX_POR_ENVIO = 500


def _dec(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation as exc:
        raise ValueError(f"valor inválido: {v!r}") from exc


@csrf_exempt
@require_POST
def receber_medicoes(request):
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    medidor = Medidor.pelo_token(token)
    if medidor is None:
        return JsonResponse({"erro": "token inválido"}, status=401)
    try:
        corpo = json.loads(request.body or b"null")
    except json.JSONDecodeError:
        return JsonResponse({"erro": "JSON inválido"}, status=400)
    itens = corpo if isinstance(corpo, list) else [corpo]
    if not itens or len(itens) > MAX_POR_ENVIO or not all(isinstance(i, dict) for i in itens):
        return JsonResponse({"erro": f"envie de 1 a {MAX_POR_ENVIO} objetos"}, status=400)

    agora = timezone.now()
    objs = []
    try:
        for item in itens:
            momento = parse_datetime(item["momento"]) if item.get("momento") else agora
            if momento is None:
                raise ValueError("momento inválido")
            if timezone.is_naive(momento):
                momento = timezone.make_aware(momento)
            if momento > agora + datetime.timedelta(minutes=5):
                raise ValueError("momento no futuro")
            objs.append(MedicaoBruta(medidor=medidor, momento=momento.replace(microsecond=0),
                                     **{c: _dec(item.get(c)) for c in CAMPOS}))
    except (ValueError, TypeError) as exc:
        return JsonResponse({"erro": str(exc)}, status=400)

    MedicaoBruta.objects.bulk_create(objs, ignore_conflicts=True)
    Medidor.objects.filter(pk=medidor.pk).update(ultimo_contato=agora)
    return JsonResponse({"recebidas": len(objs), "intervalo_s": medidor.intervalo_envio_s}, status=201)
