from django import forms

from apps.cadastro.forms import TenantModelForm
from apps.core.forms import DATA

from .models import Fatura


class FaturaForm(TenantModelForm):
    tenant_fields = ("uc",)
    secoes = [
        ("Fatura", "", ["uc", "mes_referencia", "vencimento", "valor_total", "status", "pdf"]),
        ("Leitura", "Janela de leitura: o sistema soma a geração do inversor exatamente entre estas datas.",
         ["data_leitura_anterior", "data_leitura_atual", "leitura_anterior", "leitura_atual", "constante_medidor"]),
        ("Energia", "", ["consumo_kwh", "consumo_ponta_kwh", "energia_injetada_kwh", "energia_compensada_kwh",
                         "saldo_creditos_kwh", "modalidade_gd", "custo_disponibilidade_kwh", "bandeira"]),
        ("Valores", "", ["valor_fio_b", "valor_icms", "valor_pis_cofins", "valor_cip"]),
        ("Grupo A", "Só para unidades de média tensão.", ["demanda_contratada_kw", "demanda_medida_kw",
                                                           "valor_ultrapassagem", "valor_reativo"]),
        ("Observações", "", ["observacoes"]),
    ]

    class Meta:
        model = Fatura
        exclude = ["integradora", "origem"]
        widgets = {"mes_referencia": forms.DateInput(attrs={"type": "month"}), "vencimento": DATA,
                   "data_leitura_anterior": DATA, "data_leitura_atual": DATA,
                   "observacoes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mes_referencia"].input_formats = ["%Y-%m", "%Y-%m-%d"]
        self.fields["uc"].label_from_instance = lambda uc: f"{uc} · {uc.cliente}"

    def clean_mes_referencia(self):
        return self.cleaned_data["mes_referencia"].replace(day=1)

    def clean(self):
        data = super().clean()
        a, b = data.get("data_leitura_anterior"), data.get("data_leitura_atual")
        if a and b and b <= a:
            self.add_error("data_leitura_atual", "A leitura atual deve ser depois da anterior.")
        return data
