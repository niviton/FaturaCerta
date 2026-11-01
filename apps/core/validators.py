import re

from django.core.exceptions import ValidationError


def so_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _dv(digitos: str, pesos: list[int]) -> int:
    resto = sum(int(d) * p for d, p in zip(digitos, pesos, strict=False)) % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(valor: str) -> bool:
    d = so_digitos(valor)
    if len(d) != 14 or d == d[0] * 14:
        return False
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return _dv(d[:12], p1) == int(d[12]) and _dv(d[:13], p2) == int(d[13])


def cpf_valido(valor: str) -> bool:
    d = so_digitos(valor)
    if len(d) != 11 or d == d[0] * 11:
        return False
    v1 = sum(int(d[i]) * (10 - i) for i in range(9)) * 10 % 11 % 10
    v2 = sum(int(d[i]) * (11 - i) for i in range(10)) * 10 % 11 % 10
    return v1 == int(d[9]) and v2 == int(d[10])


def validar_cnpj(valor):
    if not cnpj_valido(valor):
        raise ValidationError("CNPJ inválido.")


def validar_cpf_cnpj(valor):
    if not (cpf_valido(valor) or cnpj_valido(valor)):
        raise ValidationError("CPF ou CNPJ inválido.")
