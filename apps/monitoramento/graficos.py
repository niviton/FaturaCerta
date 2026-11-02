"""Gráficos de monitoramento (geração, curva do dia, desempenho, fabricantes)."""

import datetime
from collections import defaultdict
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from apps.core import charts
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


# ------------------------------------------------------------------ gráficos do design system (ECharts)
def _pct(gerado, esperado):
    return None if not esperado else round(float(gerado) / float(esperado) * 100)


def desempenho_janelas(usinas, hoje=None):
    """{'Hoje': %, '15 dias': %, '30 dias': %, '12 meses': %} contra o esperado (None quando não há esperado)."""
    hoje = hoje or timezone.localdate()
    out = {}
    resumos = [services.resumir_usina(u, 1) for u in usinas]
    hoje_g = sum((r.hoje_kwh for r in resumos), Decimal(0))
    hoje_e = sum((r.esperado_hoje_kwh or 0 for r in resumos), Decimal(0))
    agora = timezone.localtime()
    fracao = min(max((agora.hour + agora.minute / 60 - 5.5) / 12, 0), 1)  # parte do dia de sol já passada
    out["Hoje"] = _pct(hoje_g, hoje_e * Decimal(str(fracao))) if fracao > 0.15 else None
    for rotulo, dias in (("15 dias", 15), ("30 dias", 30), ("12 meses", 365)):
        inicio = hoje - datetime.timedelta(days=dias)
        ger = sum(services.serie_diaria(usinas, inicio, hoje - datetime.timedelta(days=1)).values(), Decimal(0))
        esp = Decimal(0)
        d = inicio
        while d < hoje:
            esp += sum((services.esperado_no_dia(u, d) or Decimal(0) for u in usinas), Decimal(0))
            d += datetime.timedelta(days=1)
        out[rotulo] = _pct(ger, esp)
    return out


def aneis_usina(usinas):
    jan = desempenho_janelas(usinas)
    itens = [{"rotulo": k, "pct": v} for k, v in jan.items() if v is not None]
    return charts.aneis(itens) if itens else None


def geracao_x_esperado(usinas):
    """Área de geração com a faixa esperada (85% a 110%), em 7D, 30D e 12M."""
    hoje = timezone.localdate()

    def diario(n):
        datas = [hoje - datetime.timedelta(days=k) for k in range(n, 0, -1)]
        por = services.serie_diaria(usinas, datas[0], datas[-1])
        esp = [sum((services.esperado_no_dia(u, d) or Decimal(0) for u in usinas), Decimal(0)) for d in datas]
        return {"rotulos": [f"{d:%d/%m}" for d in datas], "gerado": [por.get(d, 0) for d in datas], "esperado": esp,
                "min": [e * Decimal("0.85") for e in esp], "max": [e * Decimal("1.1") for e in esp]}

    meses = services.serie_mensal(usinas, services.ultimos_meses(12))
    mensal = {"rotulos": [rotulo_mes(m) for m, _, _ in meses], "gerado": [g for _, g, _ in meses],
              "esperado": [e or 0 for _, _, e in meses], "min": [(e or 0) * Decimal("0.85") for _, _, e in meses],
              "max": [(e or 0) * Decimal("1.1") for _, _, e in meses]}
    return charts.geracao({"7D": diario(7), "30D": diario(30), "12M": mensal}, "30D")


def calendario_usinas(usinas, dias=365):
    hoje = timezone.localdate()
    inicio = hoje - datetime.timedelta(days=dias)
    por = services.serie_diaria(usinas, inicio, hoje - datetime.timedelta(days=1))
    if not por:
        return None
    serie = [(inicio + datetime.timedelta(days=k), por.get(inicio + datetime.timedelta(days=k), 0)) for k in range(dias)]
    return charts.calendario(serie)


def mapa_usinas(resumos):
    tons = {"gerando": "ok", "noite": "ok", "abaixo": "solar", "parada": "danger", "sem_comunicacao": "danger",
            "sem_inversor": "neutro"}
    pontos = []
    for r in resumos:
        u = r.usina
        lat, lon = u.latitude or u.uc_geradora.latitude, u.longitude or u.uc_geradora.longitude
        if lat is None or lon is None:
            continue
        pontos.append({"nome": u.nome, "lat": lat, "lon": lon, "status": tons[r.situacao], "rotulo": r.rotulo,
                       "kwp": u.potencia_kwp, "url": reverse("cadastro:usina", args=[u.pk])})
    return charts.mapa(pontos) if pontos else None


def rosca_fabricantes(inversores_qs):
    g = por_fabricante(inversores_qs)
    if not g:
        return None
    return charts.rosca([{"nome": r, "valor": v} for r, v in zip(g["rotulos"], g["series"][0]["valores"], strict=False)],
                        "kWp monitorados", "kWp")
