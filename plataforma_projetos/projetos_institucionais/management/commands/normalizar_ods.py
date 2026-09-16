from django.core.management.base import BaseCommand
from django.db import transaction

from projetos_institucionais.ods_catalogo import normalizar_ods_padrao


class Command(BaseCommand):
    help = 'Reutiliza o catálogo existente de ODS e remove duplicatas equivalentes.'

    @transaction.atomic
    def handle(self, *args, **options):
        ods, removidas = normalizar_ods_padrao()
        self.stdout.write(self.style.SUCCESS(
            f'Catálogo de ODS normalizado: {len(ods)} registros principais; '
            f'{removidas} duplicata(s) removida(s).'
        ))
