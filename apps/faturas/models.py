"""Fonte 3 da auditoria: o que a concessionária mediu e cobrou.

Nesta etapa a fatura é lançada à mão (ou gerada nos dados de demonstração). O leitor de PDF
(pdfplumber + IA) preenche estes mesmos campos na fase seguinte.
"""

from decimal import Decimal

from django.db import models

from apps.core.models import TenantModel


class Fatura(TenantModel):
    class Origem(models.TextChoices):
        MANUAL = "manual", "Lançada à mão"
        PDF = "pdf", "Lida do PDF"
        IA = "ia", "Lida com IA"
        DEMO = "demo", "Demonstração"

    class Status(models.TextChoices):
        RECEBIDA = "recebida", "Recebida"
        REVISAO = "revisao", "Em revisão"
        CONFERIDA = "conferida", "Confere"
        DIVERGENTE = "divergente", "Divergência"

    class Bandeira(models.TextChoices):
        VERDE = "verde", "Verde"
        AMARELA = "amarela", "Amarela"
        VERMELHA1 = "vermelha1", "Vermelha patamar 1"
        VERMELHA2 = "vermelha2", "Vermelha patamar 2"
        ESCASSEZ = "escassez", "Escassez hídrica"

    uc = models.ForeignKey("cadastro.UnidadeConsumidora", on_delete=models.CASCADE, related_name="faturas")
    mes_referencia = models.DateField("mês de referência", help_text="Primeiro dia do mês.")
    data_leitura_anterior = models.DateField("leitura anterior")
    data_leitura_atual = models.DateField("leitura atual")
    vencimento = models.DateField(null=True, blank=True)
    leitura_anterior = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    leitura_atual = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    constante_medidor = models.DecimalField(max_digits=8, decimal_places=3, default=Decimal(1))
    consumo_kwh = models.DecimalField("consumo faturado (kWh)", max_digits=10, decimal_places=2)
    consumo_ponta_kwh = models.DecimalField("consumo na ponta (kWh)", max_digits=10, decimal_places=2,
                                            null=True, blank=True)
    energia_injetada_kwh = models.DecimalField("energia injetada (kWh)", max_digits=10, decimal_places=2,
                                               default=Decimal(0))
    energia_compensada_kwh = models.DecimalField("energia compensada (kWh)", max_digits=10, decimal_places=2,
                                                 default=Decimal(0))
    saldo_creditos_kwh = models.DecimalField("saldo de créditos (kWh)", max_digits=12, decimal_places=2,
                                             null=True, blank=True)
    modalidade_gd = models.CharField("modalidade GD na fatura", max_length=3, blank=True)
    bandeira = models.CharField(max_length=10, choices=Bandeira.choices, blank=True)
    custo_disponibilidade_kwh = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    valor_fio_b = models.DecimalField("Fio B cobrado (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    valor_icms = models.DecimalField("ICMS (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    valor_pis_cofins = models.DecimalField("PIS/COFINS (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    valor_cip = models.DecimalField("CIP (R$)", max_digits=10, decimal_places=2, null=True, blank=True)
    demanda_contratada_kw = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    demanda_medida_kw = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    valor_ultrapassagem = models.DecimalField("ultrapassagem de demanda (R$)", max_digits=10, decimal_places=2,
                                              null=True, blank=True)
    valor_reativo = models.DecimalField("energia reativa (R$)", max_digits=10, decimal_places=2, null=True,
                                        blank=True)
    valor_total = models.DecimalField("total a pagar (R$)", max_digits=12, decimal_places=2)
    origem = models.CharField(max_length=8, choices=Origem.choices, default=Origem.MANUAL)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RECEBIDA)
    pdf = models.FileField(upload_to="faturas/%Y/%m/", blank=True)
    observacoes = models.TextField(blank=True)

    class Meta:
        ordering = ["-mes_referencia"]
        constraints = [models.UniqueConstraint(fields=["uc", "mes_referencia"], name="fatura_unica_por_mes")]

    def __str__(self):
        return f"{self.uc} {self.mes_referencia:%m/%Y}"

    @property
    def dias(self):
        return (self.data_leitura_atual - self.data_leitura_anterior).days

    @property
    def consumo_pela_leitura(self):
        if self.leitura_anterior is None or self.leitura_atual is None:
            return None
        return ((self.leitura_atual - self.leitura_anterior) * self.constante_medidor).quantize(Decimal("0.01"))

    @property
    def leitura_confere(self):
        c = self.consumo_pela_leitura
        return None if c is None else abs(c - self.consumo_kwh) <= Decimal("1")
