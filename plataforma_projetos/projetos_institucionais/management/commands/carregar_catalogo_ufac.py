from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projetos_institucionais.catalogo_ufac import CURSOS_UFAC, criar_catalogo_ufac
from projetos_institucionais.models import CentroLotacao, CursoGraduacao, ProgramaPos, Projeto, Usuario


class Command(BaseCommand):
    help = 'Carrega os centros acadêmicos e cursos presenciais oficiais da UFAC.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--substituir',
            action='store_true',
            help='Remove o catálogo atual antes de recriá-lo. Exige que não haja vínculos.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        limpar = options['substituir']
        if limpar and (
            Usuario.objects.filter(centro_lotacao__isnull=False).exists()
            or Usuario.objects.filter(curso__isnull=False).exists()
            or Projeto.objects.filter(centro_lotacao__isnull=False).exists()
            or Projeto.objects.filter(curso__isnull=False).exists()
            or ProgramaPos.objects.exists()
        ):
            raise CommandError(
                'O catálogo possui vínculos. Execute sem --substituir ou remova os vínculos primeiro.'
            )

        centros = criar_catalogo_ufac(CentroLotacao, CursoGraduacao, limpar=limpar)
        self.stdout.write(self.style.SUCCESS(
            f'Catálogo UFAC carregado: {len(centros)} centros e {len(CURSOS_UFAC)} cursos.'
        ))
