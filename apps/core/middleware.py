from .models import Integradora

SESSAO_ATUANDO = "atuando_integradora_id"


class TenantMiddleware:
    """Define request.tenant.

    Equipe e cliente: a integradora do próprio usuário.
    Administrador geral: a integradora escolhida em "atuar como" (guardada na sessão), ou nenhuma.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.tenant = None
        request.atuando = False
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            if user.is_admin_geral:
                iid = request.session.get(SESSAO_ATUANDO)
                if iid:
                    request.tenant = Integradora.objects.filter(pk=iid).first()
                    request.atuando = request.tenant is not None
            else:
                request.tenant = user.integradora
        return self.get_response(request)
