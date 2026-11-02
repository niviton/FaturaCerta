from django.urls import reverse


def _item(request, titulo, nome, icone, exato=False):
    url = reverse(nome)
    ativo = request.path == url if exato else request.path.startswith(url)
    return {"titulo": titulo, "url": url, "icone": icone, "ativo": ativo}


def tenant(request):
    ctx = {"tenant": getattr(request, "tenant", None), "atuando": getattr(request, "atuando", False)}
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated or u.is_cliente_final:
        return ctx

    menus = []
    if u.is_admin_geral:
        menus.append({"titulo": "Plataforma", "itens": [
            _item(request, "Visão geral", "plataforma:visao", "grade", exato=True),
            _item(request, "Integradoras", "plataforma:integradoras", "predio"),
            _item(request, "Usuários", "plataforma:usuarios", "pessoas"),
            _item(request, "Integrações e APIs", "plataforma:integracoes", "plugue"),
            _item(request, "Logs de auditoria", "plataforma:logs", "escudo"),
            _item(request, "Manuais", "manuais", "documento"),
        ]})
    if ctx["tenant"] is not None:
        itens = [
            _item(request, "Visão geral", "painel:visao", "grade", exato=True),
            _item(request, "Usinas agora", "monitoramento:painel", "raio"),
            _item(request, "Clientes", "cadastro:clientes", "pessoas"),
            _item(request, "Faturas", "faturas:lista", "documento"),
        ]
        if u.is_gestor or u.is_admin_geral:
            itens += [
                _item(request, "Equipe e acessos", "equipe:usuarios", "chave"),
                _item(request, "Configurações", "cadastro:integradora", "engrenagem"),
            ]
        if not u.is_admin_geral:  # o administrador já tem "Manuais" no grupo Plataforma
            itens.append(_item(request, "Manuais", "manuais", "documento"))
        menus.append({"titulo": "Integradora" if u.is_admin_geral else "", "itens": itens})
    ctx["menus"] = menus
    return ctx
