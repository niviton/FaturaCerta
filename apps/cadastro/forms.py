import json
from decimal import Decimal

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.models import Integradora

from .models import Cliente, Inversor, LoteCredito, Medidor, Rateio, UnidadeConsumidora, Usina

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


class TenantModelForm(forms.ModelForm):
    """Recebe a integradora e restringe as escolhas de FK aos dados dela."""

    tenant_fields: dict[str, str] = {}

    def __init__(self, *args, integradora=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.integradora = integradora
        for nome in self.tenant_fields:
            if nome in self.fields:
                self.fields[nome].queryset = self.fields[nome].queryset.filter(integradora=integradora)


class IntegradoraForm(forms.ModelForm):
    class Meta:
        model = Integradora
        fields = ["razao_social", "nome_fantasia", "cnpj", "responsavel_tecnico_nome", "responsavel_tecnico_crea",
                  "logo", "cor_marca", "email_contato", "telefone_contato"]
        widgets = {"cor_marca": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, integradora=None, **kwargs):
        super().__init__(*args, **kwargs)


class ClienteForm(TenantModelForm):
    class Meta:
        model = Cliente
        fields = ["nome", "documento", "contato_nome", "email", "telefone", "whatsapp", "ativo"]

    def clean_documento(self):
        from apps.core.validators import so_digitos

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
    tenant_fields = {"cliente": "integradora"}

    class Meta:
        model = UnidadeConsumidora
        fields = ["cliente", "concessionaria", "numero_uc", "codigo_cliente", "apelido",
                  "logradouro", "numero", "bairro", "municipio", "uf", "cep",
                  "grupo", "subgrupo", "tipo_ligacao", "modalidade_tarifaria",
                  "demanda_contratada_kw", "demanda_contratada_ponta_kw", "email_fatura", "ativa"]

    def clean(self):
        data = super().clean()
        self.instance.integradora = self.integradora
        return data


class UsinaForm(TenantModelForm):
    tenant_fields = {"uc_geradora": "integradora"}

    class Meta:
        model = Usina
        fields = ["nome", "uc_geradora", "tipo", "data_protocolo", "enquadramento", "enquadramento_manual",
                  "potencia_kwp", "potencia_inversor_kw", "data_conexao", "numero_modulos", "ativa"]
        widgets = {
            "data_protocolo": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "data_conexao": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["enquadramento"].help_text = (
            "Preenchido pela data do protocolo (GD1 até 07/01/2023). Marque 'manual' para fixar outro valor."
        )
        atuais = self.instance.geracao_esperada_kwh or []
        for i, mes in enumerate(MESES):
            self.fields[f"esp_{mes}"] = forms.DecimalField(
                label=mes, required=False, min_value=0, decimal_places=1,
                initial=atuais[i] if len(atuais) == 12 else None,
            )

    def campos_esperada(self):
        return [self[f"esp_{m}"] for m in MESES]

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


class CredenciaisMixin(forms.ModelForm):
    """Credenciais nunca voltam para a tela; campo vazio na edição mantém o valor salvo."""

    credenciais_json = forms.CharField(
        label="Credenciais da API (JSON)", required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text='Ex.: {"usuario": "...", "token": "..."}. Guardadas criptografadas. '
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
    class Meta:
        model = Inversor
        fields = ["marca", "modelo", "numero_serie", "provedor_api", "id_externo"]


class MedidorForm(CredenciaisMixin):
    class Meta:
        model = Medidor
        fields = ["fabricante", "modelo", "numero_serie", "provedor_api", "id_externo"]


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
