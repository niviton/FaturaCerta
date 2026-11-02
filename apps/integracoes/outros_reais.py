"""Conectores reais de medidor próprio e de notificação."""

import datetime
import json
import logging
import uuid

from django.conf import settings
from django.core.mail import send_mail

from .base import (
    IntegracaoNaoConfigurada,
    LeituraMedidorDia,
    Mensagem,
    Notificador,
    ProvedorMedidor,
)
from .inversores_reais import d, http_json

log = logging.getLogger(__name__)


class MedidorHTTP(ProvedorMedidor):
    """API HTTP genérica do fabricante do medidor.

    Credenciais: {"url_base": "https://...", "token": "..."}. Espera
    GET {url_base}/medidores/{id_externo}/diario?inicio=AAAA-MM-DD&fim=AAAA-MM-DD
    devolvendo {"itens": [{"data": "...", "importacao_kwh": n, "exportacao_kwh": n, "carga_kwh": n}]}.
    Ajuste o mapeamento por fabricante.
    """

    codigo = "http"

    def __init__(self, medidor):
        super().__init__(medidor)
        if not self.credenciais.get("url_base") or not medidor.id_externo:
            raise IntegracaoNaoConfigurada("Medidor HTTP: faltam url_base e id_externo")

    def leituras_diarias(self, inicio, fim):
        r = http_json("GET", f"{self.credenciais['url_base'].rstrip('/')}/medidores/{self.medidor.id_externo}/diario",
                      params={"inicio": inicio.isoformat(), "fim": fim.isoformat()},
                      headers={"Authorization": f"Bearer {self.credenciais.get('token', '')}"})
        def opc(v):
            return None if v is None else d(v)

        return [LeituraMedidorDia(datetime.date.fromisoformat(i["data"]), opc(i.get("importacao_kwh")),
                                  opc(i.get("exportacao_kwh")), opc(i.get("carga_kwh")))
                for i in r.get("itens", [])]


def _leituras_gravadas(medidor, inicio, fim):
    from apps.monitoramento.models import LeituraMedidor

    qs = LeituraMedidor.objects.filter(medidor=medidor, data__range=(inicio, fim)).order_by("data")
    return [LeituraMedidorDia(x.data, x.importacao_kwh, x.exportacao_kwh, x.carga_kwh) for x in qs]


class MedidorESP(ProvedorMedidor):
    """ESP32 (ou outro dispositivo) que envia medições para POST /api/medidores/medicoes.

    Não buscamos nada: o dispositivo empurra os contadores, e a tarefa `consolidar_medicoes`
    transforma as medições brutas em leituras diárias. Aqui só devolvemos o que foi consolidado.
    """

    codigo = "esp"

    def __init__(self, medidor):
        super().__init__(medidor)
        if not medidor.token_hash:
            raise IntegracaoNaoConfigurada("ESP: gere o token do dispositivo")

    def leituras_diarias(self, inicio, fim):
        return _leituras_gravadas(self.medidor, inicio, fim)


class MedidorMQTT(ProvedorMedidor):
    """Medidor que publica por MQTT.

    A leitura em tempo real é feita por um assinante separado (worker) que grava as leituras no banco;
    aqui só lemos o que já foi gravado. Credenciais: {"host": "...", "porta": 8883, "usuario": "...",
    "senha": "...", "topico": "medidores/<serie>/energia"}. O assinante entra quando houver medidor real.
    """

    codigo = "mqtt"

    def __init__(self, medidor):
        super().__init__(medidor)
        if not self.credenciais.get("host"):
            raise IntegracaoNaoConfigurada("Medidor MQTT: falta host")

    def leituras_diarias(self, inicio, fim):
        return _leituras_gravadas(self.medidor, inicio, fim)


class EmailDjango(Notificador):
    """E-mail pelo backend SMTP configurado no Django (EMAIL_HOST etc.)."""

    canal = "email"

    def enviar(self, mensagem: Mensagem) -> str:
        send_mail(mensagem.assunto, mensagem.texto, settings.DEFAULT_FROM_EMAIL, [mensagem.destino])
        return f"email-{uuid.uuid4().hex[:12]}"


class WhatsAppCloud(Notificador):
    """WhatsApp Business Cloud API (Meta). Requer WHATSAPP_TOKEN e WHATSAPP_PHONE_ID.

    Fora da janela de 24 h a Meta exige template aprovado; aqui enviamos o template
    WHATSAPP_TEMPLATE com o texto como parâmetro. CONFIRMAR nome do template aprovado.
    """

    canal = "whatsapp"

    def __init__(self):
        self.token = getattr(settings, "WHATSAPP_TOKEN", "")
        self.phone_id = getattr(settings, "WHATSAPP_PHONE_ID", "")
        self.template = getattr(settings, "WHATSAPP_TEMPLATE", "alerta_usina")
        if not (self.token and self.phone_id):
            raise IntegracaoNaoConfigurada("WhatsApp: faltam WHATSAPP_TOKEN e WHATSAPP_PHONE_ID")

    def enviar(self, mensagem: Mensagem) -> str:
        corpo = {
            "messaging_product": "whatsapp", "to": mensagem.destino, "type": "template",
            "template": {"name": self.template, "language": {"code": "pt_BR"},
                         "components": [{"type": "body", "parameters": [{"type": "text", "text": mensagem.texto}]}]},
        }
        r = http_json("POST", f"https://graph.facebook.com/v21.0/{self.phone_id}/messages", corpo=corpo,
                      headers={"Authorization": f"Bearer {self.token}"})
        log.info("WhatsApp enviado: %s", json.dumps(r.get("messages", []))[:200])
        return (r.get("messages") or [{}])[0].get("id", "")
