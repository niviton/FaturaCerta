"""Monta os dados dos gráficos (Chart.js) no servidor.

O template recebe um dicionário pronto: rótulos, séries com papel de cor e uma tabela
equivalente (para quem não enxerga o gráfico ou quer copiar os números).
Papéis de cor (fixos em todo o sistema): geracao, esperado, injecao, autoconsumo, rede, carga,
compensada, fatura, e as categorias c1..c6 na ordem validada.
"""

from decimal import Decimal


def _num(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(round(v, 2))
    return round(float(v), 2)


def serie(nome, valores, papel=None, tipo="bar", pilha=None, tracejado=False, cores=None):
    return {"nome": nome, "valores": [_num(v) for v in valores], "papel": papel, "tipo": tipo, "pilha": pilha,
            "tracejado": tracejado, "cores": cores}


def grafico(rotulos, series, unidade="kWh", tipo="barras", horizontal=False, empilhado=False, casas=0,
            rotulos_tabela=None):
    tabela = {
        "cabecalho": [s["nome"] for s in series],
        "linhas": [[(rotulos_tabela or rotulos)[i]] + [s["valores"][i] for s in series] for i in range(len(rotulos))],
    }
    return {"rotulos": list(rotulos), "series": series, "unidade": unidade, "tipo": tipo, "horizontal": horizontal,
            "empilhado": empilhado, "casas": casas, "tabela": tabela}


MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def rotulo_mes(d):
    return f"{MESES_CURTOS[d.month - 1]}/{d:%y}"
