"""Manuais em PDF por perfil.

Os textos ficam em Markdown (docs/). O comando `python manage.py gerar_manuais` gera os PDFs em
docs/manuais/, que são versionados e servidos pelo sistema a quem tem acesso.
"""

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class Manual:
    codigo: str
    titulo: str
    publico: str
    descricao: str
    fonte: str  # caminho do Markdown, relativo a BASE_DIR

    @property
    def arquivo(self):
        return settings.BASE_DIR / "docs" / "manuais" / f"FaturaCerta-manual-{self.codigo}.pdf"

    @property
    def caminho_fonte(self):
        return settings.BASE_DIR / self.fonte


MANUAIS = {
    "administrador": Manual(
        "administrador", "Manual do administrador geral", "Administrador geral",
        "O manual completo: uso de todos os perfis, instalação, configuração, integrações com inversores e ESP32, "
        "API de medições, regras de monitoramento e análise, segurança e solução de problemas.",
        "docs/MANUAL.md"),
    "integradora": Manual(
        "integradora", "Manual da integradora", "Gestores e técnicos da integradora",
        "Uso do dia a dia: monitoramento, cadastro completo do cliente, conexão dos inversores e do medidor ESP32, "
        "faturas, análise da conta, equipe e o que o cliente vê no portal.",
        "docs/manuais/manual_integradora.md"),
}


def manuais_do_usuario(user):
    """Administrador geral acessa todos; a equipe da integradora, só o da integradora."""
    if user.is_admin_geral:
        return [MANUAIS["administrador"], MANUAIS["integradora"]]
    if user.is_equipe:
        return [MANUAIS["integradora"]]
    return []
