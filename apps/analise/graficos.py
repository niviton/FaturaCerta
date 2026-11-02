"""Gráficos da análise da conta (balanço energético e cruzamento das três fontes)."""

from decimal import Decimal

from apps.core import charts
from apps.core.graficos import grafico, serie

from .services import balancos_uc


def balanco_energetico(balancos):
    """Para onde foi a energia: consumo real = autoconsumo (sol na hora) + o que veio da rede. Linha: geração."""
    bs = [b for b in balancos if b.importacao_ref is not None]
    if not bs:
        return None
    rot = [b.rotulo for b in bs]
    series = [
        serie("Autoconsumo (sol na hora)", [max(b.autoconsumo_kwh or 0, 0) for b in bs], papel="autoconsumo", pilha="c"),
        serie("Consumido da rede", [b.importacao_ref for b in bs], papel="rede", pilha="c"),
    ]
    if any(b.geracao_kwh is not None for b in bs):
        series.append(serie("Geração do inversor", [b.geracao_kwh for b in bs], papel="geracao", tipo="line"))
    return grafico(rot, series, empilhado=True)


def injetado_compensado(balancos):
    bs = [b for b in balancos if b.fatura]
    if not bs:
        return None
    return grafico([b.rotulo for b in bs], [
        serie("Injetado (fatura)", [b.fat_injetada for b in bs], papel="injecao"),
        serie("Compensado (fatura)", [b.fat_compensada for b in bs], papel="autoconsumo"),
    ])


def consumo_tres_fontes(balancos):
    """Consumo da rede: o que a concessionária cobrou × o que o nosso medidor mediu."""
    bs = [b for b in balancos if b.fatura and b.esp_importacao_kwh is not None]
    if not bs:
        return None
    return grafico([b.rotulo for b in bs], [
        serie("Faturado pela concessionária", [b.fat_consumo for b in bs], papel="fatura"),
        serie("Medido pelo medidor próprio", [b.esp_importacao_kwh for b in bs], papel="carga"),
    ])


def custo(balancos):
    bs = [b for b in balancos if b.fat_total is not None]
    if not bs:
        return None
    series = [serie("Pago na fatura", [b.fat_total for b in bs], papel="injecao")]
    if any(b.custo_sem_solar_estimado for b in bs):
        series.append(serie("Sem solar (estimativa)", [b.custo_sem_solar_estimado for b in bs], papel="rede"))
    return grafico([b.rotulo for b in bs], series, unidade="R$", casas=2)


# ------------------------------------------------------------------ gráficos do design system (ECharts)
D0 = Decimal(0)


def partes_injecao(b):
    """Divide a energia injetada em (compensado, virou crédito, não compensado sem explicação).

    Não compensado é só o que poderia ter abatido o consumo do mês e não abateu (mesma conta do indício
    "injeção não compensada"); o resto que sobrou vira crédito, o que é legítimo.
    """
    inj = b.injetada_ref or D0
    if not b.fatura:
        return inj, D0, D0
    f = b.fatura
    comp = min(f.energia_compensada_kwh, inj)
    disp = Decimal(f.custo_disponibilidade_kwh or b.uc.custo_disponibilidade_kwh or 0)
    compensavel = max(f.consumo_kwh - disp, D0)
    nao_comp = max(min(inj, compensavel) - f.energia_compensada_kwh, D0)
    credito = max(inj - comp - nao_comp, D0)
    return comp, credito, nao_comp


def sankey_balanco(b):
    """Fluxo de energia de um período: gerado → instantâneo / injetado → compensado, crédito ou não compensado."""
    if b is None or b.geracao_kwh is None or b.injetada_ref is None:
        return None
    comp, credito, nao_comp = partes_injecao(b)
    instantaneo = max(b.geracao_kwh - b.injetada_ref, D0)
    return charts.sankey(b.geracao_kwh, instantaneo, b.injetada_ref, comp, nao_comp, credito)


def cascata_balanco(b):
    """Da conta sem solar (estimada pela tarifa de referência) até o total cobrado. Estimativa, não laudo."""
    if b is None or not b.fatura or b.custo_sem_solar_estimado is None or b.tarifa is None:
        return None
    f, t = b.fatura, b.tarifa
    sem = b.custo_sem_solar_estimado
    auto = (max(b.autoconsumo_kwh or D0, D0) * t).quantize(Decimal("0.01"))
    comp = (f.energia_compensada_kwh * t).quantize(Decimal("0.01"))
    fio_b = f.valor_fio_b or D0
    cip = f.valor_cip or D0
    extras = (f.valor_ultrapassagem or D0) + (f.valor_reativo or D0)
    ajuste = f.valor_total - (sem - auto - comp + fio_b + cip + extras)
    itens = [{"rotulo": "Conta sem solar (estimada)", "curto": "Sem solar", "valor": sem, "tipo": "total"}]
    if auto:
        itens.append({"rotulo": "Consumo instantâneo", "curto": "Instantâneo", "valor": auto, "tipo": "menos"})
    if comp:
        itens.append({"rotulo": "Energia compensada", "curto": "Compensada", "valor": comp, "tipo": "menos"})
    if fio_b:
        itens.append({"rotulo": "Fio B não compensado", "curto": "Fio B", "valor": fio_b, "tipo": "mais"})
    if cip:
        itens.append({"rotulo": "Iluminação pública (CIP)", "curto": "CIP", "valor": cip, "tipo": "mais"})
    if extras:
        itens.append({"rotulo": "Demanda e reativo", "curto": "Demanda", "valor": extras, "tipo": "mais"})
    if abs(ajuste) >= 1:
        itens.append({"rotulo": "Disponibilidade, tributos e ajustes", "curto": "Tributos e outros",
                      "valor": abs(ajuste), "tipo": "mais" if ajuste > 0 else "menos"})
    itens.append({"rotulo": "Conta com solar (cobrada)", "curto": "Com solar", "valor": f.valor_total, "tipo": "total"})
    return charts.cascata(itens)


def conferencia(b):
    """Linhas faturado × medido/esperado, com a diferença. Só o que dá para conferir com as fontes disponíveis."""
    if b is None or not b.fatura:
        return []
    f = b.fatura
    linhas = []
    if b.esp_importacao_kwh is not None:
        linhas.append(("Consumo da rede", f.consumo_kwh, b.esp_importacao_kwh, "medidor próprio"))
    if b.esp_exportacao_kwh is not None:
        linhas.append(("Energia injetada", f.energia_injetada_kwh, b.esp_exportacao_kwh, "medidor próprio"))
    if f.energia_injetada_kwh:
        disp = Decimal(f.custo_disponibilidade_kwh or b.uc.custo_disponibilidade_kwh or 0)
        compensavel = min(f.energia_injetada_kwh + (f.saldo_creditos_kwh or D0), max(f.consumo_kwh - disp, D0))
        linhas.append(("Energia compensada", f.energia_compensada_kwh, compensavel, "possível pela regra"))
    if f.consumo_pela_leitura is not None:
        linhas.append(("Leitura × constante", f.consumo_kwh, f.consumo_pela_leitura, "leitura do medidor"))
    out = []
    for nome, faturado, esperado, fonte in linhas:
        dif = faturado - esperado
        rel = abs(dif) / esperado if esperado else (D0 if not dif else Decimal(1))
        out.append({"nome": nome, "faturado": faturado, "esperado": esperado, "fonte": fonte, "diferenca": dif,
                    "diverge": rel > Decimal("0.05") and abs(dif) > 5})
    return out


def carteira(ucs, meses=12):
    """Agregados da carteira: fluxo de energia da última fatura de cada UC e injetado × compensado em 12 meses."""
    from apps.monitoramento.services import ultimos_meses

    ultimos = []
    por_mes = {}
    tarifa = None
    for uc in ucs:
        bal = balancos_uc(uc, meses)
        com_fatura = [b for b in bal if b.fatura]
        if com_fatura:
            ultimos.append(com_fatura[-1])
        for b in com_fatura:
            m = b.fatura.mes_referencia
            inj, comp, perd = por_mes.get(m, (D0, D0, D0))
            por_mes[m] = (inj + b.fat_injetada, comp + b.fat_compensada, perd + partes_injecao(b)[2])
            tarifa = tarifa or b.tarifa
    g_sankey = None
    validos = [b for b in ultimos if b.geracao_kwh is not None]
    if validos:
        partes = [partes_injecao(b) for b in validos]
        ger = sum((b.geracao_kwh for b in validos), D0)
        inj = sum((b.injetada_ref for b in validos), D0)
        g_sankey = charts.sankey(ger, max(ger - inj, D0), inj, sum((p[0] for p in partes), D0),
                                 sum((p[2] for p in partes), D0), sum((p[1] for p in partes), D0))
    g_barras = None
    perdido_kwh = D0
    if por_mes:
        ms = [m for m in ultimos_meses(meses) if m in por_mes]
        inj = [por_mes[m][0] for m in ms]
        comp = [por_mes[m][1] for m in ms]
        anot = []
        for i, m in enumerate(ms):
            perd = por_mes[m][2]
            if perd > 50:
                texto = f"{int(perd)} kWh"
                if tarifa:
                    texto = f"≈ R$ {int(perd * tarifa):,}".replace(",", ".")
                anot.append({"indice": i, "texto": texto})
        if ms:
            perdido_kwh = por_mes[ms[-1]][2]
        g_barras = charts.barras_agrupadas(
            [charts.rotulo_mes(m) for m in ms],
            [{"nome": "Injetado", "valores": inj, "tom": "brand"}, {"nome": "Compensado", "valores": comp, "tom": "ok"}],
            anot)
    return {"sankey": g_sankey, "injetado": g_barras, "ultimos": ultimos, "perdido_kwh": perdido_kwh, "tarifa": tarifa}
