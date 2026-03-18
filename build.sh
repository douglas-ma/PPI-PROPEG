#!/usr/bin/env bash
# build.sh — executado pelo Render a cada deploy
set -o errexit   # para se qualquer comando falhar

pip install --upgrade pip
pip install -r requirements.txt

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input

# Aplica as migrations
python manage.py migrate

# Adicione o super user se ele não existir
python manage.py shell -c "
from projetos_institucionais.models import Usuario
if not Usuario.objects.filter(cpf='$ADMIN_CPF').exists():
    u = Usuario.objects.create_superuser(
        username='$ADMIN_CPF',
        cpf='$ADMIN_CPF',
        email='$ADMIN_EMAIL',
        password='$ADMIN_PASSWORD',
        perfil='gestor',
        status='ativo',
    )
    print('Superusuário criado com sucesso.')
else:
    print('Superusuário já existe.')
"
