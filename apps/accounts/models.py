from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    """Três níveis: administrador geral (plataforma), integradora (gestor/técnico) e cliente final."""

    class Papel(models.TextChoices):
        ADMIN_INTERNO = "admin", "Administrador geral"
        GESTOR = "gestor", "Integradora: gestor"
        TECNICO = "tecnico", "Integradora: técnico"
        CLIENTE = "cliente", "Cliente final"

    papel = models.CharField(max_length=10, choices=Papel.choices, default=Papel.TECNICO)
    integradora = models.ForeignKey(
        "core.Integradora", null=True, blank=True, on_delete=models.CASCADE, related_name="usuarios"
    )
    cliente = models.ForeignKey(
        "cadastro.Cliente", null=True, blank=True, on_delete=models.CASCADE, related_name="usuarios",
        help_text="Só para o papel cliente final.",
    )
    telefone = models.CharField(max_length=20, blank=True)

    def clean(self):
        super().clean()
        if self.papel == self.Papel.ADMIN_INTERNO:
            return
        if not self.integradora_id:
            raise ValidationError({"integradora": "Escolha a integradora deste usuário."})
        if self.papel == self.Papel.CLIENTE:
            if not self.cliente_id:
                raise ValidationError({"cliente": "Escolha o cliente que este usuário vai acompanhar."})
            if self.cliente.integradora_id != self.integradora_id:
                raise ValidationError({"cliente": "O cliente pertence a outra integradora."})

    @property
    def is_admin_geral(self):
        return self.is_superuser or self.papel == self.Papel.ADMIN_INTERNO

    @property
    def is_gestor(self):
        return self.papel == self.Papel.GESTOR

    @property
    def is_equipe(self):
        return self.papel in (self.Papel.GESTOR, self.Papel.TECNICO) and self.integradora_id is not None

    @property
    def is_cliente_final(self):
        return self.papel == self.Papel.CLIENTE and self.cliente_id is not None

    @property
    def nome_exibicao(self):
        return self.get_full_name() or self.username
