"""Dados de cadastro que cada regra de auditoria/alerta precisa.

Mostra na tela da UC quais regras estão ativas e quais estão desligadas por falta de dado.
As regras em si ficam no motor de auditoria (fase 5); aqui só a dependência de cadastro.
"""

from dataclasses import dataclass, field

from django.apps import apps


@dataclass
class StatusRegra:
    codigo: str
    nome: str
    ativa: bool
    faltando: list[str] = field(default_factory=list)
    nao_se_aplica: bool = False


def _usinas_da_uc(uc):
    """Usinas em que a UC é geradora ou beneficiária."""
    Usina = apps.get_model("cadastro", "Usina")
    return list(
        Usina.objects.filter(integradora=uc.integradora)
        .filter(models_q_uc(uc))
        .distinct()
        .prefetch_related("inversores")
    )


def models_q_uc(uc):
    from django.db.models import Q

    return Q(uc_geradora=uc) | Q(rateios__uc=uc)


def _qtd_faturas(uc):
    try:
        Fatura = apps.get_model("faturas", "Fatura")
    except LookupError:  # app de faturas entra na fase 3
        return 0
    return Fatura.objects.filter(uc=uc).count()


def status_regras(uc) -> list[StatusRegra]:
    usinas = _usinas_da_uc(uc)
    geradoras = [u for u in usinas if u.uc_geradora_id == uc.id]
    tem_inversor = any(u.inversores.all() for u in geradoras)
    tem_medidor = uc.medidores.exists()
    grupo_a = uc.grupo == "A"
    out = []

    def add(codigo, nome, faltando, nao_se_aplica=False):
        out.append(StatusRegra(codigo, nome, not faltando and not nao_se_aplica, faltando, nao_se_aplica))

    falta_vinculo = [] if usinas else ["vínculo com uma usina (geradora ou beneficiária)"]
    add("injecao_nao_compensada", "Injeção não compensada", falta_vinculo)
    add("injecao_vs_geracao", "Injeção × geração do inversor",
        ([] if geradoras else ["ser UC geradora de uma usina"]) + ([] if tem_inversor else ["inversor cadastrado"]))
    add("constante_medidor", "Constante do medidor (fatura × medidor próprio)",
        [] if tem_medidor else ["medidor próprio (ESP)"])

    falta_prot = [] if any(u.data_protocolo for u in usinas) else ["data do protocolo do pedido de acesso"]
    add("enquadramento_gd", "Enquadramento GD1 × GD2", falta_vinculo + falta_prot)
    gd2 = any(u.enquadramento == "GD2" for u in usinas)
    add("fio_b_gd2", "Fio B (GD2)", falta_vinculo + falta_prot, nao_se_aplica=bool(usinas) and not gd2 and not falta_prot)

    add("salto_consumo", "Salto anormal de consumo",
        [] if _qtd_faturas(uc) >= 12 else ["histórico de 12 faturas"])
    add("custo_disponibilidade", "Custo de disponibilidade",
        [] if uc.tipo_ligacao else ["tipo de ligação"], nao_se_aplica=grupo_a)
    add("cip", "CIP do município", [] if uc.municipio else ["município"])
    add("leitura", "Leitura × constante = consumo", [] if uc.constante_medidor else ["constante do medidor"])
    add("demanda", "Ultrapassagem de demanda",
        [] if uc.demanda_contratada_kw else ["demanda contratada"], nao_se_aplica=not grupo_a)
    add("reativo", "Cobrança de reativo", [], nao_se_aplica=not grupo_a)
    falta_esp = [] if any(len(u.geracao_esperada_kwh) == 12 for u in geradoras) else ["geração esperada (12 meses)"]
    add("geracao_abaixo", "Geração abaixo do esperado",
        ([] if tem_inversor else ["inversor cadastrado"]) + falta_esp, nao_se_aplica=not geradoras)
    add("fatura_nao_recebida", "Fatura não recebida",
        [] if uc.email_fatura or uc.codigo_cliente else ["e-mail de recebimento ou código do cliente"])
    return out


def pendencias_cadastro_uc(uc) -> list[str]:
    """Campos que faltam para ao menos uma regra aplicável."""
    vistos = []
    for r in status_regras(uc):
        if not r.nao_se_aplica:
            for f in r.faltando:
                if f not in vistos:
                    vistos.append(f)
    return vistos
