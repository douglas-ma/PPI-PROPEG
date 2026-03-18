#!/usr/bin/env bash
# build.sh — executado pelo Render a cada deploy
set -o errexit   # para se qualquer comando falhar

pip install --upgrade pip
pip install -r requirements.txt

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input

# Aplica as migrations
python manage.py migrate

# Cria superusuário padrão se não existir (opcional)
# python manage.py createsuperuser --no-input || true
