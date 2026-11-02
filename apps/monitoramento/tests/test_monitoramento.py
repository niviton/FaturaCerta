import datetime
from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cadastro.models import Inversor, Medidor, Usina
from apps.integracoes.base import IntegracaoNaoConfigurada
from apps.integracoes.fake import FakeInversor, FakeMedidor
from apps.integracoes.inversores_reais import PROVEDORES_REAIS, SolarEdgeProvedor
from apps.integracoes.registro import notificador, provedor_inversor, provedor_medidor
from apps.monitoramento import services
from apps.monitoramento.models import GeracaoDiaria

pytestmark = pytest.mark.django_db


@pytest.fixture
def usina_a(uc_a):
    return Usina.objects.create(integradora=uc_a.integradora, nome="Usina A", uc_geradora=uc_a, potencia_kwp=10,
                                geracao_esperada_kwh=[1400] * 12)


def _inv(usina, **kw):
    return Inversor.objects.create(usina=usina, marca=kw.pop("marca", "Growatt"), numero_serie=kw.pop("serie", "S1"),
                                   **kw)


def test_fake_e_deterministico(usina_a):
    inv = _inv(usina_a)
    a = FakeInversor(inv).geracao_diaria(datetime.date(2026, 1, 1), datetime.date(2026, 1, 10))
    b = FakeInversor(inv).geracao_diaria(datetime.date(2026, 1, 1), datetime.date(2026, 1, 10))
    assert a == b and len(a) == 10
    media = sum(g.kwh for g in a) / 10
    assert Decimal(25) < media < Decimal(55)  # ~1400/30 kWh/dia com clima


def test_fake_cenario_parada_zera_geracao(usina_a):
    inv = _inv(usina_a, credenciais={"cenario": "parada", "desde": "2026-01-05"})
    g = FakeInversor(inv).geracao_diaria(datetime.date(2026, 1, 1), datetime.date(2026, 1, 8))
    assert all(x.kwh > 0 for x in g[:4]) and all(x.kwh == 0 for x in g[4:])


def test_provedor_real_sem_credenciais_cai_no_fake(usina_a):
    inv = _inv(usina_a, provedor_api="solaredge")
    assert isinstance(provedor_inversor(inv), FakeInversor)
    inv.credenciais, inv.id_externo = {"api_key": "x"}, "123"
    assert isinstance(provedor_inversor(inv), SolarEdgeProvedor)


@pytest.mark.parametrize("codigo", sorted(PROVEDORES_REAIS))
def test_todo_provedor_real_exige_credenciais(usina_a, codigo):
    inv = _inv(usina_a, provedor_api=codigo)
    with pytest.raises(IntegracaoNaoConfigurada):
        PROVEDORES_REAIS[codigo](inv)


def test_solaredge_mapeia_campos(usina_a):
    inv = _inv(usina_a, provedor_api="solaredge", credenciais={"api_key": "k"}, id_externo="99")
    resposta = {"energy": {"values": [{"date": "2026-01-01 00:00:00", "value": 41230.0},
                                      {"date": "2026-01-02 00:00:00", "value": None}]}}
    with mock.patch("apps.integracoes.inversores_reais.http_json", return_value=resposta):
        g = provedor_inversor(inv).geracao_diaria(datetime.date(2026, 1, 1), datetime.date(2026, 1, 2))
    assert len(g) == 1 and g[0].kwh == Decimal("41.23")


def test_medidor_e_notificador_fake(usina_a):
    _inv(usina_a)
    med = Medidor.objects.create(uc=usina_a.uc_geradora, usina=usina_a, fabricante="X", numero_serie="M1")
    assert isinstance(provedor_medidor(med), FakeMedidor)
    leituras = FakeMedidor(med).leituras_diarias(datetime.date(2026, 1, 1), datetime.date(2026, 1, 3))
    assert len(leituras) == 3 and all(x.exportacao_kwh >= 0 and x.importacao_kwh > 0 for x in leituras)
    assert all(x.carga_kwh is None for x in leituras)  # ponto "rede" não mede a carga
    med.provedor_api = "esp"
    assert isinstance(provedor_medidor(med), FakeMedidor)  # sem token: demonstração
    med.gerar_token()
    assert provedor_medidor(med).codigo == "esp"
    assert notificador("whatsapp").demo


def test_curva_do_dia_fake(usina_a):
    inv = _inv(usina_a)
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    n = services.coletar_curva(inv, ontem)
    assert n == 49  # 5h30 a 17h30, a cada 15 min
    pontos = services.curva_do_dia([usina_a], ontem)
    assert max(kw for _, kw in pontos) > 0


def test_coleta_e_geracao_no_periodo(usina_a):
    inv = _inv(usina_a)
    n = services.coletar_geracao(inv, dias=10)
    assert n == 10 and GeracaoDiaria.objects.filter(inversor=inv, demo=True).count() == 10
    hoje = timezone.localdate()
    total = services.geracao_no_periodo(usina_a, hoje - datetime.timedelta(days=9), hoje)
    assert total == sum(g.kwh for g in GeracaoDiaria.objects.filter(inversor=inv))


def test_resumo_detecta_parada_e_sem_comunicacao(usina_a, uc_a):
    _inv(usina_a, credenciais={"cenario": "parada"})
    services.coletar_status(usina_a.inversores.get())
    assert services.resumir_usina(usina_a).situacao == "parada"

    u2 = Usina.objects.create(integradora=uc_a.integradora, nome="U2", uc_geradora=uc_a, potencia_kwp=5)
    _inv(u2, serie="S2", credenciais={"cenario": "offline"})
    services.coletar_status(u2.inversores.get())
    assert services.resumir_usina(u2).situacao == "sem_comunicacao"


def test_resumo_detecta_abaixo_do_esperado(usina_a):
    inv = _inv(usina_a, credenciais={"cenario": "baixa", "fator": 0.5})
    services.coletar_geracao(inv, dias=10)
    services.coletar_status(inv)
    r = services.resumir_usina(usina_a)
    assert r.desempenho_7d < Decimal("0.8")
    assert r.situacao in ("abaixo", "parada")  # à noite com zero também pode ser parada? não: só de dia
    assert len(r.ultimos_dias) == 14


def test_painel_agrupa_por_cliente_e_isola_integradoras(client, gestor_a, usina_a, usina_b):
    _inv(usina_a, marca="Growatt")
    _inv(usina_a, marca="SolarEdge", serie="S9")
    Inversor.objects.create(usina=usina_b, marca="Fronius", numero_serie="B1")
    client.force_login(gestor_a)
    html = client.get(reverse("monitoramento:painel")).content.decode()
    assert "Usina A" in html and "Growatt + SolarEdge" in html
    assert "Usina B" not in html and "Fronius" not in html
    parcial = client.post(reverse("monitoramento:painel"), HTTP_HX_REQUEST="true").content.decode()
    assert 'id="lista"' in parcial and "<html" not in parcial


def test_seed_demo_roda(db):
    from django.core.management import call_command

    from apps.faturas.models import Fatura

    call_command("seed_demo", dias=5)
    assert Usina.objects.count() == 11
    assert Inversor.objects.filter(provedor_api="goodwe").count() == 3
    assert Fatura.objects.filter(status="divergente").exists()
    assert Fatura.objects.filter(status="conferida").exists()
