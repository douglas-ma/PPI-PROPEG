"""
settings_prod.py — Configurações de PRODUÇÃO para deploy no Render.
"""

from .settings import *
import dj_database_url
from decouple import config

# ─────────────────────────────────────────────────────────────────────────────
# Segurança
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')
DEBUG = False

ALLOWED_HOSTS = [
    host.strip()
    for host in config('ALLOWED_HOSTS', default='.onrender.com').split(',')
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in config(
        'CSRF_TRUSTED_ORIGINS', default='https://*.onrender.com'
    ).split(',')
    if origin.strip()
]

# ─────────────────────────────────────────────────────────────────────────────
# Banco de dados — PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.parse(
        config('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=True,
    )
}

# ─────────────────────────────────────────────────────────────────────────────
# Arquivos estáticos — WhiteNoise
# ─────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# ─────────────────────────────────────────────────────────────────────────────
# Arquivos de mídia — Cloudinary
# ImageField  → MediaCloudinaryStorage    (resource_type='image')
# FileField   → RawMediaCloudinaryStorage (resource_type='raw')  ← PDFs, docs
# A separação é feita no models.py via storage=_raw_storage()
# ─────────────────────────────────────────────────────────────────────────────
cloudinary_url = config('CLOUDINARY_URL')

import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(cloudinary_url=cloudinary_url)

INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
CLOUDINARY_URL = cloudinary_url
MEDIA_URL = '/media/'

STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': cloudinary_url.split('@')[-1].strip('/'),
    'FILE_OVERWRITE': False,
    'MEDIA_TAG': 'media',
    'SECURE': True,
    'ACCESS_CONTROL': [{'access_type': 'anonymous'}],
}

# ─────────────────────────────────────────────────────────────────────────────
# E-mail — Brevo API
# ─────────────────────────────────────────────────────────────────────────────
BREVO_API_KEY = config('BREVO_API_KEY')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL')
EMAIL_BACKEND = 'projetos_institucionais.email_backend.BrevoEmailBackend'
APROVACAO_CENTRO_LINK_HORAS = config('APROVACAO_CENTRO_LINK_HORAS', default=168, cast=int)

# ─────────────────────────────────────────────────────────────────────────────
# Segurança HTTPS
# ─────────────────────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER        = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT            = True
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD            = False
SECURE_CONTENT_TYPE_NOSNIFF    = True
SECURE_REFERRER_POLICY         = 'same-origin'
X_FRAME_OPTIONS                = 'DENY'
