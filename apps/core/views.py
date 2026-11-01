from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def home(request):
    u = request.user
    if u.is_equipe:
        return redirect("monitoramento:painel")
    if u.is_superuser or u.papel == u.Papel.ADMIN_INTERNO:
        return redirect("admin:index")
    # Portal do cliente final entra na fase 10.
    return render(request, "core/em_breve.html")
