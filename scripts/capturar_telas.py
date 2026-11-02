"""Tira screenshots de todas as telas, por perfil, em desktop (1440px) e celular (390px).

Uso (com o servidor rodando e o seed_demo carregado):
    .venv/Scripts/python scripts/capturar_telas.py docs/design/antes
    .venv/Scripts/python scripts/capturar_telas.py docs/design/depois --tema claro
    .venv/Scripts/python scripts/capturar_telas.py docs/design/etapa1 --so design

Usa o Edge instalado (channel="msedge"); em Linux/Mac, troque por chromium com `playwright install chromium`.
"""

import argparse
import os
import sys
from pathlib import Path

import django

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from playwright.sync_api import sync_playwright  # noqa: E402

from apps.cadastro.models import Cliente, UnidadeConsumidora, Usina  # noqa: E402

URL = "http://127.0.0.1:8000"
SENHA = "FaturaCerta@2026"
TAMANHOS = {"desktop": {"width": 1440, "height": 900}, "celular": {"width": 390, "height": 844}}


def roteiro():
    padaria = Cliente.objects.filter(nome__startswith="Padaria").first()
    uc = UnidadeConsumidora.objects.filter(cliente=padaria).first()
    usina = Usina.objects.filter(uc_geradora__cliente=padaria).first()
    uc_a = UnidadeConsumidora.objects.filter(subgrupo="A4").first()
    cliente_usina = Usina.objects.filter(nome="Casa Lima").first()
    return {
        "anonimo": [("login", "/entrar/")],
        "admin": [
            ("plataforma", "/plataforma/"), ("integradoras", "/plataforma/integradoras/"),
            ("usuarios", "/plataforma/usuarios/"), ("integracoes", "/plataforma/integracoes/"),
            ("logs", "/plataforma/logs/"), ("manuais-admin", "/manuais/"), ("design", "/design/"),
        ],
        "gestor": [
            ("visao-integradora", "/painel/"), ("usinas-agora", "/usinas/"), ("clientes", "/cadastro/clientes/"),
            ("cliente-resumo", f"/cadastro/clientes/{padaria.pk}/"),
            ("cliente-ucs", f"/cadastro/clientes/{padaria.pk}/?aba=ucs"),
            ("cliente-equipamentos", f"/cadastro/clientes/{padaria.pk}/?aba=equipamentos"),
            ("cliente-acesso", f"/cadastro/clientes/{padaria.pk}/?aba=acesso"),
            ("uc-analise", f"/cadastro/ucs/{uc.pk}/"), ("uc-analise-grupo-a", f"/cadastro/ucs/{uc_a.pk}/"),
            ("uc-perfil", f"/cadastro/ucs/{uc.pk}/?aba=perfil"), ("usina", f"/cadastro/usinas/{usina.pk}/"),
            ("faturas", "/faturas/"), ("fatura-nova", f"/faturas/nova/?uc={uc.pk}"),
            ("cliente-novo", "/cadastro/clientes/novo/"), ("equipe", "/equipe/"),
            ("configuracoes", "/cadastro/integradora/"), ("manuais-integradora", "/manuais/"),
        ],
        "lima": [("portal-inicio", "/meu/"), ("portal-usina", f"/meu/usinas/{cliente_usina.pk}/")],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("saida")
    ap.add_argument("--tema", choices=["escuro", "claro"], default="escuro")
    ap.add_argument("--so", help="captura só as telas cujo nome contém este texto")
    args = ap.parse_args()
    saida = BASE / args.saida
    saida.mkdir(parents=True, exist_ok=True)
    plano = roteiro()  # consulta o banco antes do Playwright abrir o loop assíncrono

    with sync_playwright() as p:
        nav = p.chromium.launch(channel="msedge")
        for perfil, telas in plano.items():
            telas = [t for t in telas if not args.so or args.so in t[0]]
            if not telas:
                continue
            for nome_tam, tam in TAMANHOS.items():
                ctx = nav.new_context(viewport=tam, device_scale_factor=1, locale="pt-BR",
                                      color_scheme="light" if args.tema == "claro" else "dark")
                ctx.add_init_script(f"try{{localStorage.setItem('fc-tema','{args.tema}')}}catch(e){{}}")
                pag = ctx.new_page()
                if perfil != "anonimo":
                    pag.goto(f"{URL}/entrar/")
                    pag.fill("#id_username", perfil)
                    pag.fill("#id_password", SENHA)
                    pag.click("button[type=submit]")
                    pag.wait_for_load_state("networkidle")
                for nome, caminho in telas:
                    resp = pag.goto(f"{URL}{caminho}")
                    if resp is None or resp.status >= 400:
                        print(f"  pulei {nome}: HTTP {resp.status if resp else '?'}")
                        continue
                    pag.wait_for_load_state("load")
                    try:  # o mapa segue baixando partes do mapa; não espera a rede parar para sempre
                        pag.wait_for_load_state("networkidle", timeout=6000)
                    except Exception:  # noqa: BLE001
                        pass
                    pag.wait_for_timeout(1500)  # animação de entrada dos gráficos
                    arquivo = saida / f"{nome}_{nome_tam}{'_claro' if args.tema == 'claro' else ''}.jpg"
                    pag.screenshot(path=str(arquivo), full_page=True, type="jpeg", quality=78)
                    print(f"  {arquivo.relative_to(BASE)}")
                ctx.close()
        nav.close()


if __name__ == "__main__":
    main()
