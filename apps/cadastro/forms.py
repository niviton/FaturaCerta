import json
from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.forms import DATA, SecoesMixin
from apps.core.models import Integradora
from apps.core.validators import so_digitos

from .models import (
    ArranjoModulos,
    Cliente,
    Inversor,
    LoteCredito,
    Medidor,
    Rateio,
    UnidadeConsumidora,
    Usina,
)

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


class TenantModelForm(SecoesMixin, forms.ModelForm):
    """Recebe a integradora e restringe as escolhas de FK aos dados dela."""

    tenant_fields: tuple[str, ...] = ()

    def __init__(self, *args, integradora=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.integradora = integradora
        for nome in self.tenant_fields:
            if nome in self.fields:
                self.fields[nome].queryset = self.fields[nome].queryset.filter(integradora=integradora)


class IntegradoraForm(SecoesMixin, forms.ModelForm):
    secoes = [
        ("Empresa", "", ["razao_social", "nome_fantasia", "cnpj", "inscricao_estadual"]),
        ("Responsável técnico", "Aparece no laudo de contestação.", ["responsavel_tecnico_nome",
                                                                     "responsavel_tecnico_crea"]),
        ("Contato e endereço", "", ["email_contato", "telefone_contato", "whatsapp", "site", "logradouro",
                                    "municipio", "uf"]),
        ("Marca no portal do cliente", "Logo e cor usados no portal que o seu cliente acessa.", ["logo", "cor_marca"]),
    ]

    class Meta:
        model = Integradora
        fields = ["razao_social", "nome_fantasia", "cnpj", "inscricao_estadual", "responsavel_tecnico_nome",
                  "responsavel_tecnico_crea", "email_contato", "telefone_contato", "whatsapp", "site", "logradouro",
                  "municipio", "uf", "logo", "cor_marca"]
        widgets = {"cor_marca": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, integradora=None, **kwargs):
        super().__init__(*args, **kwargs)


class IntegradoraAdminForm(IntegradoraForm):
    """Versão do administrador geral: inclui plano, cobrança e situação."""

    secoes = IntegradoraForm.secoes + [
        ("Contrato", "Visível só para o administrador geral.", ["plano", "valor_por_usina", "taxa_exito_pct",
                                                                "ativa", "observacoes"]),
    ]

    class Meta(IntegradoraForm.Meta):
        fields = IntegradoraForm.Meta.fields + ["plano", "valor_por_usina", "taxa_exito_pct", "ativa", "observacoes"]


class ClienteForm(TenantModelForm):
    secoes = [
        ("Titular", "Quem é o titular das contas de energia.", ["tipo_pessoa", "nome", "nome_fantasia", "documento",
                                                                "segmento", "atividade"]),
        ("Contato", "", ["contato_nome", "email", "telefone", "whatsapp"]),
        ("Endereço", "", ["cep", "logradouro", "numero", "complemento", "bairro", "municipio", "uf"]),
        ("Perfil de uso", "Ajuda a interpretar o consumo e o autoconsumo na auditoria.",
         ["horario_funcionamento", "data_inicio_contrato", "observacoes", "ativo"]),
    ]

    class Meta:
        model = Cliente
        fields = ["tipo_pessoa", "nome", "nome_fantasia", "documento", "segmento", "atividade", "contato_nome", "email",
                  "telefone", "whatsapp", "cep", "logradouro", "numero", "complemento", "bairro", "municipio", "uf",
                  "horario_funcionamento", "data_inicio_contrato", "observacoes", "ativo"]
        widgets = {"data_inicio_contrato": DATA, "observacoes": forms.Textarea(attrs={"rows": 3})}

    def clean_documento(self):
        doc = so_digitos(self.cleaned_data["documento"])
        qs = Cliente.objects.filter(integradora=self.integradora, documento=doc).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cliente com este CPF/CNPJ.")
        return doc


class ConsentimentoForm(forms.Form):
    versao_termo = forms.CharField(label="Versão do termo", max_length=20, initial="1.0")
    aceito = forms.BooleanField(
        label="O titular aceitou o termo para recebermos e processarmos as faturas dele", required=True
    )


class UCForm(TenantModelForm):
    tenant_fields = ("cliente",)
    secoes = [
        ("Identificação", "Os números como aparecem na fatura. É por eles que a fatura chega no cliente certo.",
         ["cliente", "concessionaria", "numero_uc", "codigo_cliente", "apelido", "email_fatura"]),
        ("Perfil tarifário", "Define quais regras valem: grupo A ou B, custo de disponibilidade, demanda.",
         ["grupo", "subgrupo", "classe", "tipo_ligacao", "tensao_fornecimento_v", "modalidade_tarifaria",
          "tarifa_social", "demanda_contratada_kw", "demanda_contratada_ponta_kw"]),
        ("Medidor da concessionária", "Para conferir leitura × constante = consumo.",
         ["numero_medidor_concessionaria", "constante_medidor", "medidor_bidirecional", "data_ligacao"]),
        ("Linha de base", "Consumo antes da usina. Base para medir a economia.", ["consumo_medio_kwh"]),
        ("Endereço da UC", "O município define a CIP.", ["cep", "logradouro", "numero", "complemento", "bairro",
                                                          "municipio", "uf", "latitude", "longitude"]),
    ]

    class Meta:
        model = UnidadeConsumidora
        fields = ["cliente", "concessionaria", "numero_uc", "codigo_cliente", "apelido", "email_fatura", "grupo",
                  "subgrupo", "classe", "tipo_ligacao", "tensao_fornecimento_v", "modalidade_tarifaria",
                  "tarifa_social", "demanda_contratada_kw", "demanda_contratada_ponta_kw",
                  "numero_medidor_concessionaria", "constante_medidor", "medidor_bidirecional", "data_ligacao",
                  "consumo_medio_kwh", "cep", "logradouro", "numero", "complemento", "bairro", "municipio", "uf",
                  "latitude", "longitude", "ativa"]
        widgets = {"data_ligacao": DATA}

    def clean(self):
        data = super().clean()
        self.instance.integradora = self.integradora
        return data


class UsinaForm(TenantModelForm):
    tenant_fields = ("uc_geradora",)
    secoes = [
        ("Identificação", "", ["nome", "uc_geradora", "tipo"]),
        ("Acesso e enquadramento", "A data do protocolo define GD1 ou GD2 (Lei 14.300). É a base do cálculo do Fio B.",
         ["data_protocolo", "numero_protocolo", "data_parecer_acesso", "data_conexao", "enquadramento",
          "enquadramento_manual"]),
        ("Dados técnicos", "Se você cadastrar os arranjos de módulos, a potência é calculada sozinha.",
         ["potencia_kwp", "potencia_inversor_kw", "numero_modulos", "tipo_instalacao", "inclinacao_graus",
          "azimute_graus", "performance_ratio"]),
        ("Local e investimento", "", ["cep", "logradouro", "numero", "bairro", "municipio", "uf", "latitude",
                                      "longitude", "valor_investido", "observacoes", "ativa"]),
    ]

    class Meta:
        model = Usina
        fields = ["nome", "uc_geradora", "tipo", "data_protocolo", "numero_protocolo", "data_parecer_acesso",
                  "data_conexao", "enquadramento", "enquadramento_manual", "potencia_kwp", "potencia_inversor_kw",
                  "numero_modulos", "tipo_instalacao", "inclinacao_graus", "azimute_graus", "performance_ratio",
                  "cep", "logradouro", "numero", "bairro", "municipio", "uf", "latitude", "longitude",
                  "valor_investido", "observacoes", "ativa"]
        widgets = {"data_protocolo": DATA, "data_parecer_acesso": DATA, "data_conexao": DATA,
                   "observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cliente is not None:
            self.fields["uc_geradora"].queryset = self.fields["uc_geradora"].queryset.filter(cliente=cliente)
        self.fields["uc_geradora"].label_from_instance = lambda uc: f"{uc} · {uc.cliente}"
        atuais = self.instance.geracao_esperada_kwh or []
        for i, mes in enumerate(MESES):
            self.fields[f"esp_{mes}"] = forms.DecimalField(
                label=mes, required=False, min_value=0, decimal_places=1,
                initial=atuais[i] if len(atuais) == 12 else None,
            )

    def campos_esperada(self):
        return [self[f"esp_{m}"] for m in MESES]

    def secoes_renderizadas(self):
        return [s for s in super().secoes_renderizadas() if not s["campos"][0].name.startswith("esp_")]

    def clean(self):
        data = super().clean()
        valores = [data.get(f"esp_{m}") for m in MESES]
        preenchidos = [v for v in valores if v is not None]
        if preenchidos and len(preenchidos) != 12:
            raise forms.ValidationError("Preencha a geração esperada dos 12 meses ou deixe todos vazios.")
        self.instance.geracao_esperada_kwh = [float(v) for v in valores] if preenchidos else []
        self.instance.integradora = self.integradora
        return data


class RateioBaseFormSet(BaseInlineFormSet):
    def __init__(self, *args, integradora=None, **kwargs):
        self.integradora = integradora
        super().__init__(*args, **kwargs)
        for f in self.forms:
            f.fields["uc"].queryset = UnidadeConsumidora.objects.filter(integradora=integradora)

    @property
    def empty_form(self):
        form = super().empty_form
        form.fields["uc"].queryset = UnidadeConsumidora.objects.filter(integradora=self.integradora)
        return form

    def clean(self):
        super().clean()
        total, ucs = Decimal(0), set()
        for f in self.forms:
            if not hasattr(f, "cleaned_data") or not f.cleaned_data or f.cleaned_data.get("DELETE"):
                continue
            uc = f.cleaned_data.get("uc")
            if uc in ucs:
                raise forms.ValidationError("A mesma UC aparece duas vezes no rateio.")
            ucs.add(uc)
            total += f.cleaned_data.get("percentual") or 0
        if ucs and total != 100:
            raise forms.ValidationError(f"A soma do rateio deve ser 100%. Hoje está em {total}%.")


RateioFormSet = inlineformset_factory(
    Usina, Rateio, formset=RateioBaseFormSet, fields=["uc", "percentual"], extra=1, can_delete=True
)


class ArranjoForm(SecoesMixin, forms.ModelForm):
    class Meta:
        model = ArranjoModulos
        fields = ["fabricante", "modelo", "potencia_wp", "quantidade", "inclinacao_graus", "azimute_graus",
                  "garantia_anos"]


class CredenciaisMixin(SecoesMixin, forms.ModelForm):
    """Credenciais nunca voltam para a tela; campo vazio na edição mantém o valor salvo."""

    credenciais_json = forms.CharField(
        label="Credenciais da API (JSON)", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text='Ex.: {"token": "..."}. Guardadas criptografadas e nunca exibidas de novo. '
                  "Deixe vazio para manter as atuais.",
    )

    def clean_credenciais_json(self):
        bruto = self.cleaned_data["credenciais_json"].strip()
        if not bruto:
            return None
        try:
            valor = json.loads(bruto)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("JSON inválido.") from exc
        if not isinstance(valor, dict):
            raise forms.ValidationError("Use um objeto JSON, ex.: {\"token\": \"...\"}.")
        return valor

    def save(self, commit=True):
        novo = self.cleaned_data.get("credenciais_json")
        if novo is not None:
            self.instance.credenciais = novo
        return super().save(commit)


class InversorForm(CredenciaisMixin):
    secoes = [
        ("Equipamento", "", ["marca", "modelo", "numero_serie", "tipo", "potencia_nominal_kw", "fases", "numero_mppt",
                             "data_instalacao", "garantia_ate"]),
        ("Conexão com a API do fabricante", "Fonte 1 da auditoria: quanto a usina gerou. Sem credenciais, o sistema "
         "mostra dados de demonstração.", ["provedor_api", "id_externo", "credenciais_json"]),
    ]

    class Meta:
        model = Inversor
        fields = ["marca", "modelo", "numero_serie", "tipo", "potencia_nominal_kw", "fases", "numero_mppt",
                  "data_instalacao", "garantia_ate", "provedor_api", "id_externo"]
        widgets = {"data_instalacao": DATA, "garantia_ate": DATA}


class MedidorForm(CredenciaisMixin):
    secoes = [
        ("Dispositivo", "Fonte 2 da auditoria: o que entra e sai da rede, medido por nós.",
         ["nome", "tipo", "ponto_medicao", "fabricante", "modelo", "numero_serie", "fases", "corrente_ct_a",
          "intervalo_envio_s", "data_instalacao", "usina"]),
        ("Origem dos dados", "ESP32: o dispositivo envia para a nossa API com um token. "
         "HTTP/MQTT: buscamos no serviço do fabricante.", ["provedor_api", "id_externo", "credenciais_json"]),
    ]

    class Meta:
        model = Medidor
        fields = ["nome", "tipo", "ponto_medicao", "fabricante", "modelo", "numero_serie", "fases", "corrente_ct_a",
                  "intervalo_envio_s", "data_instalacao", "usina", "provedor_api", "id_externo"]
        widgets = {"data_instalacao": DATA}

    def __init__(self, *args, uc=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usina"].queryset = Usina.objects.filter(uc_geradora=uc) if uc else Usina.objects.none()


class LoteCreditoForm(forms.ModelForm):
    class Meta:
        model = LoteCredito
        fields = ["mes_referencia", "kwh_gerado", "kwh_saldo", "posto"]
        widgets = {"mes_referencia": forms.DateInput(attrs={"type": "month"})}

    def clean_mes_referencia(self):
        return self.cleaned_data["mes_referencia"].replace(day=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes_referencia"].input_formats = ["%Y-%m", "%Y-%m-%d"]
