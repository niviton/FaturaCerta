"""Cadastro completo: tudo o que a auditoria da conta precisa saber sobre o cliente,
as unidades consumidoras, as usinas e os equipamentos."""

import datetime
import hashlib
import secrets
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.fields import EncryptedJSONField
from apps.core.models import TenantModel
from apps.core.validators import so_digitos, validar_cpf_cnpj

# Lei 14.300/2022, art. 26: GD1 para pedido de acesso protocolado até 07/01/2023.
# Confirmar fonte; na fase de regras vira tabela regulatória com vigência.
DATA_CORTE_GD1 = datetime.date(2023, 1, 7)

# REN 1.000/2021: custo de disponibilidade por tipo de ligação (grupo B).
CUSTO_DISPONIBILIDADE_KWH = {"mono": 30, "bi": 50, "tri": 100}

VALIDADE_CREDITO_MESES = 60


def somar_meses(d: datetime.date, meses: int) -> datetime.date:
    total = d.month - 1 + meses
    ano, mes = d.year + total // 12, total % 12 + 1
    bissexto = ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)
    dias_no_mes = [31, 29 if bissexto else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mes - 1]
    return datetime.date(ano, mes, min(d.day, dias_no_mes))


class Endereco(models.Model):
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField("número", max_length=20, blank=True)
    complemento = models.CharField(max_length=80, blank=True)
    bairro = models.CharField(max_length=80, blank=True)
    municipio = models.CharField("município", max_length=80, blank=True)
    uf = models.CharField(max_length=2, blank=True)
    cep = models.CharField("CEP", max_length=9, blank=True)

    class Meta:
        abstract = True

    @property
    def endereco_curto(self):
        partes = [f"{self.logradouro} {self.numero}".strip(), self.bairro,
                  f"{self.municipio}/{self.uf}" if self.municipio else ""]
        return ", ".join(p for p in partes if p)


class Concessionaria(models.Model):
    """Catálogo global (não é por integradora)."""

    nome = models.CharField(max_length=120)
    sigla = models.SlugField(max_length=30, unique=True, help_text="Ex.: cosern")
    uf = models.CharField(max_length=2)
    layout_fatura = models.CharField(
        max_length=40, blank=True, help_text="Código do leitor de PDF no catálogo de leitores."
    )
    tarifa_referencia_kwh = models.DecimalField(
        "tarifa de referência (R$/kWh, com tributos)", max_digits=6, decimal_places=4, null=True, blank=True,
        help_text="Só para ESTIMAR economia nas telas. Os cálculos de auditoria usam as tabelas regulatórias. "
                  "Confirmar fonte.",
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "concessionária"

    def __str__(self):
        return f"{self.nome} ({self.uf})"


class Cliente(TenantModel, Endereco):
    """Titular das UCs: cliente final da integradora."""

    class TipoPessoa(models.TextChoices):
        PF = "pf", "Pessoa física"
        PJ = "pj", "Pessoa jurídica"

    class Segmento(models.TextChoices):
        RESIDENCIAL = "residencial", "Residencial"
        COMERCIAL = "comercial", "Comércio e serviços"
        INDUSTRIAL = "industrial", "Indústria"
        RURAL = "rural", "Rural / agronegócio"
        PUBLICO = "publico", "Poder público"
        CONDOMINIO = "condominio", "Condomínio"

    tipo_pessoa = models.CharField("tipo", max_length=2, choices=TipoPessoa.choices, default=TipoPessoa.PJ)
    nome = models.CharField("nome ou razão social", max_length=200)
    nome_fantasia = models.CharField(max_length=120, blank=True)
    documento = models.CharField("CPF/CNPJ", max_length=18, validators=[validar_cpf_cnpj])
    segmento = models.CharField(max_length=12, choices=Segmento.choices, default=Segmento.COMERCIAL)
    atividade = models.CharField("atividade / ramo", max_length=120, blank=True,
                                 help_text="Ex.: panificação, clínica, oficina. Ajuda a explicar o perfil de consumo.")
    contato_nome = models.CharField("pessoa de contato", max_length=120, blank=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    horario_funcionamento = models.CharField(
        max_length=80, blank=True, help_text="Ex.: seg a sáb, 5h às 20h. Usado para interpretar o consumo diurno."
    )
    data_inicio_contrato = models.DateField("cliente desde", null=True, blank=True)
    observacoes = models.TextField("observações", blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["integradora", "documento"], name="cliente_doc_por_integradora"),
        ]

    def __str__(self):
        return self.nome_fantasia or self.nome

    def save(self, *args, **kwargs):
        self.documento = so_digitos(self.documento)
        super().save(*args, **kwargs)

    @property
    def documento_formatado(self):
        d = self.documento
        if len(d) == 11:
            return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
        if len(d) == 14:
            return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
        return d

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


class UnidadeConsumidora(TenantModel, Endereco):
    class Grupo(models.TextChoices):
        A = "A", "Grupo A (média/alta tensão)"
        B = "B", "Grupo B (baixa tensão)"

    class Subgrupo(models.TextChoices):
        B1 = "B1", "B1 residencial"
        B2 = "B2", "B2 rural"
        B3 = "B3", "B3 demais classes"
        B4 = "B4", "B4 iluminação pública"
        A1 = "A1", "A1 (≥ 230 kV)"
        A2 = "A2", "A2 (88 a 138 kV)"
        A3 = "A3", "A3 (69 kV)"
        A3A = "A3a", "A3a (30 a 44 kV)"
        A4 = "A4", "A4 (2,3 a 25 kV)"
        AS = "AS", "AS (subterrâneo)"

    class Classe(models.TextChoices):
        RESIDENCIAL = "residencial", "Residencial"
        COMERCIAL = "comercial", "Comercial, serviços e outras"
        INDUSTRIAL = "industrial", "Industrial"
        RURAL = "rural", "Rural"
        PODER_PUBLICO = "poder_publico", "Poder público"
        SERVICO_PUBLICO = "servico_publico", "Serviço público"
        ILUMINACAO = "iluminacao", "Iluminação pública"

    class Ligacao(models.TextChoices):
        MONO = "mono", "Monofásica"
        BI = "bi", "Bifásica"
        TRI = "tri", "Trifásica"

    class Modalidade(models.TextChoices):
        CONVENCIONAL = "convencional", "Convencional"
        BRANCA = "branca", "Branca"
        VERDE = "verde", "Verde (horária)"
        AZUL = "azul", "Azul (horária)"

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name="ucs")
    concessionaria = models.ForeignKey(Concessionaria, on_delete=models.PROTECT)
    numero_uc = models.CharField("número da UC (instalação)", max_length=30)
    codigo_cliente = models.CharField(
        "código do cliente", max_length=30, blank=True, help_text="Como vem impresso na fatura."
    )
    apelido = models.CharField(max_length=80, blank=True, help_text="Ex.: loja centro, casa de praia.")
    # perfil tarifário
    grupo = models.CharField(max_length=1, choices=Grupo.choices, default=Grupo.B)
    subgrupo = models.CharField(max_length=3, choices=Subgrupo.choices, blank=True)
    classe = models.CharField(max_length=16, choices=Classe.choices, blank=True)
    tipo_ligacao = models.CharField("tipo de ligação", max_length=4, choices=Ligacao.choices, blank=True)
    tensao_fornecimento_v = models.PositiveIntegerField("tensão de fornecimento (V)", null=True, blank=True,
                                                        help_text="Ex.: 220, 380, 13800.")
    modalidade_tarifaria = models.CharField(
        max_length=12, choices=Modalidade.choices, default=Modalidade.CONVENCIONAL
    )
    tarifa_social = models.BooleanField("tarifa social", default=False)
    demanda_contratada_kw = models.DecimalField(
        "demanda contratada (kW)", max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Grupo A. Na modalidade azul é a demanda fora de ponta.",
    )
    demanda_contratada_ponta_kw = models.DecimalField(
        "demanda contratada na ponta (kW)", max_digits=9, decimal_places=2, null=True, blank=True,
        help_text="Só na modalidade azul.",
    )
    # medição da concessionária
    numero_medidor_concessionaria = models.CharField("número do medidor da concessionária", max_length=30, blank=True)
    constante_medidor = models.DecimalField("constante do medidor", max_digits=8, decimal_places=3, null=True,
                                            blank=True, help_text="Fator de multiplicação impresso na fatura.")
    medidor_bidirecional = models.BooleanField("medidor bidirecional instalado", default=False)
    data_ligacao = models.DateField("data de ligação da UC", null=True, blank=True)
    consumo_medio_kwh = models.DecimalField(
        "consumo médio antes da usina (kWh/mês)", max_digits=10, decimal_places=1, null=True, blank=True,
        help_text="Linha de base informada pelo cliente ou tirada do histórico.",
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
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

    @property
    def perfil_tarifario(self):
        partes = [self.subgrupo or f"Grupo {self.grupo}"]
        if self.tipo_ligacao:
            partes.append(self.get_tipo_ligacao_display())
        partes.append(self.get_modalidade_tarifaria_display())
        return " · ".join(partes)


class Usina(TenantModel, Endereco):
    class Enquadramento(models.TextChoices):
        GD1 = "GD1", "GD1 (protocolo até 07/01/2023)"
        GD2 = "GD2", "GD2 (protocolo após 07/01/2023)"
        GD3 = "GD3", "GD3 (> 500 kW, fonte não despachável)"

    class Tipo(models.TextChoices):
        JUNTO_CARGA = "junto_carga", "Junto à carga"
        AUTOCONSUMO_REMOTO = "autoconsumo_remoto", "Autoconsumo remoto"
        COMPARTILHADA = "compartilhada", "Geração compartilhada"
        MULTIPLAS_UCS = "multiplas_ucs", "Múltiplas UCs (condomínio)"

    class Instalacao(models.TextChoices):
        TELHADO_CERAMICO = "ceramico", "Telhado cerâmico"
        TELHADO_METALICO = "metalico", "Telhado metálico"
        FIBROCIMENTO = "fibrocimento", "Fibrocimento"
        LAJE = "laje", "Laje"
        SOLO = "solo", "Solo"
        CARPORT = "carport", "Carport / estacionamento"

    nome = models.CharField(max_length=120)
    uc_geradora = models.ForeignKey(UnidadeConsumidora, on_delete=models.PROTECT, related_name="usinas")
    tipo = models.CharField("modalidade de GD", max_length=20, choices=Tipo.choices, default=Tipo.JUNTO_CARGA)
    # acesso / regulatório
    data_protocolo = models.DateField("protocolo do pedido de acesso", null=True, blank=True)
    numero_protocolo = models.CharField("número do protocolo / parecer", max_length=40, blank=True)
    data_parecer_acesso = models.DateField("data do parecer de acesso", null=True, blank=True)
    data_conexao = models.DateField("data de conexão (troca do medidor)", null=True, blank=True)
    enquadramento = models.CharField(max_length=3, choices=Enquadramento.choices, blank=True)
    enquadramento_manual = models.BooleanField(
        default=False, help_text="Marque para não recalcular o enquadramento pela data do protocolo."
    )
    # técnico
    potencia_kwp = models.DecimalField("potência instalada (kWp)", max_digits=9, decimal_places=2,
                                       null=True, blank=True, help_text="Calculada pelos arranjos, se houver.")
    potencia_inversor_kw = models.DecimalField("potência total de inversores (kW)", max_digits=9, decimal_places=2,
                                               null=True, blank=True)
    numero_modulos = models.PositiveIntegerField("número de módulos", null=True, blank=True)
    tipo_instalacao = models.CharField("tipo de instalação", max_length=14, choices=Instalacao.choices, blank=True)
    inclinacao_graus = models.DecimalField("inclinação (°)", max_digits=4, decimal_places=1, null=True, blank=True)
    azimute_graus = models.DecimalField("azimute (°, 0 = norte)", max_digits=5, decimal_places=1, null=True,
                                        blank=True)
    performance_ratio = models.DecimalField("performance ratio esperado", max_digits=4, decimal_places=2,
                                            default=Decimal("0.78"),
                                            validators=[MinValueValidator(Decimal("0.3")), MaxValueValidator(1)])
    geracao_esperada_kwh = models.JSONField(
        "geração esperada por mês (kWh)", default=list, blank=True, help_text="12 valores, de janeiro a dezembro."
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    valor_investido = models.DecimalField("valor investido (R$)", max_digits=12, decimal_places=2, null=True,
                                          blank=True)
    observacoes = models.TextField("observações", blank=True)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if not self.enquadramento_manual and self.data_protocolo:
            self.enquadramento = self.enquadramento_pela_data(self.data_protocolo)
        super().save(*args, **kwargs)

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

    def recalcular_potencia(self):
        arranjos = list(self.arranjos.all())
        if arranjos:
            self.potencia_kwp = sum((a.potencia_kwp for a in arranjos), Decimal(0))
            self.numero_modulos = sum(a.quantidade for a in arranjos)
        inversores = [i.potencia_nominal_kw for i in self.inversores.all() if i.potencia_nominal_kw]
        if inversores:
            self.potencia_inversor_kw = sum(inversores, Decimal(0))
        self.save(update_fields=["potencia_kwp", "numero_modulos", "potencia_inversor_kw"])

    @property
    def enquadramento_divergente_da_data(self):
        esperado = self.enquadramento_pela_data(self.data_protocolo)
        return bool(esperado and self.enquadramento in ("GD1", "GD2") and self.enquadramento != esperado)

    @property
    def cliente(self):
        return self.uc_geradora.cliente

    @property
    def relacao_dc_ac(self):
        if self.potencia_kwp and self.potencia_inversor_kw:
            return (self.potencia_kwp / self.potencia_inversor_kw).quantize(Decimal("0.01"))
        return None

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


class ArranjoModulos(models.Model):
    """Conjunto de módulos iguais com a mesma orientação."""

    usina = models.ForeignKey(Usina, on_delete=models.CASCADE, related_name="arranjos")
    fabricante = models.CharField(max_length=60)
    modelo = models.CharField(max_length=80, blank=True)
    potencia_wp = models.PositiveIntegerField("potência do módulo (Wp)")
    quantidade = models.PositiveIntegerField()
    inclinacao_graus = models.DecimalField("inclinação (°)", max_digits=4, decimal_places=1, null=True, blank=True)
    azimute_graus = models.DecimalField("azimute (°)", max_digits=5, decimal_places=1, null=True, blank=True)
    garantia_anos = models.PositiveSmallIntegerField("garantia de desempenho (anos)", null=True, blank=True)

    class Meta:
        verbose_name = "arranjo de módulos"
        verbose_name_plural = "arranjos de módulos"

    def __str__(self):
        return f"{self.quantidade} × {self.fabricante} {self.modelo} {self.potencia_wp} Wp"

    @property
    def potencia_kwp(self):
        return (Decimal(self.potencia_wp) * self.quantidade / 1000).quantize(Decimal("0.01"))


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
    ("esp", "ESP32 / dispositivo próprio (envia para a nossa API)"),
    ("http", "API HTTP do fabricante"),
    ("mqtt", "MQTT"),
]


class Inversor(models.Model):
    class Tipo(models.TextChoices):
        STRING = "string", "String (on-grid)"
        MICRO = "micro", "Microinversor"
        HIBRIDO = "hibrido", "Híbrido (com bateria)"
        CENTRAL = "central", "Central"

    class Fases(models.TextChoices):
        MONO = "mono", "Monofásico"
        TRI = "tri", "Trifásico"

    usina = models.ForeignKey(Usina, on_delete=models.CASCADE, related_name="inversores")
    marca = models.CharField(max_length=60)
    modelo = models.CharField(max_length=80, blank=True)
    numero_serie = models.CharField("número de série", max_length=60, blank=True)
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.STRING)
    potencia_nominal_kw = models.DecimalField("potência nominal (kW)", max_digits=8, decimal_places=2, null=True,
                                              blank=True)
    fases = models.CharField(max_length=4, choices=Fases.choices, blank=True)
    numero_mppt = models.PositiveSmallIntegerField("número de MPPTs", null=True, blank=True)
    data_instalacao = models.DateField("data de instalação", null=True, blank=True)
    garantia_ate = models.DateField("garantia até", null=True, blank=True)
    provedor_api = models.CharField("API de monitoramento", max_length=20, choices=PROVEDORES_INVERSOR,
                                    default="fake")
    id_externo = models.CharField(
        "ID no portal do fabricante", max_length=80, blank=True, help_text="Ex.: plant id / site id / stationCode."
    )
    credenciais = EncryptedJSONField(blank=True, default=dict)

    class Meta:
        verbose_name_plural = "inversores"

    def __str__(self):
        return f"{self.marca} {self.modelo}".strip()

    @property
    def credenciais_configuradas(self):
        return self.provedor_api != "fake" and bool(self.credenciais) and bool(self.id_externo) and not set(
            self.credenciais) <= {"cenario", "fator", "desde"}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Medidor(models.Model):
    """Medição própria (ESP32 com sensores de corrente, medidor inteligente, gateway).

    Fica na UC: mede o que entra e sai da rede (bidirecional) e/ou o consumo total da carga.
    É a segunda fonte da auditoria, ao lado do inversor e da fatura.
    """

    class Tipo(models.TextChoices):
        ESP32 = "esp32", "ESP32 + sensores de corrente (CT)"
        SMART = "smart", "Medidor inteligente"
        GATEWAY = "gateway", "Gateway / datalogger"

    class Ponto(models.TextChoices):
        REDE = "rede", "Entrada da rede (bidirecional: consumo e injeção)"
        CARGA = "carga", "Carga (consumo total da instalação)"
        REDE_E_CARGA = "rede_carga", "Rede e carga (dois conjuntos de sensores)"

    uc = models.ForeignKey(UnidadeConsumidora, on_delete=models.CASCADE, related_name="medidores")
    usina = models.ForeignKey(Usina, on_delete=models.SET_NULL, null=True, blank=True, related_name="medidores",
                              help_text="Opcional: usina associada a esta medição.")
    nome = models.CharField(max_length=80, default="Medidor próprio")
    tipo = models.CharField(max_length=8, choices=Tipo.choices, default=Tipo.ESP32)
    ponto_medicao = models.CharField("ponto de medição", max_length=10, choices=Ponto.choices, default=Ponto.REDE)
    fabricante = models.CharField(max_length=60, blank=True)
    modelo = models.CharField(max_length=80, blank=True)
    numero_serie = models.CharField("número de série / ID do dispositivo", max_length=60, blank=True)
    fases = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(3)])
    corrente_ct_a = models.PositiveIntegerField("faixa dos sensores (A)", null=True, blank=True)
    intervalo_envio_s = models.PositiveIntegerField("intervalo de envio (s)", default=60)
    data_instalacao = models.DateField("data de instalação", null=True, blank=True)
    provedor_api = models.CharField("origem dos dados", max_length=20, choices=PROVEDORES_MEDIDOR, default="fake")
    id_externo = models.CharField(max_length=80, blank=True)
    credenciais = EncryptedJSONField(blank=True, default=dict)
    token_hash = models.CharField(max_length=64, blank=True, editable=False)
    token_prefixo = models.CharField(max_length=8, blank=True, editable=False)
    ultimo_contato = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name_plural = "medidores"

    def __str__(self):
        return f"{self.nome} ({self.get_tipo_display()})"

    def gerar_token(self) -> str:
        """Gera o token do dispositivo. O valor só é mostrado uma vez; guardamos o hash."""
        token = "fc_" + secrets.token_urlsafe(24)
        self.token_hash, self.token_prefixo = _hash_token(token), token[:8]
        self.save(update_fields=["token_hash", "token_prefixo"])
        return token

    @classmethod
    def pelo_token(cls, token: str):
        if not token:
            return None
        return cls.objects.filter(token_hash=_hash_token(token)).select_related("uc").first()

    @property
    def online(self):
        from django.utils import timezone

        return bool(self.ultimo_contato and timezone.now() - self.ultimo_contato < datetime.timedelta(
            seconds=max(self.intervalo_envio_s * 5, 900)))


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
