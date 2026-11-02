"""Gráficos da análise da conta (balanço energético e cruzamento das três fontes)."""

from apps.core.graficos import grafico, serie


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
