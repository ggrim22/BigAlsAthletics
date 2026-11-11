from pathlib import Path
from decouple import config
import dj_database_url
from django.contrib import messages

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# BASIC SETTINGS
# ============================================================

SECRET_KEY = config("SECRET_KEY", default="unsafe-default-key")
DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost").split(",")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# ============================================================
# INSTALLED APPS
# ============================================================

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
    'storages',
]

if DEBUG:
    INSTALLED_APPS.append('debug_toolbar')

# ============================================================
# MIDDLEWARE
# ============================================================

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

# ============================================================
# TEMPLATES
# ============================================================

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    }
]

WSGI_APPLICATION = "core.wsgi.application"

# ============================================================
# DATABASE
# ============================================================

if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("LOCAL_DB_NAME", default="bigals_dev"),
            "USER": config("LOCAL_DB_USER", default="postgres"),
            "PASSWORD": config("LOCAL_DB_PASSWORD", default="postgres"),
            "HOST": config("LOCAL_DB_HOST", default="localhost"),
            "PORT": config("LOCAL_DB_PORT", default="5432"),
        }
    }
else:
    DATABASES = {
        "default": dj_database_url.config(conn_max_age=600)
    }

# ============================================================
# STATIC & MEDIA
# ============================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

if DEBUG:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    # In DEBUG, Django skips the content hash in {% static %} URLs, so WhiteNoise
    # serves /static/css/style.css with no Cache-Control and browsers fall back to
    # heuristic caching off Last-Modified — which can pin an edited CSS/JS file for
    # days. Serve edits straight from static/ and never cache them in development.
    WHITENOISE_AUTOREFRESH = True
    WHITENOISE_USE_FINDERS = True

    def _dev_no_cache_headers(headers, path, url):
        """Force revalidation so an edited stylesheet is never served from cache."""
        headers["Cache-Control"] = "no-cache"

    WHITENOISE_ADD_HEADERS_FUNCTION = _dev_no_cache_headers

else:
    # Production uses S3
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_CUSTOM_DOMAIN = f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

# ============================================================
# STRIPE
# ============================================================

STRIPE_PUBLISHABLE_KEY = config("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

# ============================================================
# CRISPY FORMS
# ============================================================

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MESSAGE_TAGS = {
    messages.DEBUG: "bg-light",
    messages.INFO: "text-white bg-primary",
    messages.SUCCESS: "text-white bg-success",
    messages.WARNING: "text-dark bg-warning",
    messages.ERROR: "text-white bg-danger",
}
# ============================================================
# LOGIN
# ============================================================

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "order:index"
LOGOUT_REDIRECT_URL = "order:index"

# ============================================================
# CONTENT SECURITY POLICY
# ============================================================

CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_FONT_SRC = ("'self'",)

if DEBUG:
    CSP_IMG_SRC = ("'self'", "data:", "http://localhost:8000")
else:
    CSP_IMG_SRC = (
        "'self'",
        "data:",
        f"https://{AWS_S3_CUSTOM_DOMAIN}",
        "https://*.amazonaws.com",
    )

CSP_CONNECT_SRC = ("'self'",)
CSP_FRAME_SRC = ("'self'",)

# ============================================================
# EMAIL
# ============================================================




DEFAULT_FROM_EMAIL = config("SENDGRID_FROM_EMAIL", default="noreply@example.com")
CONTACT_EMAIL = config("CONTACT_EMAIL", default="")

if DEBUG:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.sendgrid.net"
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = "apikey"
    EMAIL_HOST_PASSWORD = config("SENDGRID_API_KEY", default="")

# ============================================================
# ALERTS
# ============================================================
# Comma-separated. SMS works through carrier email-to-SMS gateways, e.g.
#   Verizon  5551234567@vtext.com
#   AT&T     5551234567@txt.att.net
#   T-Mobile 5551234567@tmomail.net
# Leave either blank to disable that channel.


def _csv_setting(name):
    return [item.strip() for item in config(name, default="").split(",") if item.strip()]


ALERT_EMAIL_RECIPIENTS = _csv_setting("ALERT_EMAILS") or ([CONTACT_EMAIL] if CONTACT_EMAIL else [])
ALERT_SMS_RECIPIENTS = _csv_setting("ALERT_SMS")

# ============================================================
# LOGGING
# ============================================================
# Level is INFO so the breadcrumbs around an order (created, email sent) are in
# `heroku logs` when something goes wrong; ERROR alone only shows the fallout.

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Django's request logger is noisy at INFO (every 4xx); keep it at WARNING.
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.server": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "order": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ============================================================
# SENTRY (error monitoring)
# ============================================================
# No-op until SENTRY_DSN is set, so local and CI runs are unaffected.

SENTRY_DSN = config("SENTRY_DSN", default="")

if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=config("SENTRY_ENVIRONMENT", default="production"),
            # Sample rate for performance traces; errors are always captured.
            traces_sample_rate=float(config("SENTRY_TRACES_SAMPLE_RATE", default="0.0")),
            send_default_pii=False,
        )
    except ImportError:  # pragma: no cover - dependency missing in this env
        import warnings

        warnings.warn("SENTRY_DSN is set but sentry-sdk is not installed; skipping.")



