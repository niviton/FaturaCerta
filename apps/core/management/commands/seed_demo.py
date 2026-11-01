"""Dados de demonstração. Uso: python manage.py seed_demo [--dias 120] [--limpar]

Nesta fase gera integradora, usuários, os 6 clientes com usinas de fabricantes diferentes e o
histórico de geração. Faturas fictícias entram junto com o leitor de PDF.
"""

import datetime

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.cadastro.models import (
    Cliente,
    Concessionaria,
    ConsentimentoLGPD,
    Inversor,
    Medidor,
    Rateio,
    UnidadeConsumidora,
    Usina,
)
from apps.core.models import Integradora
from apps.monitoramento import tasks

SENHA = "FaturaCerta@2026"


def _dv(base, pesos):
    r = sum(int(a) * b for a, b in zip(base, pesos, strict=False)) % 11
    return "0" if r < 2 else str(11 - r)


def cnpj(base12: str) -> str:
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    b = base12 + _dv(base12, p1)
    return b + _dv(b, [6] + p1)


def cpf(base9: str) -> str:
    v1 = sum(int(base9[i]) * (10 - i) for i in range(9)) * 10 % 11 % 10
    b = base9 + str(v1)
    v2 = sum(int(b[i]) * (11 - i) for i in range(10)) * 10 % 11 % 10
    return b + str(v2)


def esperada(kwp):
    # perfil de Natal: kWh/mês por kWp (aprox.)
    perfil = [140, 128, 136, 120, 116, 106, 114, 131, 140, 150, 147, 146]
    return [round(kwp * v) for v in perfil]


# (cliente, documento, ucs, usinas)
# usina: (nome, uc_idx, kwp, protocolo, [(marca, modelo, provedor, credenciais)], medidor?)
CLIENTES = [
    ("Padaria Sol Nascente", cnpj("123456780001"), [("7010453067", "B3", "tri", "Natal")], [
        ("Padaria · telhado", 0, 18.6, "2022-08-10", [("Growatt", "MID 15KTL3-X", "growatt", {})], False),
        ("Padaria · ampliação", 0, 8.2, "2023-09-02", [("SolarEdge", "SE8K", "solaredge", {})], False),
    ]),
    ("Clínica Boa Vista", cnpj("234567890001"), [("7020111222", "B3", "tri", "Natal")], [
        ("Clínica Boa Vista", 0, 22.0, "2023-06-15", [("Huawei", "SUN2000-20KTL-M2", "huawei", {})], False),
    ]),
    ("Oficina Potengi", cnpj("345678900001"), [("7030222333", "B3", "tri", "Natal")], [
        ("Oficina Potengi", 0, 12.4, "2022-11-20", [("Fronius", "Symo 12.5-3-M", "fronius", {})], True),
    ]),
    ("Supermercado Pajuçara", cnpj("456789010001"), [("7040333444", "A4", "", "Natal")], [
        ("Pajuçara · cobertura", 0, 75.0, "2022-10-01",
         [("GoodWe", "GW50K-MT", "goodwe", {}), ("GoodWe", "GW25K-MT", "goodwe", {})], True),
        ("Pajuçara · estacionamento", 0, 40.0, "2024-02-19",
         [("Deye", "SUN-40K-G03", "deye", {"cenario": "baixa", "fator": 0.62})], False),
    ]),
    ("Escola Nova Era", cnpj("567890120001"), [("7050444555", "B3", "tri", "Parnamirim")], [
        ("Escola Nova Era", 0, 30.0, "2023-03-30",
         [("Deye", "SUN-30K-G04", "deye", {"cenario": "parada", "desde": "__parada__"})], False),
    ]),
    ("Residência Lima", cpf("390533447"), [("7060555666", "B1", "bi", "Natal"), ("7060555777", "B1", "mono", "Natal")], [
        ("Casa Lima", 0, 6.1, "2022-05-12", [("Growatt", "MIN 5000TL-X", "growatt", {})], False),
        ("Casa de praia Lima", 1, 4.4, "2024-07-08", [("Huawei", "SUN2000-4KTL-L1", "huawei", {"cenario": "offline"})],
         False),
    ]),
]


class Command(BaseCommand):
    help = "Cria dados de demonstração (integradora, usuários, clientes, usinas e geração)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=120)
        parser.add_argument("--limpar", action="store_true", help="Apaga a integradora de demonstração antes.")

    @transaction.atomic
    def handle(self, *args, dias, limpar, **opts):
        doc_integradora = cnpj("112223330001")
        if limpar:
            Integradora.objects.filter(cnpj=doc_integradora).delete()
            User.objects.filter(username__in=["admin", "gestor", "tecnico", "cliente"]).delete()

        cosern, _ = Concessionaria.objects.get_or_create(
            sigla="cosern", defaults={"nome": "Neoenergia Cosern", "uf": "RN", "layout_fatura": "cosern"})
        integ, criada = Integradora.objects.get_or_create(cnpj=doc_integradora, defaults={
            "razao_social": "Integradora Exemplo Energia Solar Ltda", "nome_fantasia": "Integradora Exemplo",
            "responsavel_tecnico_nome": "Eng. Ana Exemplo", "responsavel_tecnico_crea": "RN-0000000000",
            "email_contato": "contato@integradora-exemplo.com.br", "telefone_contato": "(84) 3000-0000",
            "cor_marca": "#1F4FFF"})
        if not criada:
            self.stdout.write("Integradora de demonstração já existe. Use --limpar para recriar.")
            return

        parada = (timezone.localdate() - datetime.timedelta(days=4)).isoformat()
        primeiro_cliente = None
        for i, (nome, doc, ucs, usinas) in enumerate(CLIENTES):
            cli = Cliente.objects.create(integradora=integ, nome=nome, documento=doc,
                                         email=f"contato{i}@exemplo.com.br", telefone="(84) 99999-0000")
            primeiro_cliente = primeiro_cliente or cli
            ConsentimentoLGPD.objects.create(cliente=cli, data=timezone.now(), versao_termo="1.0", ip="127.0.0.1")
            objs_uc = []
            for numero, sub, lig, municipio in ucs:
                objs_uc.append(UnidadeConsumidora.objects.create(
                    integradora=integ, cliente=cli, concessionaria=cosern, numero_uc=numero,
                    codigo_cliente=f"00{numero[-6:]}", grupo=sub[0], subgrupo=sub, tipo_ligacao=lig,
                    modalidade_tarifaria="verde" if sub.startswith("A") else "convencional",
                    demanda_contratada_kw=150 if sub.startswith("A") else None, municipio=municipio, uf="RN",
                    email_fatura=f"faturas+uc{numero}@integradora-exemplo.com.br"))
            for j, (unome, uc_idx, kwp, prot, invs, tem_medidor) in enumerate(usinas):
                u = Usina.objects.create(
                    integradora=integ, nome=unome, uc_geradora=objs_uc[uc_idx],
                    data_protocolo=datetime.date.fromisoformat(prot), potencia_kwp=kwp,
                    potencia_inversor_kw=round(kwp * 0.85, 1), numero_modulos=round(kwp * 1000 / 550),
                    data_conexao=datetime.date.fromisoformat(prot) + datetime.timedelta(days=75),
                    geracao_esperada_kwh=esperada(kwp))
                for k, (marca, modelo, prov, cred) in enumerate(invs):
                    cred = {kk: (parada if vv == "__parada__" else vv) for kk, vv in cred.items()}
                    # provedor real escolhido, sem credenciais -> o sistema usa dados fictícios
                    Inversor.objects.create(usina=u, marca=marca, modelo=modelo, provedor_api=prov,
                                            numero_serie=f"{marca[:2].upper()}{i}{j}{k}2026", credenciais=cred)
                if tem_medidor:
                    Medidor.objects.create(usina=u, fabricante="Medidor demo", modelo="M3F", numero_serie=f"MD{i}{j}")
        # Residência Lima: casa de praia rateia 30% para a casa principal
        lima = Usina.objects.get(integradora=integ, nome="Casa de praia Lima")
        Rateio.objects.create(usina=lima, uc=lima.uc_geradora, percentual=70)
        Rateio.objects.create(usina=lima, uc=UnidadeConsumidora.objects.get(integradora=integ, numero_uc="7060555666"),
                              percentual=30)

        def usuario(username, papel, nome, **extra):
            u = User.objects.create_user(username=username, password=SENHA, papel=papel, first_name=nome, **extra)
            return u

        usuario("gestor", User.Papel.GESTOR, "Gestora Exemplo", integradora=integ)
        usuario("tecnico", User.Papel.TECNICO, "Técnico Exemplo", integradora=integ)
        usuario("cliente", User.Papel.CLIENTE, "Padaria Sol Nascente", integradora=integ, cliente=primeiro_cliente)
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@faturacerta.local", SENHA, papel=User.Papel.ADMIN_INTERNO)

        self.stdout.write(f"Coletando {dias} dias de geração fictícia...")
        tasks.coletar_geracao_todos(dias=dias, integradora_id=integ.pk)
        tasks.coletar_status_todos(integradora_id=integ.pk)
        self.stdout.write(self.style.SUCCESS(
            f"Pronto. Usuários admin, gestor, tecnico e cliente, senha {SENHA}"))
