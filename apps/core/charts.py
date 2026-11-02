"""Dados dos gráficos (ECharts) montados no servidor.

Cada função devolve um dicionário com `tipo` (que o static/js/charts.js sabe desenhar), os dados e a
`tabela` equivalente (para o "Ver os números"). As views só chamam estas funções; nenhuma regra de negócio
mora aqui.

Tipos: sankey, geracao, barras_agrupadas, cascata, aneis, calendario, rosca, ranking, bullet, mapa, gauge.
(As sparklines dos indicadores são SVG do servidor: tag {% sparkline %}, mais leves que um gráfico inteiro.)
"""

import datetime
import math
import random
from decimal import Decimal

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _n(v, casas=2):
    if v is None:
        return None
    return round(float(v), casas)


def _tabela(cabecalho, linhas):
    return {"cabecalho": cabecalho, "linhas": linhas}


def rotulo_mes(d: datetime.date) -> str:
    return f"{MESES[d.month - 1]}/{d:%y}"


# ------------------------------------------------------------------ 1. fluxo de energia
def sankey(gerado, instantaneo, injetado, compensado, nao_compensado, credito=0, unidade="kWh"):
    """Gerado → consumo instantâneo / injetado → compensado, virou crédito ou não compensado (sem explicação)."""
    nos = [{"nome": "Gerado", "tom": "solar"}, {"nome": "Consumo instantâneo", "tom": "ok"},
           {"nome": "Injetado na rede", "tom": "brand"}]
    links = [{"de": "Gerado", "para": "Consumo instantâneo", "valor": _n(instantaneo)},
             {"de": "Gerado", "para": "Injetado na rede", "valor": _n(injetado)}]
    if compensado and compensado > 0:  # nó com zero vira um risco espremido no desenho
        nos.append({"nome": "Compensado", "tom": "ok"})
        links.append({"de": "Injetado na rede", "para": "Compensado", "valor": _n(compensado)})
    if credito and credito > 0:
        nos.append({"nome": "Virou crédito", "tom": "neutro"})
        links.append({"de": "Injetado na rede", "para": "Virou crédito", "valor": _n(credito)})
    if nao_compensado and nao_compensado > 0:
        nos.append({"nome": "Não compensado", "tom": "danger"})
        links.append({"de": "Injetado na rede", "para": "Não compensado", "valor": _n(nao_compensado)})
    return {"tipo": "sankey", "unidade": unidade, "casas": 0, "nos": nos, "links": links,
            "tabela": _tabela(["kWh"], [["Gerado", _n(gerado)], ["Consumo instantâneo", _n(instantaneo)],
                                        ["Injetado", _n(injetado)], ["Compensado", _n(compensado)],
                                        ["Virou crédito", _n(credito or 0)],
                                        ["Não compensado", _n(nao_compensado or 0)]])}


# ------------------------------------------------------------------ 2. geração × esperado
def geracao(periodos: dict, padrao: str, unidade="kWh"):
    """periodos = {"30D": {"rotulos": [...], "gerado": [...], "esperado": [...], "min": [...], "max": [...]}}"""
    p = periodos[padrao]
    return {"tipo": "geracao", "unidade": unidade, "casas": 1, "padrao": padrao,
            "periodos": {k: {kk: ([_n(x, 1) for x in vv] if kk != "rotulos" else vv) for kk, vv in v.items()}
                         for k, v in periodos.items()},
            "tabela": _tabela(["Gerado", "Esperado"],
                              [[r, _n(g, 1), _n(e, 1)] for r, g, e in zip(p["rotulos"], p["gerado"], p["esperado"],
                                                                          strict=False)])}


# ------------------------------------------------------------------ 3. injetado × compensado
def barras_agrupadas(rotulos, series, anotacoes=None, unidade="kWh"):
    """series = [{"nome", "valores", "tom"}]; anotacoes = [{"indice", "texto"}] (ex.: valor perdido em R$)."""
    return {"tipo": "barras_agrupadas", "unidade": unidade, "casas": 0, "rotulos": rotulos,
            "series": [{**s, "valores": [_n(v) for v in s["valores"]]} for s in series],
            "anotacoes": anotacoes or [],
            "tabela": _tabela([s["nome"] for s in series],
                              [[r] + [_n(s["valores"][i]) for s in series] for i, r in enumerate(rotulos)])}


# ------------------------------------------------------------------ 4. cascata da fatura
def cascata(itens, unidade="R$"):
    """itens = [{"rotulo", "valor", "tipo": "total"|"menos"|"mais"}]; o primeiro e o último são totais."""
    return {"tipo": "cascata", "unidade": unidade, "casas": 2,
            "itens": [{**i, "valor": _n(i["valor"])} for i in itens],
            "tabela": _tabela(["Valor (R$)"], [[i["rotulo"], _n(-i["valor"] if i["tipo"] == "menos" else i["valor"])]
                                               for i in itens])}


# ------------------------------------------------------------------ 5. anéis de desempenho
def aneis(itens):
    """itens = [{"rotulo": "1D", "pct": 92}]. Faixas: ≥ 85 ok, 60–85 solar, < 60 danger."""
    return {"tipo": "aneis", "unidade": "%", "casas": 0, "itens": [{**i, "pct": _n(i["pct"], 0)} for i in itens],
            "tabela": _tabela(["Desempenho (%)"], [[i["rotulo"], _n(i["pct"], 0)] for i in itens])}


# ------------------------------------------------------------------ 6. calendário de calor
def calendario(dias, unidade="kWh"):
    """dias = [(date, kwh)] do último ano."""
    valores = [float(v) for _, v in dias if v is not None]
    return {"tipo": "calendario", "unidade": unidade, "casas": 1,
            "inicio": dias[0][0].isoformat(), "fim": dias[-1][0].isoformat(),
            "dias": [[d.isoformat(), _n(v, 1)] for d, v in dias], "max": max(valores) if valores else 0,
            "tabela": _tabela(["Gerado (kWh)"], [[f"{d:%d/%m/%Y}", _n(v, 1)] for d, v in dias[-31:]])}


# ------------------------------------------------------------------ 7. rosca
def rosca(itens, centro_rotulo, unidade=""):
    """itens = [{"nome", "valor"}] em ordem decrescente; a cor segue a ordem da paleta categórica."""
    total = sum(float(i["valor"]) for i in itens) or 1
    return {"tipo": "rosca", "unidade": unidade, "casas": 1 if unidade == "kWp" else 0, "centro": centro_rotulo,
            "itens": [{"nome": i["nome"], "valor": _n(i["valor"], 1)} for i in itens],
            "tabela": _tabela([unidade or "Quantidade", "%"],
                              [[i["nome"], _n(i["valor"], 1), _n(float(i["valor"]) / total * 100, 1)] for i in itens])}


# ------------------------------------------------------------------ 8. ranking
def ranking(itens, unidade="", casas=0):
    """itens = [{"nome", "valor", "tom"?}] — desenhado do maior para o menor."""
    itens = sorted(itens, key=lambda i: -float(i["valor"]))
    return {"tipo": "ranking", "unidade": unidade, "casas": casas,
            "itens": [{**i, "valor": _n(i["valor"], casas)} for i in itens],
            "tabela": _tabela([unidade or "Valor"], [[i["nome"], _n(i["valor"], casas)] for i in itens])}


# ------------------------------------------------------------------ 9. bullet de demanda
def bullet(rotulos, medida, contratada, tolerancia=0.05, unidade="kW"):
    return {"tipo": "bullet", "unidade": unidade, "casas": 0, "rotulos": rotulos,
            "medida": [_n(v, 1) for v in medida], "contratada": _n(contratada, 1), "tolerancia": tolerancia,
            "tabela": _tabela(["Medida", "Contratada", "Ultrapassagem"],
                              [[r, _n(m, 1), _n(contratada, 1), _n(max(float(m) - float(contratada), 0), 1)]
                               for r, m in zip(rotulos, medida, strict=False)])}


# ------------------------------------------------------------------ 11. mapa
def mapa(pontos):
    """pontos = [{"nome", "lat", "lon", "status": ok|solar|danger|neutro, "rotulo", "kwp", "url"}]."""
    return {"tipo": "mapa", "unidade": "", "casas": 0,
            "pontos": [{**p, "lat": float(p["lat"]), "lon": float(p["lon"]), "kwp": _n(p.get("kwp"), 1)}
                       for p in pontos],
            "tabela": _tabela(["Situação", "kWp"], [[p["nome"], p["rotulo"], _n(p.get("kwp"), 1)] for p in pontos])}


# ------------------------------------------------------------------ 12. medidor de economia
def gauge(valor, meta, rotulo="Economia no ano", unidade="R$"):
    return {"tipo": "gauge", "unidade": unidade, "casas": 0, "valor": _n(valor), "meta": _n(meta), "rotulo": rotulo,
            "tabela": _tabela(["R$"], [["Economizado", _n(valor)], ["Meta do ano", _n(meta)]])}


# ------------------------------------------------------------------ dados fictícios para a página /design/
def exemplos_design():
    r = random.Random(42)
    hoje = datetime.date(2026, 11, 2)

    def serie_dias(n, base):
        out = []
        for k in range(n, 0, -1):
            d = hoje - datetime.timedelta(days=k)
            sazonal = 1 + 0.18 * math.cos((d.timetuple().tm_yday - 300) / 365 * 2 * math.pi)
            nublado = r.random() < 0.08  # poucos dias ruins, para o destaque chamar o olho
            v = base * sazonal * (r.uniform(0.45, 0.7) if nublado else r.uniform(0.9, 1.08))
            out.append((d, v))
        return out

    d30 = serie_dias(30, 98)
    d7 = d30[-7:]
    meses = [(hoje.replace(day=1) - datetime.timedelta(days=31 * k)).replace(day=1) for k in range(11, -1, -1)]

    def periodo(pares, esp_base):
        esp = [esp_base * (1 + 0.18 * math.cos((d.timetuple().tm_yday - 300) / 365 * 2 * math.pi)) for d, _ in pares]
        return {"rotulos": [f"{d:%d/%m}" for d, _ in pares], "gerado": [v for _, v in pares], "esperado": esp,
                "min": [e * 0.85 for e in esp], "max": [e * 1.1 for e in esp]}

    mensal_g = [r.uniform(2550, 3250) * (1 + 0.15 * math.cos((m.month - 10) / 12 * 2 * math.pi)) for m in meses]
    mensal_e = [2900 * (1 + 0.15 * math.cos((m.month - 10) / 12 * 2 * math.pi)) for m in meses]
    p12 = {"rotulos": [rotulo_mes(m) for m in meses], "gerado": mensal_g, "esperado": mensal_e,
           "min": [e * 0.85 for e in mensal_e], "max": [e * 1.1 for e in mensal_e]}
    p12["gerado"][-4] = mensal_e[-4] * 0.62  # um mês ruim, para aparecer o destaque

    injetado = [r.uniform(1800, 2300) for _ in meses]
    compensado = [v * r.uniform(0.97, 1.0) for v in injetado]
    compensado[-1], compensado[-2] = 0, injetado[-2] * 0.4  # injeção não compensada
    perdido = [round((i - c) * 0.95, 2) for i, c in zip(injetado, compensado, strict=False)]

    ano = serie_dias(365, 95)
    ano = [(d, 0 if hoje - datetime.timedelta(days=60) <= d <= hoje - datetime.timedelta(days=52) else v)
           for d, v in ano]

    return {
        "sankey": sankey(3184, 1105, 2079, 1350, 729),
        "geracao": geracao({"7D": periodo(d7, 98), "30D": periodo(d30, 98), "12M": p12}, "30D"),
        "injetado": barras_agrupadas(
            [rotulo_mes(m) for m in meses],
            [{"nome": "Injetado", "valores": injetado, "tom": "brand"},
             {"nome": "Compensado", "valores": compensado, "tom": "ok"}],
            [{"indice": i, "texto": f"R$ {p:,.0f}".replace(",", ".")} for i, p in enumerate(perdido) if p > 200]),
        "cascata": cascata([
            {"rotulo": "Conta sem solar", "curto": "Sem solar", "valor": 2846.30, "tipo": "total"},
            {"rotulo": "Energia compensada", "curto": "Compensada", "valor": 1282.50, "tipo": "menos"},
            {"rotulo": "Fio B não compensado", "curto": "Fio B", "valor": 168.40, "tipo": "mais"},
            {"rotulo": "Custo de disponibilidade", "curto": "Disponib.", "valor": 95.00, "tipo": "mais"},
            {"rotulo": "CIP", "valor": 38.90, "tipo": "mais"},
            {"rotulo": "Tributos", "valor": 211.70, "tipo": "mais"},
            {"rotulo": "Conta com solar", "curto": "Com solar", "valor": 2077.80, "tipo": "total"},
        ]),
        "aneis": aneis([{"rotulo": "Hoje", "pct": 92}, {"rotulo": "15 dias", "pct": 78},
                        {"rotulo": "30 dias", "pct": 88}, {"rotulo": "12 meses", "pct": 54}]),
        "calendario": calendario(ano),
        "rosca": rosca([{"nome": "GoodWe", "valor": 85.9}, {"nome": "Deye", "valor": 70.4},
                        {"nome": "Growatt", "valor": 24.8}, {"nome": "Huawei", "valor": 26.4},
                        {"nome": "Fronius", "valor": 57.2}, {"nome": "SolarEdge", "valor": 8.3}],
                       "kWp monitorados", "kWp"),
        "rosca_gd": rosca([{"nome": "GD1", "valor": 6}, {"nome": "GD2", "valor": 5}], "usinas"),
        "ranking": ranking([{"nome": "Integradora Exemplo", "valor": 217.8}, {"nome": "Sol do Seridó", "valor": 55.6},
                            {"nome": "Potiguar Solar", "valor": 148.2}, {"nome": "Energia Agreste", "valor": 96.5}],
                           "kWp", 1),
        "ranking_div": ranking([{"nome": "Constante do medidor", "valor": 12, "tom": "danger"},
                                {"nome": "Ultrapassagem de demanda", "valor": 9, "tom": "solar"},
                                {"nome": "Injeção não compensada", "valor": 5, "tom": "danger"},
                                {"nome": "Fio B divergente", "valor": 3, "tom": "brand"}], "faturas"),
        "bullet": bullet([rotulo_mes(m) for m in meses],
                         [150 * r.uniform(0.86, 1.22) for _ in meses], 150),
        "mapa": mapa([
            {"nome": "Padaria · telhado", "lat": -5.80, "lon": -35.21, "status": "ok", "rotulo": "Gerando", "kwp": 18.7},
            {"nome": "Padaria · ampliação", "lat": -5.81, "lon": -35.20, "status": "ok", "rotulo": "Gerando", "kwp": 8.3},
            {"nome": "Clínica Boa Vista", "lat": -5.79, "lon": -35.19, "status": "ok", "rotulo": "Gerando", "kwp": 22},
            {"nome": "Pajuçara · estacionamento", "lat": -5.75, "lon": -35.24, "status": "solar",
             "rotulo": "Abaixo do esperado", "kwp": 40.2},
            {"nome": "Escola Nova Era", "lat": -5.92, "lon": -35.26, "status": "danger", "rotulo": "Parada", "kwp": 30.3},
            {"nome": "Casa de praia Lima", "lat": -6.09, "lon": -35.21, "status": "danger", "rotulo": "Sem comunicação",
             "kwp": 4.4},
            {"nome": "Fazenda Boa Esperança", "lat": -6.26, "lon": -36.52, "status": "ok", "rotulo": "Gerando", "kwp": 45.1},
            {"nome": "Mercadinho São José", "lat": -6.46, "lon": -37.10, "status": "ok", "rotulo": "Gerando", "kwp": 10.5},
        ]),
        "gauge": gauge(Decimal("4128.40"), Decimal("5400")),
    }
