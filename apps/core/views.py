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
