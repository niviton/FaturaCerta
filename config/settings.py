import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.environ.get(name, str(int(default))).lower() in ("1", "true", "yes")


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-key-troque-em-producao")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.core",
    "apps.accounts",
    "apps.cadastro",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.TenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.tenant",
            ],
        },
    },
]

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=60
    )
}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "login"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # HTMX lê o token pelo meta tag, não pelo cookie
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000

# Criptografia de campos (credenciais, tokens OAuth)
FIELD_ENCRYPTION_KEY = os.environ.get("FIELD_ENCRYPTION_KEY", "")

# Celery
REDIS_URL = os.environ.get("REDIS_URL", "")
CELERY_BROKER_URL = REDIS_URL or "memory://"
CELERY_RESULT_BACKEND = REDIS_URL or None
CELERY_TASK_ALWAYS_EAGER = not REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {}

# Integrações
INVERTER_PROVIDER = os.environ.get("INVERTER_PROVIDER", "fake")
METER_PROVIDER = os.environ.get("METER_PROVIDER", "fake")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
