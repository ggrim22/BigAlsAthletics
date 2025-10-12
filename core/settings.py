import os
from pathlib import Path

import dj_database_url
import django_heroku
from django.contrib import messages
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-default-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'order',
    'crispy_forms',
    'crispy_bootstrap5',
]

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'csp.middleware.CSPMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.HtmxMessageMiddleware',
]

if DEBUG:
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DATABASES = {
    'default': dj_database_url.config(conn_max_age=600)
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

MESSAGE_TAGS = {
    messages.DEBUG: "bg-light",
    messages.INFO: "text-white bg-primary",
    messages.SUCCESS: "text-white bg-success",
    messages.WARNING: "text-dark bg-warning",
    messages.ERROR: "text-white bg-danger",
}

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_FONT_SRC = ("'self'",)
CSP_IMG_SRC = ("'self'", 'data:')
CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_SRC = ("'self'",)

django_heroku.settings(locals(), staticfiles=False)
