from django.db import models


class ClimaDiario(models.Model):
    """Irradiação solar real por dia, numa região de 0,1° × 0,1° (~11 km)."""

    lat = models.DecimalField(max_digits=5, decimal_places=1)
    lon = models.DecimalField(max_digits=5, decimal_places=1)
    data = models.DateField()
    irradiacao_kwh_m2 = models.DecimalField("irradiação (kWh/m²·dia)", max_digits=6, decimal_places=3)
    fonte = models.CharField(max_length=20, default="open-meteo")

    class Meta:
        ordering = ["data"]
        verbose_name = "clima diário"
        verbose_name_plural = "clima diário"
        constraints = [models.UniqueConstraint(fields=["lat", "lon", "data"], name="clima_diario_unico")]

    def __str__(self):
        return f"({self.lat}, {self.lon}) {self.data}: {self.irradiacao_kwh_m2} kWh/m²"


class ClimaHorario(models.Model):
    """Irradiância média da hora que TERMINA em `momento` (convenção do Open-Meteo)."""

    lat = models.DecimalField(max_digits=5, decimal_places=1)
    lon = models.DecimalField(max_digits=5, decimal_places=1)
    momento = models.DateTimeField()
    irradiancia_w_m2 = models.DecimalField("irradiância (W/m²)", max_digits=7, decimal_places=1)

    class Meta:
        ordering = ["momento"]
        verbose_name = "clima horário"
        verbose_name_plural = "clima horário"
        constraints = [models.UniqueConstraint(fields=["lat", "lon", "momento"], name="clima_horario_unico")]

    def __str__(self):
        return f"({self.lat}, {self.lon}) {self.momento:%d/%m %H:%M}: {self.irradiancia_w_m2} W/m²"
