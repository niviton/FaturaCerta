import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.fields import EncryptedJSONField
from apps.core.models import TenantModel
from apps.core.validators import so_digitos, validar_cpf_cnpj

# Lei 14.300/2022, art. 26: GD1 para pedido de acesso protocolado até 07/01/2023
# (12 meses após a publicação). Confirmar fonte; na fase 5 vira tabela regulatória.
DATA_CORTE_GD1 = datetime.date(2023, 1, 7)

# REN 1.000/2021: custo de disponibilidade por tipo de ligação (grupo B).
CUSTO_DISPONIBILIDADE_KWH = {"mono": 30, "bi": 50, "tri": 100}

VALIDADE_CREDITO_MESES = 60


def somar_meses(d: datetime.date, meses: int) -> datetime.date:
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    dias_no_mes = [31, 29 if ano % 4 == 0 and (ano % 100 or ano % 400 == 0) else 28, 31, 30, 31, 30,
                   31, 31, 30, 31, 30, 31][mes - 1]
    return datetime.date(ano, mes, min(d.day, dias_no_mes))


class Concessionaria(models.Model):
    """Catálogo global (não é por integradora)."""

    nome = models.CharField(max_length=120)
    sigla = models.SlugField(max_length=30, unique=True, help_text="Ex.: cosern")
    uf = models.CharField(max_length=2)
    layout_fatura = models.CharField(
        max_length=40, blank=True, help_text="Código do parser de PDF no catálogo de leitores."
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "concessionária"

    def __str__(self):
        return f"{self.nome} ({self.uf})"


class Cliente(TenantModel):
    """Titular das UCs: cliente final da integradora."""

    nome = models.CharField("nome ou razão social", max_length=200)
    documento = models.CharField("CPF/CNPJ", max_length=18, validators=[validar_cpf_cnpj])
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    contato_nome = models.CharField("pessoa de contato", max_length=120, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["integradora", "documento"], name="cliente_doc_por_integradora"),
        ]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        self.documento = so_digitos(self.documento)
        super().save(*args, **kwargs)

    @property
    def consentimento_vigente(self):
        return self.consentimentos.filter(revogado_em__isnull=True).order_by("-data").first()


class ConsentimentoLGPD(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="consentimentos")
    data = models.DateTimeField()
    versao_termo = models.CharField(max_length=20)
    ip = models.GenericIPAddressField(null=True, blank=True)
    registrado_por = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    revogado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-data"]
        verbose_name = "consentimento LGPD"

    def __str__(self):
        return f"{self.cliente} v{self.versao_termo} em {self.data:%d/%m/%Y}"


class UnidadeConsumidora(TenantModel):
    class Grupo(models.TextChoices):
        A = "A", "Grupo A (alta tensão)"
        B = "B", "Grupo B (baixa tensão)"

    class Subgrupo(models.TextChoices):
        B1 = "B1", "B1 residencial"
        B2 = "B2", "B2 rural"
        B3 = "B3", "B3 demais classes"
        B4 = "B4", "B4 iluminação pública"
        A1 = "A1", "A1"
        A2 = "A2", "A2"
        A3 = "A3", "A3"
        A3A = "A3a", "A3a"
        A4 = "A4", "A4"
        AS = "AS", "AS"

    class Ligacao(models.TextChoices):
        MONO = "mono", "Monofásica"
        BI = "bi", "Bifásica"
        TRI = "tri", "Trifásica"

    class Modalidade(models.TextChoices):
        CONVENCIONAL = "convencional", "Convencional"
        BRANCA = "branca", "Branca"
        VERDE = "verde", "Verde"
        AZUL = "azul", "Azul"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="ucs")
    concessionaria = models.ForeignKey(Concessionaria, on_delete=models.PROTECT)
    numero_uc = models.CharField("número da UC", max_length=30)
    codigo_cliente = models.CharField(
        "código do cliente", max_length=30, blank=True, help_text="Como vem impresso na fatura."
    )
    apelido = models.CharField(max_length=80, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=80, blank=True)
    municipio = models.CharField("município", max_length=80, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField(max_length=9, blank=True)
    grupo = models.CharField(max_length=1, choices=Grupo.choices, default=Grupo.B)
    subgrupo = models.CharField(max_length=3, choices=Subgrupo.choices, blank=True)
    tipo_ligacao = models.CharField("tipo de ligação", max_length=4, choices=Ligacao.choices, blank=True)
    modalidade_tarifaria = models.CharField(
        max_length=12, choices=Modalidade.choices, default=Modalidade.CONVENCIONAL
    )
    demanda_contratada_kw = models.DecimalField(
        "demanda contratada (kW)", max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Grupo A. Na modalidade azul é a demanda fora de ponta.",
    )
    demanda_contratada_ponta_kw = models.DecimalField(
        "demanda contratada na ponta (kW)", max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Só na modalidade azul.",
    )
    email_fatura = models.EmailField(
        "e-mail de recebimento da fatura", blank=True, help_text="Ex.: faturas+uc7010453067@suaempresa.com.br"
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["cliente__nome", "numero_uc"]
        verbose_name = "unidade consumidora"
        verbose_name_plural = "unidades consumidoras"
        constraints = [
            models.UniqueConstraint(
                fields=["integradora", "concessionaria", "numero_uc"], name="uc_unica_por_integradora"
            ),
        ]

    def __str__(self):
        return f"UC {self.numero_uc}" + (f" · {self.apelido}" if self.apelido else "")

    def clean(self):
        erros = {}
        if self.grupo == self.Grupo.A:
            if self.subgrupo and not self.subgrupo.startswith("A"):
                erros["subgrupo"] = "Subgrupo incompatível com o grupo A."
            if self.modalidade_tarifaria == self.Modalidade.BRANCA:
                erros["modalidade_tarifaria"] = "Tarifa branca é só para o grupo B."
        else:
            if self.modalidade_tarifaria in (self.Modalidade.VERDE, self.Modalidade.AZUL):
                erros["modalidade_tarifaria"] = "Modalidades verde e azul são só para o grupo A."
            if self.subgrupo and not self.subgrupo.startswith("B"):
                erros["subgrupo"] = "Subgrupo incompatível com o grupo B."
        if self.cliente_id and self.integradora_id and self.cliente.integradora_id != self.integradora_id:
            erros["cliente"] = "Cliente de outra integradora."
        if erros:
            raise ValidationError(erros)

    @property
    def custo_disponibilidade_kwh(self):
        return CUSTO_DISPONIBILIDADE_KWH.get(self.tipo_ligacao)


class Usina(TenantModel):
    class Enquadramento(models.TextChoices):
        GD1 = "GD1", "GD1"
        GD2 = "GD2", "GD2"
        GD3 = "GD3", "GD3"

    class Tipo(models.TextChoices):
        JUNTO_CARGA = "junto_carga", "Junto à carga"
        AUTOCONSUMO_REMOTO = "autoconsumo_remoto", "Autoconsumo remoto"
        COMPARTILHADA = "compartilhada", "Geração compartilhada"
        MULTIPLAS_UCS = "multiplas_ucs", "Múltiplas UCs (condomínio)"

    nome = models.CharField(max_length=120)
    uc_geradora = models.ForeignKey(UnidadeConsumidora, on_delete=models.PROTECT, related_name="usinas")
    data_protocolo = models.DateField("data do protocolo do pedido de acesso", null=True, blank=True)
    enquadramento = models.CharField(max_length=3, choices=Enquadramento.choices, blank=True)
    enquadramento_manual = models.BooleanField(
        default=False, help_text="Marque para não recalcular o enquadramento pela data do protocolo."
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.JUNTO_CARGA)
    potencia_kwp = models.DecimalField("potência instalada (kWp)", max_digits=9, decimal_places=2,
                                       null=True, blank=True)
    potencia_inversor_kw = models.DecimalField("potência do inversor (kW)", max_digits=9, decimal_places=2,
                                               null=True, blank=True)
    data_conexao = models.DateField("data de conexão", null=True, blank=True)
    numero_modulos = models.PositiveIntegerField("número de módulos", null=True, blank=True)
    geracao_esperada_kwh = models.JSONField(
        "geração esperada por mês (kWh)", default=list, blank=True, help_text="12 valores, de janeiro a dezembro."
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    @staticmethod
    def enquadramento_pela_data(data_protocolo):
        if not data_protocolo:
            return ""
        return "GD1" if data_protocolo <= DATA_CORTE_GD1 else "GD2"

    def clean(self):
        g = self.geracao_esperada_kwh
        if g and (len(g) != 12 or any(float(v) < 0 for v in g)):
            raise ValidationError({"geracao_esperada_kwh": "Informe 12 valores não negativos."})
        if self.uc_geradora_id and self.integradora_id and self.uc_geradora.integradora_id != self.integradora_id:
            raise ValidationError({"uc_geradora": "UC de outra integradora."})

    def save(self, *args, **kwargs):
        if not self.enquadramento_manual and self.data_protocolo:
            self.enquadramento = self.enquadramento_pela_data(self.data_protocolo)
        super().save(*args, **kwargs)

    @property
    def enquadramento_divergente_da_data(self):
        esperado = self.enquadramento_pela_data(self.data_protocolo)
        return bool(esperado and self.enquadramento in ("GD1", "GD2") and self.enquadramento != esperado)

    @property
    def cliente(self):
        return self.uc_geradora.cliente

    def geracao_esperada_mes(self, mes: int):
        g = self.geracao_esperada_kwh
        return Decimal(str(g[mes - 1])) if len(g) == 12 else None


class Rateio(models.Model):
    """UC beneficiária e percentual dos créditos. A soma por usina deve ser 100%."""

    usina = models.ForeignKey(Usina, on_delete=models.CASCADE, related_name="rateios")
    uc = models.ForeignKey(UnidadeConsumidora, on_delete=models.CASCADE, related_name="rateios_recebidos")
    percentual = models.DecimalField(
        max_digits=5, decimal_places=2, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        constraints = [models.UniqueConstraint(fields=["usina", "uc"], name="rateio_uc_unica")]

    def __str__(self):
        return f"{self.uc} {self.percentual}%"


PROVEDORES_INVERSOR = [
    ("fake", "Demonstração (fictício)"),
    ("growatt", "Growatt"),
    ("huawei", "Huawei FusionSolar"),
    ("solaredge", "SolarEdge"),
    ("fronius", "Fronius"),
    ("goodwe", "GoodWe"),
    ("deye", "Deye / Solarman"),
]

PROVEDORES_MEDIDOR = [
    ("fake", "Demonstração (fictício)"),
    ("http", "API HTTP do fabricante"),
    ("mqtt", "MQTT"),
]


class Inversor(models.Model):
    usina = models.ForeignKey(Usina, on_delete=models.CASCADE, related_name="inversores")
    marca = models.CharField(max_length=60)
    modelo = models.CharField(max_length=80, blank=True)
    numero_serie = models.CharField("número de série", max_length=60, blank=True)
    provedor_api = models.CharField(max_length=20, choices=PROVEDORES_INVERSOR, default="fake")
    id_externo = models.CharField(
        "ID no portal do fabricante", max_length=80, blank=True, help_text="Ex.: plant id / site id."
    )
    credenciais = EncryptedJSONField(blank=True, default=dict)

    class Meta:
        verbose_name_plural = "inversores"

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.numero_serie})".strip()


class Medidor(models.Model):
    usina = models.OneToOneField(Usina, on_delete=models.CASCADE, related_name="medidor")
    fabricante = models.CharField(max_length=60)
    modelo = models.CharField(max_length=80, blank=True)
    numero_serie = models.CharField("número de série", max_length=60, blank=True)
    provedor_api = models.CharField(max_length=20, choices=PROVEDORES_MEDIDOR, default="fake")
    id_externo = models.CharField(max_length=80, blank=True)
    credenciais = EncryptedJSONField(blank=True, default=dict)

    class Meta:
        verbose_name_plural = "medidores"

    def __str__(self):
        return f"{self.fabricante} {self.modelo}".strip()


class LoteCredito(models.Model):
    """Saldo de créditos em kWh por mês de geração. Validade de 60 meses."""

    uc = models.ForeignKey(UnidadeConsumidora, on_delete=models.CASCADE, related_name="lotes_credito")
    mes_referencia = models.DateField(help_text="Primeiro dia do mês em que o crédito foi gerado.")
    kwh_gerado = models.DecimalField(max_digits=12, decimal_places=2)
    kwh_saldo = models.DecimalField(max_digits=12, decimal_places=2)
    posto = models.CharField(max_length=12, blank=True, help_text="Grupo A: ponta / fora_ponta.")
    origem = models.CharField(max_length=20, default="manual")

    class Meta:
        ordering = ["uc", "mes_referencia"]
        verbose_name = "lote de crédito"

    def __str__(self):
        return f"{self.uc} {self.mes_referencia:%m/%Y}: {self.kwh_saldo} kWh"

    @property
    def validade(self):
        return somar_meses(self.mes_referencia, VALIDADE_CREDITO_MESES)
