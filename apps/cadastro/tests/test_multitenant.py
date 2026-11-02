"""Nenhum dado pode vazar entre integradoras."""

import pytest
from django.urls import reverse

from apps.cadastro.models import Inversor, UnidadeConsumidora, Usina

pytestmark = pytest.mark.django_db


def test_lista_de_clientes_mostra_so_os_da_integradora(client, gestor_a, cliente_a, cliente_b):
    client.force_login(gestor_a)
    html = client.get(reverse("cadastro:clientes")).content.decode()
    assert "Padaria A" in html
    assert "Mercado B" not in html


@pytest.mark.parametrize("rota", ["cadastro:cliente", "cadastro:cliente_editar", "cadastro:consentimento"])
def test_cliente_de_outra_integradora_da_404(client, gestor_a, cliente_b, rota):
    client.force_login(gestor_a)
    metodo = client.post if rota == "cadastro:consentimento" else client.get
    assert metodo(reverse(rota, args=[cliente_b.pk])).status_code == 404


@pytest.mark.parametrize("rota", ["cadastro:uc", "cadastro:uc_editar", "cadastro:lote_novo"])
def test_uc_de_outra_integradora_da_404(client, gestor_a, uc_b, rota):
    client.force_login(gestor_a)
    metodo = client.post if rota == "cadastro:lote_novo" else client.get
    assert metodo(reverse(rota, args=[uc_b.pk])).status_code == 404


def test_usina_e_equipamentos_de_outra_integradora_dao_404(client, gestor_a, usina_b):
    inv = Inversor.objects.create(usina=usina_b, marca="Growatt", credenciais={"token": "segredo"})
    client.force_login(gestor_a)
    assert client.get(reverse("cadastro:usina", args=[usina_b.pk])).status_code == 404
    assert client.get(reverse("cadastro:usina_editar", args=[usina_b.pk])).status_code == 404
    assert client.get(reverse("cadastro:inversor_novo", args=[usina_b.pk])).status_code == 404
    assert client.get(reverse("cadastro:inversor_editar", args=[usina_b.pk, inv.pk])).status_code == 404
    assert client.post(reverse("cadastro:inversor_novo", args=[usina_b.pk]), {"marca": "X", "provedor_api": "fake"}
                       ).status_code == 404


def test_medidor_de_outra_integradora_da_404(client, gestor_a, uc_b):
    from apps.cadastro.models import Medidor

    m = Medidor.objects.create(uc=uc_b)
    client.force_login(gestor_a)
    assert client.get(reverse("cadastro:medidor_novo", args=[uc_b.pk])).status_code == 404
    assert client.get(reverse("cadastro:medidor_editar", args=[uc_b.pk, m.pk])).status_code == 404
    assert client.get(reverse("cadastro:medidor_token", args=[uc_b.pk, m.pk])).status_code == 404


def test_faturas_isoladas(client, gestor_a, uc_b):
    import datetime

    from apps.faturas.models import Fatura

    f = Fatura.objects.create(integradora=uc_b.integradora, uc=uc_b, mes_referencia=datetime.date(2026, 1, 1),
                              data_leitura_anterior=datetime.date(2025, 12, 10),
                              data_leitura_atual=datetime.date(2026, 1, 10), consumo_kwh=100, valor_total=90)
    client.force_login(gestor_a)
    assert "7000000001" not in client.get(reverse("faturas:lista")).content.decode()
    assert client.get(reverse("faturas:editar", args=[f.pk])).status_code == 404


def test_nao_cria_uc_para_cliente_de_outra_integradora(client, gestor_a, cliente_b, cosern):
    client.force_login(gestor_a)
    resp = client.post(reverse("cadastro:uc_nova"), {
        "cliente": cliente_b.pk, "concessionaria": cosern.pk, "numero_uc": "123", "grupo": "B",
        "modalidade_tarifaria": "convencional", "ativa": "on",
    })
    assert resp.status_code == 200  # formulário volta com erro
    assert not UnidadeConsumidora.objects.filter(numero_uc="123").exists()


def test_rateio_nao_aceita_uc_de_outra_integradora(client, gestor_a, uc_a, uc_b):
    client.force_login(gestor_a)
    resp = client.post(reverse("cadastro:usina_nova"), {
        "nome": "Usina A", "uc_geradora": uc_a.pk, "tipo": "junto_carga", "ativa": "on",
        "rateios-TOTAL_FORMS": "1", "rateios-INITIAL_FORMS": "0",
        "rateios-0-uc": uc_b.pk, "rateios-0-percentual": "100",
    })
    assert resp.status_code == 200
    assert not Usina.objects.filter(nome="Usina A").exists()


def test_cliente_final_e_anonimo_nao_acessam_painel(client, cliente_a, integradora_a):
    from apps.accounts.models import User

    assert client.get(reverse("cadastro:clientes")).status_code == 302  # login
    u = User.objects.create_user("cli", password="x-senha-123", papel=User.Papel.CLIENTE,
                                 integradora=integradora_a, cliente=cliente_a)
    client.force_login(u)
    assert client.get(reverse("cadastro:clientes")).status_code == 403


def test_tecnico_nao_edita_integradora(client, tecnico_a, gestor_a):
    client.force_login(tecnico_a)
    assert client.get(reverse("cadastro:integradora")).status_code == 403
    client.force_login(gestor_a)
    assert client.get(reverse("cadastro:integradora")).status_code == 200
