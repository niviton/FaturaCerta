from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


class User(AbstractUser):
    class Papel(models.TextChoices):
        ADMIN_INTERNO = "admin", "Administrador interno"
        GESTOR = "gestor", "Gestor da integradora"
        TECNICO = "tecnico", "Técnico da integradora"
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
        if self.papel != self.Papel.ADMIN_INTERNO and not self.integradora_id:
            raise ValidationError({"integradora": "Usuário que não é administrador interno precisa de integradora."})
        if self.papel == self.Papel.CLIENTE:
            if not self.cliente_id:
                raise ValidationError({"cliente": "Cliente final precisa estar vinculado a um cliente."})
            if self.cliente.integradora_id != self.integradora_id:
                raise ValidationError({"cliente": "O cliente pertence a outra integradora."})

    @property
    def is_gestor(self):
        return self.papel == self.Papel.GESTOR

    @property
    def is_equipe(self):
        return self.papel in (self.Papel.GESTOR, self.Papel.TECNICO) and self.integradora_id is not None

    @property
    def is_cliente_final(self):
        return self.papel == self.Papel.CLIENTE
