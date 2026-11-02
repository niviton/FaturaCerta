"""Gráficos SVG gerados no servidor (sem JS)."""

from django import template
from django.utils.formats import number_format
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def barras_geracao(dias, largura=560, altura=140, compacto=False):
    """Barras de geração diária com a linha do esperado. `dias` = [(data, kwh, esperado)]."""
    if not dias:
        return ""
    topo = max([float(g) for _, g, _ in dias] + [float(e or 0) for _, _, e in dias] + [1]) * 1.1
    pad_b = 0 if compacto else 18
    h = altura - pad_b
    passo = largura / len(dias)
    larg_barra = passo * 0.68
    barras, rotulos, esperado_pts = [], [], []
    for i, (dia, g, e) in enumerate(dias):
        x = i * passo + (passo - larg_barra) / 2
        bh = float(g) / topo * h
        baixo = e and float(g) < float(e) * 0.8
        classe = "barra baixa" if baixo else "barra"
        titulo = f"{dia:%d/%m}: {number_format(g, 1)} kWh" + (f" (esperado {number_format(e, 1)})" if e else "")
        barras.append((classe, f"{x:.1f}", f"{h - bh:.1f}", f"{larg_barra:.1f}", f"{max(bh, 1):.1f}", titulo))
        if e:
            esperado_pts.append(f"{i * passo:.1f},{h - float(e) / topo * h:.1f} "
                                f"{(i + 1) * passo:.1f},{h - float(e) / topo * h:.1f}")
        if not compacto and (i % max(len(dias) // 7, 1) == 0 or i == len(dias) - 1):
            rotulos.append((f"{x + larg_barra / 2:.1f}", altura - 4, f"{dia:%d/%m}"))
    rects = format_html_join(
        "", '<rect class="{}" x="{}" y="{}" width="{}" height="{}" rx="1"><title>{}</title></rect>', barras)
    textos = format_html_join("", '<text x="{}" y="{}" text-anchor="middle">{}</text>', rotulos)
    linha = mark_safe(f'<polyline class="esperado" points="{" ".join(esperado_pts)}"/>') if esperado_pts else ""
    resumo = f"Geração diária dos últimos {len(dias)} dias"
    return format_html(
        '<svg class="mini{}" viewBox="0 0 {} {}" preserveAspectRatio="none" role="img" aria-label="{}">{}{}{}</svg>',
        " compacto" if compacto else "", largura, altura, resumo, rects, linha, textos)
