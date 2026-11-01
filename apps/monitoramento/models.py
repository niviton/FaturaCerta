from django.db import models


class GeracaoDiaria(models.Model):
    inversor = models.ForeignKey("cadastro.Inversor", on_delete=models.CASCADE, related_name="geracoes")
    data = models.DateField()
    kwh = models.DecimalField(max_digits=10, decimal_places=2)
    demo = models.BooleanField(default=False)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["data"]
        verbose_name = "geração diária"
        verbose_name_plural = "gerações diárias"
        constraints = [models.UniqueConstraint(fields=["inversor", "data"], name="geracao_unica_por_dia")]
        indexes = [models.Index(fields=["data"])]

    def __str__(self):
        return f"{self.inversor} {self.data}: {self.kwh} kWh"


class StatusAtual(models.Model):
    """Última leitura instantânea do inversor."""

    inversor = models.OneToOneField("cadastro.Inversor", on_delete=models.CASCADE, related_name="status_atual")
    online = models.BooleanField(default=False)
    potencia_atual_kw = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    energia_hoje_kwh = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    medido_em = models.DateTimeField(null=True, blank=True)
    coletado_em = models.DateTimeField(auto_now=True)
    demo = models.BooleanField(default=False)
    erro = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "status do inversor"
        verbose_name_plural = "status dos inversores"

    def __str__(self):
        return f"{self.inversor}: {'online' if self.online else 'offline'}"


class LeituraMedidor(models.Model):
    medidor = models.ForeignKey("cadastro.Medidor", on_delete=models.CASCADE, related_name="leituras")
    data = models.DateField()
    consumo_kwh = models.DecimalField(max_digits=10, decimal_places=2)
    injecao_kwh = models.DecimalField(max_digits=10, decimal_places=2)
    demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["data"]
        verbose_name = "leitura do medidor"
        verbose_name_plural = "leituras do medidor"
        constraints = [models.UniqueConstraint(fields=["medidor", "data"], name="leitura_unica_por_dia")]

    def __str__(self):
        return f"{self.medidor} {self.data}"
