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
from django.core.files.storage import default_storage
print('Storage:', default_storage.__class__.__name__)
# Simula o .url() de um arquivo de ODS
url = default_storage.url('ods_imagens/teste.png')
print('URL gerada:', url)
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
