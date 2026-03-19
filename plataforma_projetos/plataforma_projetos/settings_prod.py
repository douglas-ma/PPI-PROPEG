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
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='.onrender.com').split(',')
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS', default='https://*.onrender.com'
).split(',')

# ─────────────────────────────────────────────────────────────────────────────
# Banco de dados — PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
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
cloudinary_url = config('CLOUDINARY_URL', default='')
if cloudinary_url:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api

    cloudinary.config(cloudinary_url=cloudinary_url)

    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    CLOUDINARY_URL  = cloudinary_url

    # Sem prefixo espúrio no MEDIA_URL — o cloudinary monta as URLs via .url()
    MEDIA_URL = '/media/'

    # Django 5.x — STORAGES substitui DEFAULT_FILE_STORAGE
    STORAGES = {
        'default': {
            'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

    # Configurações do django-cloudinary-storage
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': cloudinary_url.split('@')[-1].strip('/'),
        'FILE_OVERWRITE': False,       # gera nome único em vez de sobrescrever
        'MEDIA_TAG': 'media',          # tag padrão para organização no Cloudinary
    }
else:
    MEDIA_URL  = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }

# ─────────────────────────────────────────────────────────────────────────────
# E-mail — Brevo API
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND      = 'django.core.mail.backends.dummy.EmailBackend'
BREVO_API_KEY      = config('BREVO_API_KEY', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@propeg.ufac.br')

# ─────────────────────────────────────────────────────────────────────────────
# Segurança HTTPS
# ─────────────────────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER        = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT            = True
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD            = True
SECURE_CONTENT_TYPE_NOSNIFF    = True