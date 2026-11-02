"""Screenshot de uma tela, logado como um usuário (revisão visual rápida).

Uso: .venv/Scripts/python scripts/olhar.py <caminho> <usuario> <arquivo.png> [escuro|claro] [largura] [inteira]
Ex.: .venv/Scripts/python scripts/olhar.py /painel/ gestor painel.png claro 1440 inteira
"""

import sys

from playwright.sync_api import sync_playwright

caminho, usuario, arquivo = sys.argv[1:4]
tema = sys.argv[4] if len(sys.argv) > 4 else "escuro"
largura = int(sys.argv[5]) if len(sys.argv) > 5 else 1440
inteira = len(sys.argv) > 6 and sys.argv[6] == "inteira"

with sync_playwright() as p:
    nav = p.chromium.launch(channel="msedge")
    ctx = nav.new_context(viewport={"width": largura, "height": 900 if largura > 600 else 844},
                          color_scheme="light" if tema == "claro" else "dark")
    ctx.add_init_script(f"try{{localStorage.setItem('fc-tema','{tema}')}}catch(e){{}}")
    pag = ctx.new_page()
    erros = []
    pag.on("pageerror", lambda e: erros.append(str(e)))
    if usuario != "-":
        pag.goto("http://127.0.0.1:8000/entrar/")
        pag.fill("#id_username", usuario)
        pag.fill("#id_password", "FaturaCerta@2026")
        pag.click("button[type=submit]")
        pag.wait_for_load_state("load")
    pag.goto(f"http://127.0.0.1:8000{caminho}")
    pag.wait_for_load_state("load")
    pag.wait_for_timeout(2800)
    pag.screenshot(path=arquivo, full_page=inteira)
    print("erros de JS:", erros or "nenhum")
    nav.close()
