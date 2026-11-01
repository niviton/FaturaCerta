from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

from .validators import validar_cnpj

cor_hex = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Use uma cor hexadecimal, ex.: #E8A900")


class Integradora(models.Model):
    """Tenant: a empresa integradora que assina o sistema."""

    razao_social = models.CharField(max_length=200)
    nome_fantasia = models.CharField(max_length=120, blank=True)
    cnpj = models.CharField(max_length=18, unique=True, validators=[validar_cnpj])
    responsavel_tecnico_nome = models.CharField("responsável técnico", max_length=120, blank=True)
    responsavel_tecnico_crea = models.CharField("CREA", max_length=30, blank=True)
    logo = models.ImageField(upload_to="logos/", blank=True)
    cor_marca = models.CharField(max_length=7, default="#13233A", validators=[cor_hex])
    email_contato = models.EmailField(blank=True)
    telefone_contato = models.CharField(max_length=20, blank=True)
    ativa = models.BooleanField(default=True)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["razao_social"]

    def __str__(self):
        return self.nome_fantasia or self.razao_social


class TenantQuerySet(models.QuerySet):
    def da_integradora(self, integradora):
        if integradora is None:
            return self.none()
        return self.filter(integradora=integradora)


class TenantModel(models.Model):
    """Base de todo dado que pertence a uma integradora."""

    integradora = models.ForeignKey(Integradora, on_delete=models.CASCADE, related_name="+")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = TenantQuerySet.as_manager()

    class Meta:
        abstract = True


class LogAuditoria(models.Model):
    """Quem viu, alterou ou exportou dados (LGPD)."""

    class Acao(models.TextChoices):
        VER = "ver", "Visualizou"
        CRIAR = "criar", "Criou"
        ALTERAR = "alterar", "Alterou"
        EXCLUIR = "excluir", "Excluiu"
        EXPORTAR = "exportar", "Exportou"

    momento = models.DateTimeField(auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    integradora = models.ForeignKey(Integradora, null=True, blank=True, on_delete=models.SET_NULL)
    acao = models.CharField(max_length=10, choices=Acao.choices)
    objeto_tipo = models.CharField(max_length=60)
    objeto_id = models.CharField(max_length=40, blank=True)
    descricao = models.CharField(max_length=255, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-momento"]
        verbose_name = "log de auditoria"
        verbose_name_plural = "logs de auditoria"

    def __str__(self):
        return f"{self.momento:%d/%m/%Y %H:%M} {self.usuario} {self.acao} {self.objeto_tipo}#{self.objeto_id}"
