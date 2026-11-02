from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


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
