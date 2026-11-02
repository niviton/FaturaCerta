import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.utils import timezone

from apps.cadastro.models import Inversor, Usina
from apps.integracoes import clima
from apps.integracoes.fake import FakeInversor
from apps.integracoes.models import ClimaDiario, ClimaHorario

pytestmark = pytest.mark.django_db


@pytest.fixture
def com_clima(settings):
    settings.CLIMA_PROVIDER = "openmeteo"
    clima.limpar_cache()


@pytest.fixture
def usina(uc_a):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a, potencia_kwp=10,
                             latitude=Decimal("-5.795"), longitude=Decimal("-35.209"),
                             performance_ratio=Decimal("0.80"))
    Inversor.objects.create(usina=u, marca="Growatt", numero_serie="S1")
    return u


def _resposta(hoje):
    dias = [hoje - datetime.timedelta(days=n) for n in (2, 1, 0)]
    horas = [f"{hoje.isoformat()}T{h:02d}:00" for h in range(24)]
    w = [0] * 6 + [100, 300, 500, 700, 800, 900, 900, 800, 700, 500, 300, 100] + [0] * 6
    return {"daily": {"time": [d.isoformat() for d in dias], "shortwave_radiation_sum": [18.0, 21.6, 25.2]},
            "hourly": {"time": horas, "shortwave_radiation": w}}


def test_atualizar_grava_diario_e_horario(com_clima):
    hoje = timezone.localdate()
    with mock.patch("apps.integracoes.clima.http_json", return_value=_resposta(hoje)) as m:
        dias, horas = clima.atualizar(-5.795, -35.209, dias=1)
    assert m.call_count == 1  # dias <= 2: só a previsão
    assert (dias, horas) == (3, 24)
    d = ClimaDiario.objects.get(data=hoje - datetime.timedelta(days=1))
    assert (d.lat, d.lon) == (Decimal("-5.8"), Decimal("-35.2"))
    assert d.irradiacao_kwh_m2 == Decimal("6.000")  # 21,6 MJ/m² ÷ 3,6
    assert ClimaHorario.objects.count() == 24


def test_fake_usa_irradiacao_real(com_clima, usina):
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    ClimaDiario.objects.create(lat=Decimal("-5.8"), lon=Decimal("-35.2"), data=ontem,
                               irradiacao_kwh_m2=Decimal("6.000"))
    f = FakeInversor(usina.inversores.get())
    assert f.usa_clima_real
    # 10 kWp × 6 kWh/m² × PR 0,80 = 48 kWh (± ruído de até 3%)
    assert 46.5 < f.kwh_do_dia(ontem) < 49.0


def test_dia_nublado_gera_menos(com_clima, usina):
    hoje = timezone.localdate()
    d1, d2 = hoje - datetime.timedelta(days=3), hoje - datetime.timedelta(days=2)
    ClimaDiario.objects.create(lat=Decimal("-5.8"), lon=Decimal("-35.2"), data=d1, irradiacao_kwh_m2=Decimal("2.2"))
    ClimaDiario.objects.create(lat=Decimal("-5.8"), lon=Decimal("-35.2"), data=d2, irradiacao_kwh_m2=Decimal("7.0"))
    f = FakeInversor(usina.inversores.get())
    assert f.kwh_do_dia(d1) < f.kwh_do_dia(d2) * 0.4


def test_potencia_segue_irradiancia_horaria(com_clima, usina):
    hoje = timezone.localdate()
    with mock.patch("apps.integracoes.clima.http_json", return_value=_resposta(hoje)):
        clima.atualizar(-5.795, -35.209, dias=1)
    f = FakeInversor(usina.inversores.get())
    tz = timezone.get_current_timezone()
    # média da hora 11h-12h = 900 W/m² (registro das 12:00); às 11:30 a interpolação dá exatamente esse valor
    meio = datetime.datetime.combine(hoje, datetime.time(11, 30), tzinfo=tz)
    assert f.potencia_em(meio) == pytest.approx(10 * 0.9 * 0.8)
    noite = datetime.datetime.combine(hoje, datetime.time(2, 0), tzinfo=tz)
    assert f.potencia_em(noite) == 0


def test_sem_clima_usa_modelo_sintetico(usina):
    f = FakeInversor(usina.inversores.get())
    assert not f.usa_clima_real
    assert f.kwh_do_dia(timezone.localdate() - datetime.timedelta(days=1)) > 0


def test_falha_de_rede_nao_quebra_atualizacao_geral(com_clima, usina):
    from apps.integracoes.base import ErroIntegracao

    with mock.patch("apps.integracoes.clima.http_json", side_effect=ErroIntegracao("sem rede")):
        r = clima.atualizar_todas(3)
    assert all(isinstance(v, str) for v in r.values())


def test_local_da_usina_cai_na_uc_e_no_padrao(uc_a, settings):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a)
    assert clima.local_da_usina(u) == clima.regiao(*settings.CLIMA_LOCAL_PADRAO)
    uc_a.latitude, uc_a.longitude = Decimal("-6.459"), Decimal("-37.098")
    uc_a.save()
    u.refresh_from_db()
    assert clima.local_da_usina(u) == (Decimal("-6.5"), Decimal("-37.1"))
