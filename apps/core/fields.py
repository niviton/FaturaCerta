"""Campo de texto criptografado com Fernet (credenciais de API, tokens OAuth)."""

import base64
import hashlib
import json

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        # Desenvolvimento: deriva da SECRET_KEY. Em produção, FIELD_ENCRYPTION_KEY é obrigatória.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Não foi possível descriptografar o campo (chave trocada?)") from exc


class EncryptedTextField(models.TextField):
    """Guarda texto cifrado no banco; em Python o valor é texto puro."""

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        return decrypt(value)

    def get_prep_value(self, value):
        if value in (None, ""):
            return value
        return encrypt(str(value))


class EncryptedJSONField(EncryptedTextField):
    """Dicionário serializado em JSON e cifrado."""

    def from_db_value(self, value, expression, connection):
        plain = super().from_db_value(value, expression, connection)
        return json.loads(plain) if plain else {}

    def to_python(self, value):
        if isinstance(value, dict):
            return value
        return json.loads(value) if value else {}

    def get_prep_value(self, value):
        if not value:
            return ""
        return super().get_prep_value(json.dumps(value))

    def value_to_string(self, obj):
        return json.dumps(self.value_from_object(obj))
