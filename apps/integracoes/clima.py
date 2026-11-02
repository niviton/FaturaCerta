"""Clima real (irradiação solar) para a demonstração.

Fonte: Open-Meteo, sem chave. ATENÇÃO: gratuito só para uso NÃO comercial. Em produção comercial,
contratar o plano pago do Open-Meteo ou trocar a fonte (PVGIS, INMET). Desligue com CLIMA_PROVIDER="".

- Histórico diário: archive-api (até ontem).
- Hoje e últimos dias, hora a hora: forecast api.
Os dados ficam no banco (ClimaDiario/ClimaHorario) por região de 0,1°, e em memória por alguns minutos,
para o gerador fictício consultar milhares de dias sem tocar na rede.

Usamos a irradiação horizontal (shortwave_radiation). Perto do equador, com módulos a ~10°, a diferença para
o plano inclinado é de poucos por cento.
"""

import datetime
import logging
import time
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .base import ErroIntegracao
from .inversores_reais import http_json
from .models import ClimaDiario, ClimaHorario

log = logging.getLogger(__name__)

URL_ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
URL_PREVISAO = "https://api.open-meteo.com/v1/forecast"
FUSO = "America/Fortaleza"
MJ_PARA_KWH = Decimal("3.6")
VALIDADE_CACHE_S = 600

_cache: dict[tuple[Decimal, Decimal], tuple[float, dict, dict]] = {}


def ativo() -> bool:
    return getattr(settings, "CLIMA_PROVIDER", "") == "openmeteo"


def regiao(lat, lon) -> tuple[Decimal, Decimal]:
    return Decimal(str(lat)).quantize(Decimal("0.1")), Decimal(str(lon)).quantize(Decimal("0.1"))


def local_da_usina(usina) -> tuple[Decimal, Decimal]:
    uc = usina.uc_geradora
    for lat, lon in ((usina.latitude, usina.longitude), (uc.latitude, uc.longitude)):
        if lat is not None and lon is not None:
            return regiao(lat, lon)
    return regiao(*settings.CLIMA_LOCAL_PADRAO)


def limpar_cache():
    _cache.clear()


def _carregar(lat, lon):
    chave = (lat, lon)
    agora = time.monotonic()
    item = _cache.get(chave)
    if item and agora - item[0] < VALIDADE_CACHE_S:
        return item[1], item[2]
    diario = dict(ClimaDiario.objects.filter(lat=lat, lon=lon).values_list("data", "irradiacao_kwh_m2"))
    desde = timezone.now() - datetime.timedelta(days=3)
    horario = {timezone.localtime(m).replace(minute=0, second=0, microsecond=0): w for m, w in
               ClimaHorario.objects.filter(lat=lat, lon=lon, momento__gte=desde).values_list(
                   "momento", "irradiancia_w_m2")}
    _cache[chave] = (agora, diario, horario)
    return diario, horario


def irradiacao_dia(local, dia: datetime.date) -> float | None:
    """kWh/m² no dia, ou None se não houver dado real."""
    if not ativo():
        return None
    v = _carregar(*local)[0].get(dia)
    return float(v) if v is not None else None


def irradiancia_hora(local, momento: datetime.datetime) -> float | None:
    """W/m² médio da hora que contém `momento`, ou None."""
    if not ativo():
        return None
    m = timezone.localtime(momento).replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
    v = _carregar(*local)[1].get(m)
    return float(v) if v is not None else None


def tem_horario_hoje(local) -> bool:
    if not ativo():
        return False
    hoje = timezone.localdate()
    return any(m.date() == hoje for m in _carregar(*local)[1])


def atualizar(lat, lon, dias: int = 3) -> tuple[int, int]:
    """Busca o clima da região e grava no banco. Devolve (dias gravados, horas gravadas)."""
    lat, lon = regiao(lat, lon)
    hoje = timezone.localdate()
    comum = {"latitude": str(lat), "longitude": str(lon), "timezone": FUSO}
    dias_gravados = horas = 0
    try:
        if dias > 2:
            r = http_json("GET", URL_ARQUIVO, params={**comum, "daily": "shortwave_radiation_sum",
                                                      "start_date": (hoje - datetime.timedelta(days=dias)).isoformat(),
                                                      "end_date": (hoje - datetime.timedelta(days=1)).isoformat()})
            dias_gravados += _gravar_diario(lat, lon, r, "open-meteo-arquivo")
        r = http_json("GET", URL_PREVISAO, params={**comum, "daily": "shortwave_radiation_sum",
                                                   "hourly": "shortwave_radiation", "past_days": 2,
                                                   "forecast_days": 1})
        dias_gravados += _gravar_diario(lat, lon, r, "open-meteo")
        horas += _gravar_horario(lat, lon, r)
    except (ErroIntegracao, KeyError, TypeError, ValueError) as exc:
        log.warning("Clima (%s, %s) indisponível: %s", lat, lon, exc)
        raise ErroIntegracao(f"Open-Meteo indisponível: {exc}") from exc
    _cache.pop((lat, lon), None)
    return dias_gravados, horas


def _gravar_diario(lat, lon, r, fonte) -> int:
    d = r["daily"]
    objs = [ClimaDiario(lat=lat, lon=lon, data=datetime.date.fromisoformat(t),
                        irradiacao_kwh_m2=(Decimal(str(v)) / MJ_PARA_KWH).quantize(Decimal("0.001")), fonte=fonte)
            for t, v in zip(d["time"], d["shortwave_radiation_sum"], strict=False) if v is not None]
    ClimaDiario.objects.bulk_create(objs, update_conflicts=True, unique_fields=["lat", "lon", "data"],
                                    update_fields=["irradiacao_kwh_m2", "fonte"])
    return len(objs)


def _gravar_horario(lat, lon, r) -> int:
    h = r["hourly"]
    tz = timezone.get_current_timezone()
    objs = [ClimaHorario(lat=lat, lon=lon, momento=datetime.datetime.fromisoformat(t).replace(tzinfo=tz),
                         irradiancia_w_m2=Decimal(str(v)))
            for t, v in zip(h["time"], h["shortwave_radiation"], strict=False) if v is not None]
    ClimaHorario.objects.bulk_create(objs, update_conflicts=True, unique_fields=["lat", "lon", "momento"],
                                     update_fields=["irradiancia_w_m2"])
    return len(objs)


def regioes_em_uso():
    from apps.cadastro.models import Usina

    return {local_da_usina(u) for u in Usina.objects.filter(ativa=True).select_related("uc_geradora")}


def atualizar_todas(dias: int = 3) -> dict:
    """Atualiza todas as regiões com usinas. Falhas de rede não interrompem as demais."""
    out = {}
    for lat, lon in regioes_em_uso():
        try:
            out[(lat, lon)] = atualizar(lat, lon, dias)
        except ErroIntegracao as exc:
            out[(lat, lon)] = str(exc)
    return out


def ha_clima_real() -> bool:
    return ativo() and ClimaDiario.objects.exists()
