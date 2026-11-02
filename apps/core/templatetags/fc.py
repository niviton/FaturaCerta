"""Tags do design system: ícones, sparklines e formatação pt-BR."""

from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

# nomes antigos (menus) -> ícones Lucide
ALIAS = {
    "grade": "layout-dashboard", "raio": "zap", "pessoas": "users", "documento": "file-text", "chave": "key-round",
    "engrenagem": "settings", "predio": "building-2", "plugue": "plug", "escudo": "shield-check",
}


@register.simple_tag
def icone(nome, classe="", rotulo=""):
    nome = ALIAS.get(nome, nome)
    aria = format_html(' role="img" aria-label="{}"', rotulo) if rotulo else mark_safe(' aria-hidden="true"')
    return format_html('<svg class="i {}"{}><use href="#i-{}"/></svg>', classe, aria, nome)


TONS = {"ok": "--ok", "danger": "--danger", "solar": "--solar", "brand": "--brand", "accent": "--accent", "muted": "--muted"}


@register.simple_tag
def sparkline(valores, tom="brand", largura=160, altura=38):
    """Linha com área em gradiente; o último ponto ganha destaque."""
    v = [float(x) for x in (valores or []) if x is not None]
    if len(v) < 2:
        return ""
    mn, mx = min(v), max(v)
    faixa = (mx - mn) or 1
    passo = largura / (len(v) - 1)
    pts = [(i * passo, altura - 4 - (y - mn) / faixa * (altura - 8)) for i, y in enumerate(v)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"0,{altura} {linha} {largura},{altura}"
    cor = f"var({TONS.get(tom, '--brand')})"
    gid = f"sg{abs(hash((tuple(v), tom))) % 10**8}"
    ux, uy = pts[-1]
    return format_html(
        '<svg class="kpi-spark" viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
        '<defs><linearGradient id="{g}" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="{c}" stop-opacity=".28"/><stop offset="1" stop-color="{c}" stop-opacity="0"/>'
        '</linearGradient></defs>'
        '<polygon points="{a}" fill="url(#{g})"/>'
        '<polyline points="{l}" fill="none" stroke="{c}" stroke-width="1.75" vector-effect="non-scaling-stroke" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        '<circle cx="{ux}" cy="{uy}" r="2.6" fill="{c}" vector-effect="non-scaling-stroke"/></svg>',
        w=largura, h=altura, g=gid, c=cor, a=area, l=linha, ux=f"{ux:.1f}", uy=f"{uy:.1f}")


def _fmt(valor, casas):
    """Número no padrão brasileiro; texto que não é número volta como está."""
    if valor in (None, ""):
        return None
    try:
        return number_format(Decimal(str(valor)), int(casas), force_grouping=True)
    except (InvalidOperation, ValueError, TypeError):
        return str(valor)


@register.filter
def brl(valor, casas=2):
    v = _fmt(valor, casas)
    return "—" if v is None else f"R$ {v}"


@register.filter
def kwh(valor, casas=1):
    v = _fmt(valor, casas)
    return "—" if v is None else f"{v} kWh"


@register.filter
def ptbr(valor, casas=0):
    v = _fmt(valor, casas)
    return "—" if v is None else v


@register.simple_tag
def anel(pct, rotulo=""):
    """Anel de desempenho pequeno (SVG): ≥ 85% verde, 60–85% âmbar, < 60% vermelho."""
    if pct is None:
        return format_html('<figure><div class="anel" title="{} sem esperado"><svg viewBox="0 0 44 44" aria-hidden="true">'
                           '<circle class="trilho" cx="22" cy="22" r="18"/></svg><span class="muted">—</span></div>'
                           '<figcaption>{}</figcaption></figure>', rotulo, rotulo)
    p = max(min(int(pct), 100), 0)
    cor = "var(--ok)" if pct >= 85 else "var(--solar)" if pct >= 60 else "var(--danger)"
    circ = 2 * 3.14159 * 18
    return format_html(
        '<figure><div class="anel" role="img" aria-label="{r}: {v}% do esperado">'
        '<svg viewBox="0 0 44 44" aria-hidden="true">'
        '<circle class="trilho" cx="22" cy="22" r="18"/>'
        '<circle class="arco" cx="22" cy="22" r="18" stroke="{c}" stroke-dasharray="{d} {t}"/></svg>'
        '<span>{v}</span></div><figcaption>{r}</figcaption></figure>',
        r=rotulo, v=int(pct), c=cor, d=f"{circ * p / 100:.1f}", t=f"{circ:.1f}")


@register.filter
def cor_texto(hex_cor):
    """Cor de texto legível sobre a cor dada (preto ou branco), pela luminância relativa."""
    h = str(hex_cor or "").lstrip("#")
    if len(h) != 6:
        return "#0B1200"
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return "#0B1200" if lum > 0.36 else "#FFFFFF"


@register.filter
def iniciais(texto):
    partes = [p for p in str(texto).split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"
