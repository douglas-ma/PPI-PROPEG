from django.core.management.base import BaseCommand

from projetos_institucionais.ethics_notifications import processar_alertas_etica


class Command(BaseCommand):
    help = 'Envia os alertas de 60, 30, 15, 7, 3 e 1 dia para aprovação ética.'

    def handle(self, *args, **options):
        total = processar_alertas_etica()
        self.stdout.write(self.style.SUCCESS(f'{total} alerta(s) de ética enviado(s).'))
