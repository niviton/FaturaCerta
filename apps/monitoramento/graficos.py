"""Gráficos de monitoramento (geração, curva do dia, desempenho, fabricantes)."""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.utils import timezone

from apps.core.graficos import grafico, rotulo_mes, serie

from . import services

MAX_SERIES = 6  # paleta categórica validada; acima disso agrupa em "Outras"


def geracao_diaria(usinas, dias=30, por_usina=True):
    hoje = timezone.localdate()
    datas = [hoje - datetime.timedelta(days=n) for n in range(dias, 0, -1)]
    rotulos = [f"{d:%d/%m}" for d in datas]
    esperado = [sum((services.esperado_no_dia(u, d) or Decimal(0) for u in usinas), Decimal(0)) for d in datas]
    series = []
    if por_usina and 1 < len(usinas):
        por = services.serie_diaria(usinas, datas[0], datas[-1], por_usina=True)
        ordem = sorted(usinas, key=lambda u: -sum(por.get(u.pk, {}).values() or [0]))
        principais, resto = ordem[:MAX_SERIES - 1], ordem[MAX_SERIES - 1:]
        if len(resto) == 1:
            principais, resto = ordem, []
        for u in principais:
            series.append(serie(u.nome, [por.get(u.pk, {}).get(d, 0) for d in datas], pilha="g"))
        if resto:
            series.append(serie(f"Outras ({len(resto)})",
                                [sum(por.get(u.pk, {}).get(d, 0) for u in resto) for d in datas], pilha="g"))
        empilhado = True
    else:
        total = services.serie_diaria(usinas, datas[0], datas[-1])
        series.append(serie("Gerado", [total.get(d, 0) for d in datas], papel="geracao"))
        empilhado = False
    if any(esperado):
        series.append(serie("Esperado", esperado, papel="esperado", tipo="line", tracejado=True))
    return grafico(rotulos, series, empilhado=empilhado, casas=1)


def geracao_mensal(usinas, meses=12):
    dados = services.serie_mensal(usinas, services.ultimos_meses(meses))
    rot = [rotulo_mes(m) for m, _, _ in dados]
    series = [serie("Gerado", [g for _, g, _ in dados], papel="geracao")]
    if any(e for _, _, e in dados):
        series.append(serie("Esperado", [e for _, _, e in dados], papel="esperado", tipo="line", tracejado=True))
    return grafico(rot, series)


def curva_hoje(usinas):
    hoje = timezone.localdate()
    pontos = services.curva_do_dia(usinas, hoje)
    if not pontos:
        return None
    return grafico([h for h, _ in pontos], [serie("Potência", [kw for _, kw in pontos], papel="geracao")],
                   unidade="kW", tipo="area", casas=1)


def desempenho_usinas(resumos):
    itens = sorted([r for r in resumos if r.pct_7d is not None], key=lambda r: r.pct_7d)
    if not itens:
        return None
    cores = ["critico" if r.situacao in ("parada", "sem_comunicacao") else
             "atencao" if r.pct_7d < 80 else "bom" for r in itens]
    return grafico([r.usina.nome for r in itens], [serie("Desempenho (7 dias)", [r.pct_7d for r in itens],
                                                         cores=cores)], unidade="% do esperado", horizontal=True)


def por_fabricante(inversores_qs):
    kwp = defaultdict(Decimal)
    for inv in inversores_qs.select_related("usina"):
        n = max(len(inv.usina.inversores.all()), 1)
        kwp[inv.marca] += (inv.usina.potencia_kwp or Decimal(0)) / n
    itens = sorted(kwp.items(), key=lambda x: -x[1])
    if not itens:
        return None
    if len(itens) > MAX_SERIES:
        itens = itens[:MAX_SERIES - 1] + [("Outros", sum(v for _, v in itens[MAX_SERIES - 1:]))]
    return grafico([m for m, _ in itens], [serie("kWp", [v for _, v in itens])], unidade="kWp", tipo="rosca", casas=1)
