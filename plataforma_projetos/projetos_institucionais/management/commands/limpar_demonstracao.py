from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projetos_institucionais.management.commands.povoar_demonstracao import (
    TITULOS_PROJETOS_DEMO,
    USUARIOS_DEMO,
)
from projetos_institucionais.models import Edital, Projeto, Usuario


class Command(BaseCommand):
    help = (
        'Remove somente os usuários, projetos e editais identificados como '
        'dados de demonstração, preservando os demais registros.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma a exclusão dos dados temporários de demonstração.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options['confirmar']:
            raise CommandError(
                'Operação não confirmada. Execute novamente com --confirmar.'
            )

        cpfs_demo = [dados[0] for dados in USUARIOS_DEMO]
        projetos = Projeto.objects.filter(
            titulo__in=TITULOS_PROJETOS_DEMO,
            coordenador__cpf__in=cpfs_demo,
        )
        quantidade_projetos = projetos.count()
        projetos.delete()

        editais = Edital.objects.filter(tipo='DEMO')
        quantidade_editais = editais.count()
        editais.delete()

        usuarios = Usuario.objects.filter(
            cpf__in=cpfs_demo,
            is_superuser=False,
        )
        quantidade_usuarios = usuarios.count()
        usuarios.delete()

        self.stdout.write(self.style.SUCCESS(
            'Dados de demonstração removidos: '
            f'{quantidade_usuarios} usuários, {quantidade_projetos} projetos e '
            f'{quantidade_editais} editais.'
        ))
