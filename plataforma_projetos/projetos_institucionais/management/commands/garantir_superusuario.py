import os

from django.core.management.base import BaseCommand, CommandError

from projetos_institucionais.models import Usuario


class Command(BaseCommand):
    help = 'Cria o administrador inicial de produção de forma idempotente.'

    def handle(self, *args, **options):
        cpf = ''.join(filter(str.isdigit, os.environ.get('ADMIN_CPF', '')))
        email = os.environ.get('ADMIN_EMAIL', '').strip()
        senha = os.environ.get('ADMIN_PASSWORD', '')

        ausentes = [
            nome
            for nome, valor in (
                ('ADMIN_CPF', cpf),
                ('ADMIN_EMAIL', email),
                ('ADMIN_PASSWORD', senha),
            )
            if not valor
        ]
        if ausentes:
            raise CommandError(
                'Defina as variáveis obrigatórias: ' + ', '.join(ausentes)
            )

        usuario = Usuario.objects.filter(cpf=cpf).first()
        if usuario is None:
            Usuario.objects.create_superuser(
                cpf=cpf,
                username=cpf,
                email=email,
                password=senha,
                first_name=os.environ.get('ADMIN_FIRST_NAME', 'Administrador'),
                last_name=os.environ.get('ADMIN_LAST_NAME', 'PROPEG'),
                perfil='gestor',
                status='ativo',
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS('Superusuário inicial criado.'))
            return

        campos_alterados = []
        valores = {
            'email': email,
            'is_active': True,
            'is_staff': True,
            'is_superuser': True,
            'perfil': 'gestor',
            'status': 'ativo',
        }
        for campo, valor in valores.items():
            if getattr(usuario, campo) != valor:
                setattr(usuario, campo, valor)
                campos_alterados.append(campo)

        if campos_alterados:
            usuario.save(update_fields=campos_alterados)
            self.stdout.write(self.style.SUCCESS('Permissões do superusuário atualizadas.'))
        else:
            self.stdout.write('Superusuário já configurado.')
