from django.db import models


class GeracaoDiaria(models.Model):
    """Fonte 1 da auditoria: energia gerada por dia, lida da API do inversor."""

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


class AmostraPotencia(models.Model):
    """Potência instantânea do inversor (curva do dia)."""

    inversor = models.ForeignKey("cadastro.Inversor", on_delete=models.CASCADE, related_name="amostras")
    momento = models.DateTimeField()
    kw = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ["momento"]
        constraints = [models.UniqueConstraint(fields=["inversor", "momento"], name="amostra_unica")]
        indexes = [models.Index(fields=["momento"])]

    def __str__(self):
        return f"{self.inversor} {self.momento:%d/%m %H:%M}: {self.kw} kW"


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


class MedicaoBruta(models.Model):
    """O que o ESP32 envia: contadores acumulados e potência instantânea."""

    medidor = models.ForeignKey("cadastro.Medidor", on_delete=models.CASCADE, related_name="medicoes")
    momento = models.DateTimeField()
    potencia_w = models.DecimalField("potência na rede (W, + importando / − injetando)", max_digits=10,
                                     decimal_places=1, null=True, blank=True)
    importacao_kwh = models.DecimalField("contador de importação (kWh)", max_digits=12, decimal_places=3,
                                         null=True, blank=True)
    exportacao_kwh = models.DecimalField("contador de exportação (kWh)", max_digits=12, decimal_places=3,
                                         null=True, blank=True)
    carga_kwh = models.DecimalField("contador de consumo da carga (kWh)", max_digits=12, decimal_places=3,
                                    null=True, blank=True)
    tensao_v = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    corrente_a = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    fator_potencia = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["momento"]
        constraints = [models.UniqueConstraint(fields=["medidor", "momento"], name="medicao_unica")]
        indexes = [models.Index(fields=["medidor", "momento"])]
        verbose_name = "medição bruta"
        verbose_name_plural = "medições brutas"

    def __str__(self):
        return f"{self.medidor} {self.momento:%d/%m %H:%M}"


class LeituraMedidor(models.Model):
    """Fonte 2 da auditoria: energia por dia medida pelo equipamento próprio."""

    medidor = models.ForeignKey("cadastro.Medidor", on_delete=models.CASCADE, related_name="leituras")
    data = models.DateField()
    importacao_kwh = models.DecimalField("consumido da rede (kWh)", max_digits=10, decimal_places=2,
                                         null=True, blank=True)
    exportacao_kwh = models.DecimalField("injetado na rede (kWh)", max_digits=10, decimal_places=2,
                                         null=True, blank=True)
    carga_kwh = models.DecimalField("consumo total da instalação (kWh)", max_digits=10, decimal_places=2,
                                    null=True, blank=True)
    demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["data"]
        verbose_name = "leitura diária do medidor"
        verbose_name_plural = "leituras diárias do medidor"
        constraints = [models.UniqueConstraint(fields=["medidor", "data"], name="leitura_unica_por_dia")]

    def __str__(self):
        return f"{self.medidor} {self.data}"
