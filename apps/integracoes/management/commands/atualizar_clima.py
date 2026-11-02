"""Busca o clima real (Open-Meteo) das regiões com usinas e grava no banco.

Uso: python manage.py atualizar_clima [--dias 400] [--regerar]

--regerar recalcula a geração fictícia dos inversores sem credencial com o clima novo.
"""

from django.core.management.base import BaseCommand

from apps.integracoes import clima


class Command(BaseCommand):
    help = "Atualiza o clima real usado na demonstração."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=3)
        parser.add_argument("--regerar", action="store_true",
                            help="Recalcula a geração de demonstração com o clima atualizado.")

    def handle(self, *args, dias, regerar, **opts):
        if not clima.ativo():
            self.stdout.write("CLIMA_PROVIDER está desligado. Nada a fazer.")
            return
        for (lat, lon), r in clima.atualizar_todas(dias).items():
            if isinstance(r, str):
                self.stdout.write(self.style.WARNING(f"({lat}, {lon}): {r}"))
            else:
                self.stdout.write(f"({lat}, {lon}): {r[0]} dias e {r[1]} horas")
        if regerar:
            from apps.monitoramento import tasks

            tasks.coletar_geracao_todos(dias=dias)
            tasks.coletar_curvas_hoje()
            tasks.coletar_status_todos()
            self.stdout.write("Geração de demonstração recalculada.")
        self.stdout.write(self.style.SUCCESS("Clima atualizado."))
