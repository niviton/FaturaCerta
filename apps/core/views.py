from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from .audit import registrar
from .manuais import MANUAIS, manuais_do_usuario
from .models import LogAuditoria


@login_required
def home(request):
    u = request.user
    if u.is_admin_geral:
        return redirect("painel:visao" if request.tenant else "plataforma:visao")
    if u.is_equipe:
        return redirect("painel:visao")
    if u.is_cliente_final:
        return redirect("portal:inicio")
    return render(request, "core/em_breve.html")


TOKENS = [
    ("--bg", "#06080C", "#F3F5F8", "Fundo da página"),
    ("--surface", "#0D1117", "#FFFFFF", "Painéis"),
    ("--surface-2", "#141A23", "#EEF1F5", "Painéis internos, hover de linha"),
    ("--glass", "rgba(20,26,35,.62)", "rgba(255,255,255,.72)", "Painéis flutuantes, modais"),
    ("--text", "#F2F5F8", "#0B1220", "Texto"),
    ("--muted", "#8B95A5", "#5B6676", "Texto secundário (≥ 4,5:1)"),
    ("--accent", "#C8FF2E", "#5A7D00", "Energia, ação principal, valor positivo"),
    ("--brand", "#3D6BFF", "#2F56E0", "Marca, links, seleção"),
    ("--solar", "#FFB224", "#B86E00", "Geração, sol"),
    ("--danger", "#FF5A3C", "#C93A1E", "Divergência, usina parada"),
    ("--ok", "#2EE6A0", "#0E8A5F", "Confere, gerando normal"),
]


@login_required
def design(request):
    """Referência viva do design system (só administrador geral / staff)."""
    if not (request.user.is_admin_geral or request.user.is_staff):
        raise Http404
    serie = [31, 34, 33, 36, 35, 38, 41, 39, 42, 44, 43, 47]
    ctx = {
        "tokens": TOKENS,
        "categoricas": [f"--c{i}" for i in range(1, 9)],
        "escala": [(12, "Rótulos pequenos, tabelas densas"), (14, "Texto da interface"), (16, "Texto de leitura"),
                   (20, "Título de painel"), (24, "Título de seção"), (32, "Título de página"),
                   (44, "Número de destaque no celular"), (64, "Número do cartão-herói")],
        "serie": serie, "serie_ruim": [12, 11, 13, 12, 15, 14, 17, 19, 18, 22, 24, 29],
        "filtros": [{"rotulo": "Todas", "valor": "todas", "contador": 50}, {"rotulo": "Normal", "valor": "ok",
                     "contador": 40, "tom": "ok"}, {"rotulo": "Com alerta", "valor": "alerta", "contador": 6,
                     "tom": "solar"}, {"rotulo": "Crítico", "valor": "critico", "contador": 3, "tom": "danger"},
                    {"rotulo": "Sem comunicação", "valor": "sem", "contador": 1}],
        "colunas": [{"titulo": "Usina"}, {"titulo": "Cliente"}, {"titulo": "Potência", "num": True},
                    {"titulo": "Hoje", "num": True}, {"titulo": "7 dias", "num": True}],
        "linhas": [
            {"href": "#", "celulas": [{"v": "Padaria · telhado", "sub": "Growatt MID 15KTL3-X"},
                                      {"v": "Padaria Sol Nascente"}, {"v": "18,7 kWp", "num": True},
                                      {"v": "102,8 kWh", "num": True}, {"v": "108%", "num": True}]},
            {"href": "#", "celulas": [{"v": "Pajuçara · estacionamento", "sub": "Deye SUN-40K-G03"},
                                      {"v": "Supermercado Pajuçara"}, {"v": "40,2 kWp", "num": True},
                                      {"v": "136,8 kWh", "num": True}, {"v": "68%", "num": True}]},
            {"href": "#", "celulas": [{"v": "Escola Nova Era", "sub": "Deye SUN-30K-G04"}, {"v": "Escola Nova Era"},
                                      {"v": "30,3 kWp", "num": True}, {"v": "0,0 kWh", "num": True},
                                      {"v": "0%", "num": True}]},
        ],
        "periodos": ["7D", "30D", "12M"],
        "skel": ["70%", "45%", "60%"],
        "nav_celular": [{"titulo": "Início", "url": "#", "icone": "house", "ativo": True},
                        {"titulo": "Usinas", "url": "#", "icone": "sun"},
                        {"titulo": "Contas", "url": "#", "icone": "receipt"},
                        {"titulo": "Ajuda", "url": "#", "icone": "info"}],
    }
    return render(request, "core/design.html", ctx)


@login_required
def manuais(request):
    itens = []
    for m in manuais_do_usuario(request.user):
        existe = m.arquivo.exists()
        itens.append({
            "manual": m, "existe": existe,
            "tamanho_kb": m.arquivo.stat().st_size // 1024 if existe else None,
            "atualizado": timezone.datetime.fromtimestamp(m.arquivo.stat().st_mtime, tz=timezone.get_current_timezone())
            if existe else None,
        })
    if not itens:
        raise Http404
    return render(request, "core/manuais.html", {"itens": itens})


@login_required
def manual_pdf(request, codigo):
    permitidos = {m.codigo for m in manuais_do_usuario(request.user)}
    manual = MANUAIS.get(codigo)
    if manual is None or codigo not in permitidos or not manual.arquivo.exists():
        raise Http404
    registrar(request, LogAuditoria.Acao.EXPORTAR, objeto_tipo="manual", descricao=manual.titulo)
    return FileResponse(manual.arquivo.open("rb"), content_type="application/pdf",
                        as_attachment=request.GET.get("baixar") == "1", filename=manual.arquivo.name)
