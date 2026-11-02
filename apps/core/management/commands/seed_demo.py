"""Dados de demonstração. Uso: python manage.py seed_demo [--dias 400] [--limpar]

Gera duas integradoras, usuários dos três níveis, clientes com cadastro completo, usinas de vários
fabricantes, medidores próprios, geração diária, curva de hoje, leituras do medidor e 12 faturas por UC.
As três fontes contam a mesma história (mesma simulação), e cada cliente tem um caso de auditoria:

    Padaria Sol Nascente ...... injeção não compensada nas 2 últimas faturas
    Clínica Boa Vista ......... GD2 com Fio B cobrado acima do previsto
    Oficina Potengi ........... constante do medidor errada na fatura (consumo 25% acima do medido)
    Supermercado Pajuçara ..... grupo A: ultrapassagem de demanda e reativo; 2ª usina abaixo do esperado
    Escola Nova Era ........... usina parada há 40 dias (a última fatura já mostra a queda)
    Residência Lima ........... tudo certo; casa de praia sem comunicação

Valores de tarifa são FICTÍCIOS, só para demonstração.
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.analise.services import balanco_periodo
from apps.cadastro.models import (
    ArranjoModulos,
    Cliente,
    Concessionaria,
    ConsentimentoLGPD,
    Inversor,
    LoteCredito,
    Medidor,
    Rateio,
    UnidadeConsumidora,
    Usina,
)
from apps.core.models import Integradora
from apps.faturas.models import Fatura
from apps.integracoes.fake import energia_fake_da_uc
from apps.monitoramento import services

SENHA = "FaturaCerta@2026"
TARIFA_FICTICIA = Decimal("0.95")  # R$/kWh com tributos, só demonstração
FIO_B_FICTICIO = Decimal("0.21")  # R$/kWh, só demonstração
PCT_FIO_B_2026 = Decimal("0.60")  # Lei 14.300, transição; confirmar na tabela regulatória


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


PERFIL_NATAL = [140, 128, 136, 120, 116, 106, 114, 131, 140, 150, 147, 146]  # kWh/mês por kWp (aprox.)


def esperada(kwp):
    return [round(kwp * v) for v in PERFIL_NATAL]


def d(x):
    return Decimal(str(round(x, 2)))


# ------------------------------------------------------------------ catálogo de demonstração
# UC: (numero, subgrupo, classe, ligacao, tensao, consumo_medio, municipio, extra)
# usina: (nome, uc_idx, tipo, kwp, protocolo, [(marca, modelo, provedor, kw, cred)], modulo)
CLIENTES = [
    {"nome": "Padaria Sol Nascente Ltda", "fantasia": "Padaria Sol Nascente", "doc": cnpj("123456780001"),
     "segmento": "comercial", "atividade": "Panificação e confeitaria", "contato": "Marta Albuquerque",
     "horario": "Todos os dias, 5h às 21h", "bairro": "Ponta Negra",
     "ucs": [("7010453067", "B3", "comercial", "tri", 380, 3600, "Natal", {})],
     "usinas": [("Padaria · telhado", 0, "junto_carga", 18.7, "2022-08-10",
                 [("Growatt", "MID 15KTL3-X", "growatt", 15, {})], ("Jinko", "Tiger Neo 550", 550)),
                ("Padaria · ampliação", 0, "junto_carga", 8.25, "2023-09-02",
                 [("SolarEdge", "SE8K-RW", "solaredge", 8, {})], ("Canadian Solar", "HiKu7 550", 550))],
     "medidor": "rede", "caso": "nao_compensada"},
    {"nome": "Clínica Boa Vista Serviços Médicos Ltda", "fantasia": "Clínica Boa Vista", "doc": cnpj("234567890001"),
     "segmento": "comercial", "atividade": "Clínica médica", "contato": "Dr. Paulo Rocha",
     "horario": "Seg a sex 7h às 19h, sáb 7h às 12h", "bairro": "Tirol",
     "ucs": [("7020111222", "B3", "comercial", "tri", 380, 2900, "Natal", {})],
     "usinas": [("Clínica Boa Vista", 0, "junto_carga", 22.0, "2023-06-15",
                 [("Huawei", "SUN2000-20KTL-M2", "huawei", 20, {})], ("Trina", "Vertex 550", 550))],
     "medidor": None, "caso": "fio_b"},
    {"nome": "Oficina Mecânica Potengi ME", "fantasia": "Oficina Potengi", "doc": cnpj("345678900001"),
     "segmento": "comercial", "atividade": "Oficina mecânica", "contato": "Seu Raimundo",
     "horario": "Seg a sáb, 7h às 18h", "bairro": "Alecrim",
     "ucs": [("7030222333", "B3", "comercial", "tri", 380, 1500, "Natal", {})],
     "usinas": [("Oficina Potengi", 0, "junto_carga", 12.1, "2022-11-20",
                 [("Fronius", "Symo 12.5-3-M", "fronius", 12.5, {})], ("Longi", "Hi-MO 6 550", 550))],
     "medidor": "rede", "caso": "constante"},
    {"nome": "Supermercado Pajuçara S.A.", "fantasia": "Supermercado Pajuçara", "doc": cnpj("456789010001"),
     "segmento": "comercial", "atividade": "Supermercado", "contato": "Fernanda Lins (manutenção)",
     "horario": "Todos os dias, 7h às 22h", "bairro": "Pajuçara",
     "ucs": [("7040333444", "A4", "comercial", "", 13800, 32000, "Natal",
              {"modalidade_tarifaria": "verde", "demanda_contratada_kw": 150})],
     "usinas": [("Pajuçara · cobertura", 0, "junto_carga", 75.9, "2022-10-01",
                 [("GoodWe", "GW50K-MT", "goodwe", 50, {}), ("GoodWe", "GW25K-MT", "goodwe", 25, {})],
                 ("Jinko", "Tiger Neo 550", 550)),
                ("Pajuçara · estacionamento", 0, "junto_carga", 40.15, "2024-02-19",
                 [("Deye", "SUN-40K-G03", "deye", 40, {"cenario": "baixa", "fator": 0.62})],
                 ("Canadian Solar", "BiHiKu7 550", 550))],
     "medidor": "rede_carga", "caso": "grupo_a"},
    {"nome": "Escola Nova Era Ensino Fundamental Ltda", "fantasia": "Escola Nova Era", "doc": cnpj("567890120001"),
     "segmento": "comercial", "atividade": "Escola", "contato": "Diretora Sílvia",
     "horario": "Seg a sex, 7h às 18h", "bairro": "Centro",
     "ucs": [("7050444555", "B3", "comercial", "tri", 380, 4200, "Parnamirim", {})],
     "usinas": [("Escola Nova Era", 0, "junto_carga", 30.25, "2023-03-30",
                 [("Deye", "SUN-30K-G04", "deye", 30, {"cenario": "parada", "desde": "__parada__"})],
                 ("Trina", "Vertex 550", 550))],
     "medidor": None, "caso": "parada"},
    {"nome": "Carlos Eduardo Lima", "fantasia": "", "doc": cpf("390533447"), "pf": True,
     "segmento": "residencial", "atividade": "", "contato": "Carlos Lima",
     "horario": "", "bairro": "Capim Macio",
     "ucs": [("7060555666", "B1", "residencial", "bi", 220, 620, "Natal", {}),
             ("7060555777", "B1", "residencial", "mono", 220, 260, "Nísia Floresta", {"apelido": "casa de praia"})],
     "usinas": [("Casa Lima", 0, "junto_carga", 6.05, "2022-05-12",
                 [("Growatt", "MIN 5000TL-X", "growatt", 5, {})], ("Jinko", "Tiger Neo 550", 550)),
                ("Casa de praia Lima", 1, "autoconsumo_remoto", 4.4, "2024-07-08",
                 [("Huawei", "SUN2000-4KTL-L1", "huawei", 4, {"cenario": "offline"})], ("Longi", "Hi-MO 6 550", 550))],
     "medidor": "rede", "caso": "ok"},
]

SEGUNDA = [
    {"nome": "Mercadinho São José", "fantasia": "", "doc": cnpj("678901230001"), "segmento": "comercial",
     "atividade": "Mercearia", "contato": "José", "horario": "", "bairro": "Centro",
     "ucs": [("7111222333", "B3", "comercial", "tri", 380, 1800, "Caicó", {})],
     "usinas": [("Mercadinho São José", 0, "junto_carga", 10.45, "2023-11-10",
                 [("GoodWe", "GW10K-SDT", "goodwe", 10, {})], ("Trina", "Vertex 550", 550))],
     "medidor": None, "caso": "ok"},
    {"nome": "Fazenda Boa Esperança", "fantasia": "", "doc": cnpj("789012340001"), "segmento": "rural",
     "atividade": "Irrigação e granja", "contato": "Antônio", "horario": "", "bairro": "Zona rural",
     "ucs": [("7111222444", "B2", "rural", "tri", 380, 5200, "Currais Novos", {})],
     "usinas": [("Fazenda Boa Esperança", 0, "junto_carga", 45.1, "2022-12-20",
                 [("Fronius", "Tauro 50-3", "fronius", 50, {})], ("Jinko", "Tiger Neo 550", 550))],
     "medidor": None, "caso": "ok"},
]


class Command(BaseCommand):
    help = "Cria dados de demonstração completos (3 perfis, 2 integradoras, 3 fontes de dados)."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=400)
        parser.add_argument("--limpar", action="store_true", help="Apaga os dados de demonstração antes.")

    def handle(self, *args, dias, limpar, **opts):
        docs = [cnpj("112223330001"), cnpj("998887770001")]
        if limpar:
            Usina.objects.filter(integradora__cnpj__in=docs).delete()  # UC geradora é protegida
            Integradora.objects.filter(cnpj__in=docs).delete()
            User.objects.filter(username__in=["admin", "gestor", "tecnico", "cliente", "lima", "gestor2"]).delete()
        if Integradora.objects.filter(cnpj=docs[0]).exists():
            self.stdout.write("Dados de demonstração já existem. Use --limpar para recriar.")
            return

        with transaction.atomic():
            cosern, _ = Concessionaria.objects.update_or_create(sigla="cosern", defaults={
                "nome": "Neoenergia Cosern", "uf": "RN", "layout_fatura": "cosern",
                "tarifa_referencia_kwh": TARIFA_FICTICIA})
            a = Integradora.objects.create(
                cnpj=docs[0], razao_social="Integradora Exemplo Energia Solar Ltda", nome_fantasia="Integradora Exemplo",
                responsavel_tecnico_nome="Eng. Ana Exemplo", responsavel_tecnico_crea="RN-2101234567",
                email_contato="contato@integradora-exemplo.com.br", telefone_contato="(84) 3000-0000",
                whatsapp="(84) 99999-0000", municipio="Natal", uf="RN", cor_marca="#1F4FFF",
                plano=Integradora.Plano.COMPLETO, valor_por_usina=Decimal("39.90"), taxa_exito_pct=Decimal("20"))
            b = Integradora.objects.create(
                cnpj=docs[1], razao_social="Sol do Seridó Energia Ltda", nome_fantasia="Sol do Seridó",
                responsavel_tecnico_nome="Eng. Bruno Seridó", responsavel_tecnico_crea="RN-2107654321",
                email_contato="contato@soldoserido.com.br", municipio="Caicó", uf="RN", cor_marca="#0E9F6E",
                plano=Integradora.Plano.ESSENCIAL, valor_por_usina=Decimal("29.90"))
            parada = (timezone.localdate() - datetime.timedelta(days=40)).isoformat()
            clientes_a = [self._cliente(a, cosern, c, i, parada) for i, c in enumerate(CLIENTES)]
            for i, c in enumerate(SEGUNDA):
                self._cliente(b, cosern, c, 10 + i, parada)

            lima = Usina.objects.get(integradora=a, nome="Casa de praia Lima")
            Rateio.objects.create(usina=lima, uc=lima.uc_geradora, percentual=40)
            Rateio.objects.create(usina=lima, uc=UnidadeConsumidora.objects.get(integradora=a, numero_uc="7060555666"),
                                  percentual=60)

            def usuario(username, papel, nome, **extra):
                return User.objects.create_user(username=username, password=SENHA, papel=papel, first_name=nome,
                                                email=f"{username}@exemplo.com.br", **extra)

            if not User.objects.filter(username="admin").exists():
                User.objects.create_superuser("admin", "admin@faturacerta.local", SENHA, papel=User.Papel.ADMIN_INTERNO,
                                              first_name="Administrador geral")
            usuario("gestor", User.Papel.GESTOR, "Ana Gestora", integradora=a)
            usuario("tecnico", User.Papel.TECNICO, "Tiago Técnico", integradora=a)
            usuario("cliente", User.Papel.CLIENTE, "Marta (Padaria)", integradora=a, cliente=clientes_a[0])
            usuario("lima", User.Papel.CLIENTE, "Carlos Lima", integradora=a, cliente=clientes_a[5])
            usuario("gestor2", User.Papel.GESTOR, "Bruno Gestor", integradora=b)

        self.stdout.write(f"Gerando {dias} dias de geração (inversores)...")
        for inv in Inversor.objects.filter(usina__integradora__in=[a, b]).select_related("usina"):
            services.coletar_geracao(inv, dias)
            services.coletar_curva(inv, timezone.localdate())
            services.coletar_status(inv)
        self.stdout.write("Gerando leituras dos medidores próprios...")
        for m in Medidor.objects.filter(uc__integradora=a):
            m.uc = UnidadeConsumidora.objects.prefetch_related("usinas__inversores__usina").select_related(
                "cliente").get(pk=m.uc_id)
            services.coletar_medidor(m, dias)
        self.stdout.write("Gerando 12 faturas por UC e conferindo...")
        for uc in UnidadeConsumidora.objects.filter(integradora__in=[a, b]).prefetch_related(
                "usinas__inversores__usina").select_related("cliente"):
            self._faturas(uc)
        self.stdout.write(self.style.SUCCESS(
            f"Pronto. Usuários: admin (administrador geral), gestor e tecnico (Integradora Exemplo), gestor2 "
            f"(Sol do Seridó), cliente (Padaria) e lima (Residência Lima). Senha de todos: {SENHA}"))

    # ------------------------------------------------------------------
    def _cliente(self, integ, cosern, c, i, parada):
        cli = Cliente.objects.create(
            integradora=integ, tipo_pessoa="pf" if c.get("pf") else "pj", nome=c["nome"],
            nome_fantasia=c["fantasia"], documento=c["doc"], segmento=c["segmento"], atividade=c["atividade"],
            contato_nome=c["contato"], email=f"contato{i}@exemplo.com.br", telefone=f"(84) 3200-00{i:02d}",
            whatsapp=f"(84) 98800-00{i:02d}", horario_funcionamento=c["horario"], logradouro="Rua Exemplo",
            numero=str(100 + i), bairro=c["bairro"], municipio=c["ucs"][0][6], uf="RN", cep="59000-000",
            data_inicio_contrato=datetime.date(2024, 1, 15))
        ConsentimentoLGPD.objects.create(cliente=cli, data=timezone.now(), versao_termo="1.0", ip="127.0.0.1")
        ucs = []
        for numero, sub, classe, lig, tensao, consumo, municipio, extra in c["ucs"]:
            constante = Decimal("1")
            ucs.append(UnidadeConsumidora.objects.create(
                integradora=integ, cliente=cli, concessionaria=cosern, numero_uc=numero,
                codigo_cliente=f"00{numero[-7:]}", grupo=sub[0], subgrupo=sub, classe=classe, tipo_ligacao=lig,
                tensao_fornecimento_v=tensao, consumo_medio_kwh=consumo, municipio=municipio, uf="RN",
                bairro=c["bairro"], logradouro="Rua Exemplo", numero=str(100 + i),
                numero_medidor_concessionaria=f"NC{numero[-6:]}", constante_medidor=constante,
                medidor_bidirecional=True, data_ligacao=datetime.date(2015, 3, 1),
                email_fatura=f"faturas+uc{numero}@integradora-exemplo.com.br", **extra))
        for j, (nome, uc_idx, tipo, kwp, prot, invs, (mfab, mmod, wp)) in enumerate(c["usinas"]):
            data_prot = datetime.date.fromisoformat(prot)
            u = Usina.objects.create(
                integradora=integ, nome=nome, uc_geradora=ucs[uc_idx], tipo=tipo, data_protocolo=data_prot,
                numero_protocolo=f"PA-{data_prot:%Y}-{4000 + i * 10 + j}",
                data_parecer_acesso=data_prot + datetime.timedelta(days=30),
                data_conexao=data_prot + datetime.timedelta(days=75), tipo_instalacao="metalico" if kwp > 15 else "ceramico",
                inclinacao_graus=Decimal("10"), azimute_graus=Decimal("0"), geracao_esperada_kwh=esperada(kwp),
                valor_investido=Decimal(str(round(kwp * 3600, 2))), municipio=ucs[uc_idx].municipio, uf="RN",
                latitude=Decimal("-5.795000"), longitude=Decimal("-35.209000"))
            ArranjoModulos.objects.create(usina=u, fabricante=mfab, modelo=mmod, potencia_wp=wp,
                                          quantidade=round(kwp * 1000 / wp), inclinacao_graus=10, azimute_graus=0,
                                          garantia_anos=25)
            for k, (marca, modelo, prov, kw, cred) in enumerate(invs):
                cred = {kk: (parada if vv == "__parada__" else vv) for kk, vv in cred.items()}
                # provedor real escolhido, sem credenciais -> o sistema usa dados fictícios
                Inversor.objects.create(
                    usina=u, marca=marca, modelo=modelo, provedor_api=prov, numero_serie=f"{marca[:2].upper()}{i}{j}{k}26",
                    tipo="string", potencia_nominal_kw=kw, fases="tri" if kw > 6 else "mono",
                    numero_mppt=2 if kw < 20 else 4,
                    data_instalacao=u.data_conexao - datetime.timedelta(days=5),
                    garantia_ate=u.data_conexao + datetime.timedelta(days=365 * 10), credenciais=cred)
            u.recalcular_potencia()
        if c.get("medidor"):
            Medidor.objects.create(
                uc=ucs[0], usina=ucs[0].usinas.first(), nome="ESP do quadro geral", tipo="esp32",
                ponto_medicao=c["medidor"], fabricante="Espressif + SCT-013", modelo="ESP32-WROOM",
                numero_serie=f"ESP-{i:03d}", fases=3 if ucs[0].tipo_ligacao in ("tri", "") else 1,
                corrente_ct_a=200 if ucs[0].grupo == "A" else 100, intervalo_envio_s=60,
                data_instalacao=datetime.date(2025, 6, 1), provedor_api="fake")
        cli.caso = c["caso"]
        Cliente.objects.filter(pk=cli.pk).update(observacoes=f"Demonstração: caso '{c['caso']}'.")
        return cli

    def _faturas(self, uc):
        caso = (uc.cliente.observacoes.split("'")[1] if "'" in uc.cliente.observacoes else "ok")
        hoje = timezone.localdate()
        leituras = []
        m = (hoje.replace(day=1) - datetime.timedelta(days=1)).replace(day=12) if hoje.day < 13 else hoje.replace(day=12)
        for _ in range(13):
            leituras.append(m)
            m = (m.replace(day=1) - datetime.timedelta(days=1)).replace(day=12)
        leituras = list(reversed(leituras))
        saldo = Decimal(0)
        contador_imp = Decimal(30000 + int(uc.numero_uc[-3:]))
        fator_constante = Decimal("1.25") if caso == "constante" else Decimal(1)
        disp = Decimal(uc.custo_disponibilidade_kwh or 0)
        grupo_a = uc.grupo == "A"
        for n, (ini, fim) in enumerate(zip(leituras, leituras[1:], strict=False)):
            imp = exp = 0.0
            dia = ini + datetime.timedelta(days=1)
            while dia <= fim:
                e = energia_fake_da_uc(uc, dia)
                imp += e["importacao"]
                exp += e["exportacao"]
                dia += datetime.timedelta(days=1)
            real = d(imp)
            consumo = d(imp * float(fator_constante))
            injetada = d(exp)
            compensavel = max(consumo - disp, Decimal(0))
            disponivel = injetada + saldo
            compensada = min(disponivel, compensavel)
            ultimas = n >= 10
            if caso == "nao_compensada" and ultimas:
                compensada = Decimal(0)
            else:
                saldo = disponivel - compensada
            faturavel = consumo - compensada
            valor_energia = (faturavel * TARIFA_FICTICIA).quantize(Decimal("0.01"))
            pct_fio_b = PCT_FIO_B_2026 + (Decimal("0.15") if caso == "fio_b" and ultimas else 0)
            fio_b = (compensada * FIO_B_FICTICIO * pct_fio_b).quantize(Decimal("0.01")) if uc.usinas.first() and \
                uc.usinas.first().enquadramento == "GD2" else None
            cip = Decimal("38.90") if consumo > 1000 else Decimal("18.45")
            demanda_medida = ultrapassagem = reativo = None
            if grupo_a:
                demanda_medida = Decimal(150) * Decimal(str(1.05 + (n % 4) * 0.06))
                excesso = demanda_medida - Decimal(150)
                ultrapassagem = None
                if excesso > Decimal("7.5"):
                    ultrapassagem = (excesso * 2 * Decimal("42.50")).quantize(Decimal("0.01"))
                reativo = Decimal(str(140 + (n % 5) * 35))
            total = valor_energia + (fio_b or 0) + cip + (ultrapassagem or 0) + (reativo or 0)
            leitura_ant = contador_imp
            contador_imp += real
            Fatura.objects.create(
                integradora=uc.integradora, uc=uc, mes_referencia=fim.replace(day=1), data_leitura_anterior=ini,
                data_leitura_atual=fim, vencimento=fim + datetime.timedelta(days=15),
                leitura_anterior=leitura_ant, leitura_atual=contador_imp, constante_medidor=fator_constante,
                consumo_kwh=consumo, energia_injetada_kwh=injetada, energia_compensada_kwh=compensada,
                saldo_creditos_kwh=saldo, modalidade_gd=(uc.usinas.first().enquadramento if uc.usinas.first() else ""),
                bandeira="amarela" if fim.month in (8, 9, 10) else "verde", custo_disponibilidade_kwh=disp or None,
                valor_fio_b=fio_b, valor_icms=(total * Decimal("0.18")).quantize(Decimal("0.01")),
                valor_pis_cofins=(total * Decimal("0.05")).quantize(Decimal("0.01")), valor_cip=cip,
                demanda_contratada_kw=uc.demanda_contratada_kw, demanda_medida_kw=demanda_medida,
                valor_ultrapassagem=ultrapassagem, valor_reativo=reativo, valor_total=total.quantize(Decimal("0.01")),
                origem=Fatura.Origem.DEMO,
                observacoes="Fio B acima do percentual de transição previsto." if caso == "fio_b" and ultimas else "")
        if saldo > 0:
            LoteCredito.objects.create(uc=uc, mes_referencia=leituras[-1].replace(day=1), kwh_gerado=saldo,
                                       kwh_saldo=saldo, origem="demo")
        for f in uc.faturas.all():
            b = balanco_periodo(uc, f.data_leitura_anterior + datetime.timedelta(days=1), f.data_leitura_atual, f)
            divergente = any(i.gravidade in ("alta", "media") for i in b.indicios) or bool(f.observacoes)
            f.status = Fatura.Status.DIVERGENTE if divergente else Fatura.Status.CONFERIDA
            f.save(update_fields=["status"])
