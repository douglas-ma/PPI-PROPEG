"""
settings_prod.py — Configurações de PRODUÇÃO para deploy no Render.
Importe a partir do settings.py base usando variáveis de ambiente.
"""

from .settings import *
import os
import dj_database_url
from decouple import config

# ─────────────────────────────────────────────────────────────────────────────
# Segurança
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='.onrender.com'
).split(',')

# CSRF para o domínio do Render
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='https://*.onrender.com'
).split(',')


# ─────────────────────────────────────────────────────────────────────────────
# Banco de dados — PostgreSQL via DATABASE_URL
# ─────────────────────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL',
        conn_max_age=600,
        ssl_require=True,
    )
}


# ─────────────────────────────────────────────────────────────────────────────
# Arquivos estáticos — WhiteNoise serve direto do Gunicorn
# ─────────────────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # logo após SecurityMiddleware
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
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ─────────────────────────────────────────────────────────────────────────────
# Arquivos de mídia — Cloudinary (recomendado) ou AWS S3
# Render não tem disco persistente no plano gratuito.
# Configure CLOUDINARY_URL no painel do Render.
# ─────────────────────────────────────────────────────────────────────────────
cloudinary_url = config('CLOUDINARY_URL', default='')
if cloudinary_url:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
    INSTALLED_APPS += ['cloudinary_storage', 'cloudinary']
    CLOUDINARY_URL = cloudinary_url
    MEDIA_URL = '/media/'
else:
    # Fallback: pasta local (só funciona se o serviço tiver disco persistente)
    MEDIA_URL  = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'


# ─────────────────────────────────────────────────────────────────────────────
# E-mail SMTP (Gmail ou outro)
# Configure EMAIL_HOST_USER e EMAIL_HOST_PASSWORD no painel do Render
# ─────────────────────────────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
BREVO_API_KEY = config('BREVO_API_KEY', default='')
EMAIL_HOST     = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT     = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS  = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)
EMAIL_TIMEOUT = 10

# ─────────────────────────────────────────────────────────────────────────────
# Segurança HTTPS
# ─────────────────────────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER       = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT            = True
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD            = True
SECURE_CONTENT_TYPE_NOSNIFF    = True
