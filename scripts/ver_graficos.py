"""Abre a /design/ e salva um screenshot de cada painel de gráfico (para revisão). Lista erros de JavaScript.

Uso: .venv/Scripts/python scripts/ver_graficos.py <pasta> [escuro|claro] [largura]
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

saida = Path(sys.argv[1])
tema = sys.argv[2] if len(sys.argv) > 2 else "escuro"
largura = int(sys.argv[3]) if len(sys.argv) > 3 else 1440
saida.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    ctx = nav.new_context(viewport={"width": largura, "height": 900}, color_scheme="light" if tema == "claro" else "dark")
    ctx.add_init_script(f"try{{localStorage.setItem('fc-tema','{tema}')}}catch(e){{}}")
    pag = ctx.new_page()
    erros = []
    pag.on("console", lambda m: erros.append(m.text) if m.type == "error" else None)
    pag.on("pageerror", lambda e: erros.append(str(e)))
    pag.on("response", lambda r: erros.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
    pag.goto("http://127.0.0.1:8000/entrar/")
    pag.fill("#id_username", "admin")
    pag.fill("#id_password", "FaturaCerta@2026")
    pag.click("button[type=submit]")
    resp = pag.goto("http://127.0.0.1:8000/design/")
    print("status", resp.status)
    pag.wait_for_timeout(4000)
    for i, painel in enumerate(pag.query_selector_all(".grafico-painel")):
        painel.scroll_into_view_if_needed()
        pag.wait_for_timeout(900)
        painel.screenshot(path=str(saida / f"grafico_{i:02d}_{tema}_{largura}.png"))
    print("erros de JS:", erros or "nenhum")
    nav.close()
