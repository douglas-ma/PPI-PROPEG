#!/usr/bin/env bash
# build.sh — executado pelo Render a cada deploy
set -o errexit   # para se qualquer comando falhar

pip install --upgrade pip
pip install -r requirements.txt

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input

# Aplica as migrations
python manage.py migrate

python manage.py shell -c "
from django.conf import settings
print('=== DIAGNÓSTICO STORAGE ===')
print('DEFAULT_FILE_STORAGE:', settings.DEFAULT_FILE_STORAGE)
print('CLOUDINARY_URL presente:', bool(getattr(settings, 'CLOUDINARY_URL', '')))
print('INSTALLED_APPS cloudinary:', 'cloudinary' in settings.INSTALLED_APPS)
print('===========================')
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
