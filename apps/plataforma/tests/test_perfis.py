"""Três níveis de acesso: administrador geral, integradora e cliente final."""

import datetime
import json
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.analise.services import balanco_periodo
from apps.cadastro.models import Inversor, Medidor, Usina
from apps.faturas.models import Fatura
from apps.monitoramento import services
from apps.monitoramento.models import LeituraMedidor, MedicaoBruta

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_geral(db):
    return User.objects.create_user("adm", password="x-senha-forte-1", papel=User.Papel.ADMIN_INTERNO)


@pytest.fixture
def cli_user(cliente_a, integradora_a):
    return User.objects.create_user("cli", password="x-senha-forte-1", papel=User.Papel.CLIENTE,
                                    integradora=integradora_a, cliente=cliente_a)


# ---------------------------------------------------------------- administrador geral

def test_admin_ve_plataforma_e_todas_as_integradoras(client, admin_geral, usina_b, uc_a):
    client.force_login(admin_geral)
    assert client.get(reverse("home")).url == reverse("plataforma:visao")
    for nome in ["visao", "integradoras", "usuarios", "integracoes", "logs", "integradora_nova", "usuario_novo"]:
        assert client.get(reverse(f"plataforma:{nome}")).status_code == 200, nome
    html = client.get(reverse("plataforma:visao")).content.decode()
    assert "Solar A" in html and "Solar B" in html


def test_admin_precisa_escolher_integradora_para_o_painel(client, admin_geral, integradora_a):
    client.force_login(admin_geral)
    assert client.get(reverse("cadastro:clientes")).url == reverse("plataforma:integradoras")


def test_admin_atua_como_integradora_e_volta(client, admin_geral, integradora_a, cliente_a, cliente_b):
    client.force_login(admin_geral)
    client.post(reverse("plataforma:atuar", args=[integradora_a.pk]))
    html = client.get(reverse("cadastro:clientes")).content.decode()
    assert "Padaria A" in html and "Mercado B" not in html
    assert client.get(reverse("cadastro:cliente", args=[cliente_b.pk])).status_code == 404
    client.post(reverse("plataforma:sair_atuacao"))
    assert client.get(reverse("cadastro:clientes")).status_code == 302


def test_admin_edita_credenciais_e_testa_conexao(client, admin_geral, usina_b):
    inv = Inversor.objects.create(usina=usina_b, marca="Growatt", numero_serie="S1")
    client.force_login(admin_geral)
    assert client.get(reverse("plataforma:inversor", args=[inv.pk])).status_code == 200
    resp = client.post(reverse("plataforma:testar", args=[inv.pk]))
    assert "Conectou" in resp.content.decode()


def test_admin_cria_gestor_de_integradora(client, admin_geral, integradora_b):
    client.force_login(admin_geral)
    resp = client.post(reverse("plataforma:usuario_novo"), {
        "username": "novo_gestor", "senha": "Senha-Forte-2026", "papel": "gestor",
        "integradora": integradora_b.pk, "is_active": "on", "first_name": "Novo"})
    assert resp.status_code == 302
    u = User.objects.get(username="novo_gestor")
    assert u.integradora == integradora_b and u.check_password("Senha-Forte-2026")


def test_equipe_nao_acessa_plataforma(client, gestor_a, cli_user):
    for u in (gestor_a, cli_user):
        client.force_login(u)
        assert client.get(reverse("plataforma:visao")).status_code == 403


# ---------------------------------------------------------------- manuais

def test_manuais_por_perfil(client, admin_geral, gestor_a, tecnico_a, cli_user):
    from apps.core.manuais import MANUAIS

    if not all(m.arquivo.exists() for m in MANUAIS.values()):
        pytest.skip("PDFs não gerados (python manage.py gerar_manuais)")
    client.force_login(admin_geral)
    html = client.get(reverse("manuais")).content.decode()
    assert "Manual do administrador geral" in html and "Manual da integradora" in html
    for codigo in ("administrador", "integradora"):
        r = client.get(reverse("manual_pdf", args=[codigo]))
        assert r.status_code == 200 and r["Content-Type"] == "application/pdf"

    for u in (gestor_a, tecnico_a):
        client.force_login(u)
        html = client.get(reverse("manuais")).content.decode()
        assert "Manual da integradora" in html and "Manual do administrador geral" not in html
        assert client.get(reverse("manual_pdf", args=["integradora"])).status_code == 200
        assert client.get(reverse("manual_pdf", args=["administrador"])).status_code == 404

    client.force_login(cli_user)
    assert client.get(reverse("manuais")).status_code == 404
    assert client.get(reverse("manual_pdf", args=["integradora"])).status_code == 404


# ---------------------------------------------------------------- integradora

def test_gestor_nao_cria_admin_nem_usuario_de_outra_integradora(client, gestor_a, integradora_b, cliente_b):
    client.force_login(gestor_a)
    client.post(reverse("equipe:novo"), {"username": "x1", "senha": "Senha-Forte-2026", "papel": "admin",
                                         "is_active": "on"})
    assert not User.objects.filter(username="x1").exists()
    client.post(reverse("equipe:novo"), {"username": "x2", "senha": "Senha-Forte-2026", "papel": "cliente",
                                         "cliente": cliente_b.pk, "is_active": "on"})
    assert not User.objects.filter(username="x2").exists()
    client.post(reverse("equipe:novo"), {"username": "x3", "senha": "Senha-Forte-2026", "papel": "tecnico",
                                         "is_active": "on"})
    assert User.objects.get(username="x3").integradora == gestor_a.integradora


def test_gestor_cria_acesso_ao_portal_para_cliente(client, gestor_a, cliente_a):
    client.force_login(gestor_a)
    client.post(reverse("cadastro:acesso_portal", args=[cliente_a.pk]),
                {"username": "padaria", "senha": "Senha-Forte-2026", "email": ""})
    u = User.objects.get(username="padaria")
    assert u.is_cliente_final and u.cliente == cliente_a


# ---------------------------------------------------------------- cliente final

def test_cliente_ve_so_as_proprias_usinas(client, cli_user, uc_a, usina_b):
    minha = Usina.objects.create(integradora=uc_a.integradora, nome="Minha usina", uc_geradora=uc_a, potencia_kwp=5)
    Inversor.objects.create(usina=minha, marca="Growatt", numero_serie="S1")
    client.force_login(cli_user)
    assert client.get(reverse("home")).url == reverse("portal:inicio")
    html = client.get(reverse("portal:inicio")).content.decode()
    assert "Minha usina" in html and "Usina B" not in html
    assert client.get(reverse("portal:usina", args=[minha.pk])).status_code == 200
    assert client.get(reverse("portal:usina", args=[usina_b.pk])).status_code == 404
    assert client.get(reverse("cadastro:clientes")).status_code == 403
    assert client.get(reverse("painel:visao")).status_code == 403


# ---------------------------------------------------------------- API do ESP

def test_api_esp_recebe_e_consolida(client, uc_a):
    m = Medidor.objects.create(uc=uc_a, provedor_api="esp")
    token = m.gerar_token()
    url = reverse("api_medicoes")
    assert client.post(url, "{}", content_type="application/json").status_code == 401
    agora = timezone.localtime().replace(minute=0, second=0, microsecond=0)
    if agora.hour < 2:
        agora += datetime.timedelta(hours=2)
    corpo = [
        {"momento": (agora - datetime.timedelta(hours=1)).isoformat(), "importacao_kwh": 100, "exportacao_kwh": 50},
        {"momento": agora.isoformat(), "importacao_kwh": 104.5, "exportacao_kwh": 58.25, "potencia_w": -800},
    ]
    resp = client.post(url, json.dumps(corpo), content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert resp.status_code == 201 and resp.json()["recebidas"] == 2
    assert MedicaoBruta.objects.filter(medidor=m).count() == 2
    services.consolidar_medicoes(m, dias=1)
    leitura = LeituraMedidor.objects.get(medidor=m, data=agora.date())
    assert leitura.importacao_kwh == Decimal("4.50") and leitura.exportacao_kwh == Decimal("8.25")
    m.refresh_from_db()
    assert m.ultimo_contato is not None
    ruim = client.post(url, json.dumps({"importacao_kwh": "abc"}), content_type="application/json",
                       HTTP_AUTHORIZATION=f"Bearer {token}")
    assert ruim.status_code == 400


# ---------------------------------------------------------------- análise das três fontes

def _fatura(uc, **kw):
    base = dict(integradora=uc.integradora, uc=uc, mes_referencia=datetime.date(2026, 1, 1),
                data_leitura_anterior=datetime.date(2025, 12, 10), data_leitura_atual=datetime.date(2026, 1, 10),
                consumo_kwh=Decimal(500), energia_injetada_kwh=Decimal(300), energia_compensada_kwh=Decimal(300),
                valor_total=Decimal(200))
    base.update(kw)
    return Fatura.objects.create(**base)


def _leituras(m, ini, fim, imp, exp):
    dia = ini
    while dia <= fim:
        LeituraMedidor.objects.create(medidor=m, data=dia, importacao_kwh=imp, exportacao_kwh=exp)
        dia += datetime.timedelta(days=1)


def test_balanco_detecta_consumo_faturado_acima_do_medido(uc_a):
    m = Medidor.objects.create(uc=uc_a)
    ini, fim = datetime.date(2025, 12, 11), datetime.date(2026, 1, 10)
    _leituras(m, ini, fim, Decimal("12.9"), Decimal("9.68"))  # 31 dias: ~400 kWh importados, ~300 exportados
    f = _fatura(uc_a)
    b = balanco_periodo(uc_a, ini, fim, f)
    codigos = {i.codigo for i in b.indicios}
    assert "consumo_diverge_medidor" in codigos
    assert any("constante" in i.detalhe for i in b.indicios if i.codigo == "consumo_diverge_medidor")
    assert "injecao_diverge_medidor" not in codigos


def test_balanco_detecta_injecao_nao_compensada_e_autoconsumo(uc_a):
    from apps.monitoramento.models import GeracaoDiaria

    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a, potencia_kwp=10)
    inv = Inversor.objects.create(usina=u, marca="X", numero_serie="S")
    ini, fim = datetime.date(2025, 12, 11), datetime.date(2026, 1, 10)
    dia = ini
    while dia <= fim:
        GeracaoDiaria.objects.create(inversor=inv, data=dia, kwh=Decimal(20))
        dia += datetime.timedelta(days=1)
    f = _fatura(uc_a, energia_compensada_kwh=Decimal(0), custo_disponibilidade_kwh=100)
    b = balanco_periodo(uc_a, ini, fim, f)
    assert b.geracao_kwh == Decimal(620) and b.autoconsumo_kwh == Decimal(320)
    assert b.consumo_real_kwh == Decimal(820)
    assert "injecao_nao_compensada" in {i.codigo for i in b.indicios}


def test_balanco_detecta_injecao_maior_que_geracao(uc_a):
    from apps.monitoramento.models import GeracaoDiaria

    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a, potencia_kwp=10)
    inv = Inversor.objects.create(usina=u, marca="X", numero_serie="S")
    GeracaoDiaria.objects.create(inversor=inv, data=datetime.date(2026, 1, 1), kwh=Decimal(100))
    f = _fatura(uc_a)
    b = balanco_periodo(uc_a, datetime.date(2025, 12, 11), datetime.date(2026, 1, 10), f)
    assert "injecao_maior_que_geracao" in {i.codigo for i in b.indicios}
