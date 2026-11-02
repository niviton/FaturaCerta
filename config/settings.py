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
    "apps.integracoes",
    "apps.monitoramento",
    "apps.faturas",
    "apps.analise",
    "apps.plataforma",
    "apps.portal",
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
FORMS_URLFIELD_ASSUME_HTTPS = True

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
CELERY_BEAT_SCHEDULE = {
    "status-inversores": {"task": "apps.monitoramento.tasks.coletar_status_todos", "schedule": 15 * 60},
    "geracao-diaria": {"task": "apps.monitoramento.tasks.coletar_geracao_todos", "schedule": 6 * 3600,
                       "kwargs": {"dias": 3}},
    "curvas-do-dia": {"task": "apps.monitoramento.tasks.coletar_curvas_hoje", "schedule": 30 * 60},
    "consolidar-esp": {"task": "apps.monitoramento.tasks.consolidar_medicoes_esp", "schedule": 15 * 60},
    "clima-real": {"task": "apps.monitoramento.tasks.atualizar_clima", "schedule": 60 * 60},
}

# Monitoramento (padrões; por integradora na fase de alertas)
MONITOR_HORAS_SEM_COMUNICACAO = int(os.environ.get("MONITOR_HORAS_SEM_COMUNICACAO", 3))
MONITOR_LIMIAR_ABAIXO = float(os.environ.get("MONITOR_LIMIAR_ABAIXO", 0.8))  # 7 dias < 80% do esperado
MONITOR_HORA_INICIO, MONITOR_HORA_FIM = 8, 16  # janela em que geração zero indica parada

# Integrações
# Clima real para a demonstração (Open-Meteo; gratuito só para uso NÃO comercial). Vazio desliga.
CLIMA_PROVIDER = os.environ.get("CLIMA_PROVIDER", "openmeteo")
CLIMA_LOCAL_PADRAO = (-5.795, -35.209)  # Natal-RN, quando a usina não tem coordenadas

INVERTER_PROVIDER = os.environ.get("INVERTER_PROVIDER", "fake")
METER_PROVIDER = os.environ.get("METER_PROVIDER", "fake")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
NOTIFY_EMAIL_PROVIDER = os.environ.get("NOTIFY_EMAIL_PROVIDER", "fake")  # fake|smtp
NOTIFY_WHATSAPP_PROVIDER = os.environ.get("NOTIFY_WHATSAPP_PROVIDER", "fake")  # fake|cloud
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID", "")
WHATSAPP_TEMPLATE = os.environ.get("WHATSAPP_TEMPLATE", "alerta_usina")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "FaturaCerta <nao-responda@faturacerta.local>")
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
