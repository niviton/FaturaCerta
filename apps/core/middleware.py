class TenantMiddleware:
    """Anexa a integradora do usuário logado em request.tenant."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        request.tenant = getattr(user, "integradora", None) if user and user.is_authenticated else None
        return self.get_response(request)
