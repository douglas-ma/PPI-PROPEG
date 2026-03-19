#!/usr/bin/env bash
# build.sh — executado pelo Render a cada deploy
set -o errexit   # para se qualquer comando falhar

pip install --upgrade pip
pip install -r requirements.txt

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input

# Aplica as migrations
python manage.py migrate

# Testa o email
python manage.py shell -c "
from django.core.mail import send_mail
from django.conf import settings
print('Tentando enviar para:', settings.EMAIL_HOST_USER)
try:
    send_mail(
        'Teste PROPEG',
        'Se recebeu este email, o envio está funcionando.',
        settings.EMAIL_HOST_USER,
        [settings.EMAIL_HOST_USER],
        fail_silently=False,
    )
    print('SUCESSO: email enviado')
except Exception as e:
    print('ERRO:', type(e).__name__, str(e))
"

# Adicione o super user se ele não existir
python manage.py shell -c "
from projetos_institucionais.models import Usuario
cpf = '$ADMIN_CPF'
if not Usuario.objects.filter(cpf=cpf).exists():
    Usuario.objects.create_superuser(
        cpf=cpf,
        username=cpf,
        email='$ADMIN_EMAIL',
        password='$ADMIN_PASSWORD',
        first_name='Admin',
        last_name='PROPEG',
        perfil='gestor',
        status='ativo',
        is_active=True,
    )
    print('Superusuario criado.')
else:
    print('Superusuario ja existe.')
"
