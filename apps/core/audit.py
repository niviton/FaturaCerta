from .models import LogAuditoria


def ip_do_request(request):
    fwd = request.META.get("HTTP_X_FORWARDED_FOR")
    return (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR")) or None


def registrar(request, acao, obj=None, descricao="", objeto_tipo=""):
    user = request.user if request.user.is_authenticated else None
    LogAuditoria.objects.create(
        usuario=user,
        integradora=getattr(request, "tenant", None),
        acao=acao,
        objeto_tipo=objeto_tipo or (obj._meta.model_name if obj is not None else ""),
        objeto_id=str(obj.pk) if obj is not None and obj.pk else "",
        descricao=descricao[:255],
        ip=ip_do_request(request),
    )
