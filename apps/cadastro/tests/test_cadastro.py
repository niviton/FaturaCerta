import datetime

import pytest
from django.db import connection
from django.urls import reverse

from apps.cadastro.models import Inversor, LoteCredito, Rateio, UnidadeConsumidora, Usina
from apps.cadastro.requisitos import pendencias_cadastro_uc, status_regras
from apps.core.models import LogAuditoria
from apps.core.validators import cnpj_valido, cpf_valido

pytestmark = pytest.mark.django_db


def test_validadores_de_documento():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-26")
    assert not cpf_valido("111.111.111-11")
    assert cnpj_valido("11.222.333/0001-81")
    assert not cnpj_valido("11.222.333/0001-80")


@pytest.mark.parametrize("data,esperado", [
    (datetime.date(2022, 12, 1), "GD1"),
    (datetime.date(2023, 1, 7), "GD1"),
    (datetime.date(2023, 1, 8), "GD2"),
])
def test_enquadramento_automatico_pela_data(uc_a, data, esperado):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a, data_protocolo=data)
    assert u.enquadramento == esperado


def test_enquadramento_manual_e_aviso_de_divergencia(uc_a):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a,
                             data_protocolo=datetime.date(2024, 3, 1), enquadramento="GD1", enquadramento_manual=True)
    assert u.enquadramento == "GD1"
    assert u.enquadramento_divergente_da_data


def test_credenciais_ficam_cifradas_no_banco(uc_a):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a)
    inv = Inversor.objects.create(usina=u, marca="Growatt", credenciais={"token": "segredo-123"})
    with connection.cursor() as c:
        c.execute("select credenciais from cadastro_inversor where id = %s", [inv.pk])
        bruto = c.fetchone()[0]
    assert "segredo-123" not in bruto
    assert Inversor.objects.get(pk=inv.pk).credenciais == {"token": "segredo-123"}


def test_validade_do_lote_e_60_meses(uc_a):
    lote = LoteCredito.objects.create(uc=uc_a, mes_referencia=datetime.date(2024, 2, 1), kwh_gerado=100,
                                      kwh_saldo=100)
    assert lote.validade == datetime.date(2029, 2, 1)


def test_custo_disponibilidade_por_ligacao(uc_a):
    assert uc_a.custo_disponibilidade_kwh == 100
    uc_a.tipo_ligacao = "mono"
    assert uc_a.custo_disponibilidade_kwh == 30


def test_uc_grupo_b_nao_aceita_modalidade_azul(uc_a):
    from django.core.exceptions import ValidationError

    uc_a.modalidade_tarifaria = "azul"
    with pytest.raises(ValidationError):
        uc_a.full_clean()


def test_regras_desligadas_por_falta_de_dado(uc_a):
    regras = {r.codigo: r for r in status_regras(uc_a)}
    assert not regras["injecao_nao_compensada"].ativa
    assert regras["demanda"].nao_se_aplica
    assert regras["cip"].ativa
    assert "vínculo com uma usina (geradora ou beneficiária)" in pendencias_cadastro_uc(uc_a)

    Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a,
                         data_protocolo=datetime.date(2024, 1, 1))
    regras = {r.codigo: r for r in status_regras(uc_a)}
    assert regras["injecao_nao_compensada"].ativa
    assert regras["fio_b_gd2"].ativa
    assert not regras["constante_medidor"].ativa


def test_cria_usina_com_rateio_que_soma_100(client, gestor_a, uc_a, cosern):
    uc2 = UnidadeConsumidora.objects.create(integradora=uc_a.integradora, cliente=uc_a.cliente,
                                            concessionaria=cosern, numero_uc="999")
    client.force_login(gestor_a)
    base = {"nome": "Usina Rateada", "uc_geradora": uc_a.pk, "tipo": "autoconsumo_remoto", "ativa": "on",
            "data_protocolo": "2024-05-10",
            "rateios-TOTAL_FORMS": "2", "rateios-INITIAL_FORMS": "0",
            "rateios-0-uc": uc_a.pk, "rateios-0-percentual": "60",
            "rateios-1-uc": uc2.pk, "rateios-1-percentual": "30"}
    resp = client.post(reverse("cadastro:usina_nova"), base)
    assert resp.status_code == 200 and "100%" in resp.content.decode()

    base["rateios-1-percentual"] = "40"
    for i, m in enumerate(["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]):
        base[f"esp_{m}"] = str(500 + i)
    resp = client.post(reverse("cadastro:usina_nova"), base)
    assert resp.status_code == 302
    u = Usina.objects.get(nome="Usina Rateada")
    assert u.enquadramento == "GD2"
    assert len(u.geracao_esperada_kwh) == 12
    assert Rateio.objects.filter(usina=u).count() == 2


def test_consentimento_registra_ip_e_versao(client, gestor_a, cliente_a):
    client.force_login(gestor_a)
    client.post(reverse("cadastro:consentimento", args=[cliente_a.pk]), {"versao_termo": "2.1", "aceito": "on"},
                REMOTE_ADDR="10.1.2.3")
    c = cliente_a.consentimento_vigente
    assert c.versao_termo == "2.1" and c.ip == "10.1.2.3" and c.registrado_por == gestor_a


def test_visualizacao_e_edicao_geram_log(client, gestor_a, cliente_a):
    client.force_login(gestor_a)
    client.get(reverse("cadastro:cliente", args=[cliente_a.pk]))
    client.post(reverse("cadastro:cliente_editar", args=[cliente_a.pk]),
                {"nome": "Padaria Nova", "documento": cliente_a.documento, "ativo": "on"})
    acoes = list(LogAuditoria.objects.filter(usuario=gestor_a).values_list("acao", flat=True))
    assert "ver" in acoes and "alterar" in acoes


def test_paginas_do_cadastro_renderizam(client, gestor_a, uc_a):
    u = Usina.objects.create(integradora=uc_a.integradora, nome="U", uc_geradora=uc_a)
    client.force_login(gestor_a)
    for url in [reverse("cadastro:clientes"), reverse("cadastro:cliente_novo"),
                reverse("cadastro:cliente", args=[uc_a.cliente_id]), reverse("cadastro:uc", args=[uc_a.pk]),
                reverse("cadastro:uc_nova"), reverse("cadastro:usina", args=[u.pk]),
                reverse("cadastro:usina_nova"), reverse("cadastro:usina_editar", args=[u.pk]),
                reverse("cadastro:inversor_novo", args=[u.pk]), reverse("cadastro:medidor_novo", args=[u.pk])]:
        assert client.get(url).status_code == 200, url
