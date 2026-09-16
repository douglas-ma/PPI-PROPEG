#!/usr/bin/env bash
# build.sh — executado pelo Render a cada deploy
set -o errexit   # para se qualquer comando falhar

pip install --upgrade pip
pip install -r requirements.txt

# Coleta os arquivos estáticos
python manage.py collectstatic --no-input

# Aplica as migrations e garante os catálogos institucionais essenciais.
python manage.py migrate
python manage.py carregar_catalogo_ufac
python manage.py normalizar_ods

# Cria o administrador inicial sem interpolar segredos no shell.
python manage.py garantir_superusuario
