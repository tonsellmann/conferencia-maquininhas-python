"""Configuração do painel. Em produção, SEGREDO e HOSTS vêm do ambiente; sem eles, só roda em modo
de desenvolvimento."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DEBUG", "1") == "1"


def _segredo() -> str | None:
    """Do ambiente, ou de um arquivo (o Docker monta os segredos em /run/secrets)."""
    if os.environ.get("SEGREDO"):
        return os.environ["SEGREDO"]
    arquivo = os.environ.get("SEGREDO_ARQUIVO")
    if arquivo and Path(arquivo).is_file():
        return Path(arquivo).read_text(encoding="utf-8").strip() or None
    return "so-para-desenvolvimento" if DEBUG else None


SECRET_KEY = _segredo()
if not SECRET_KEY:
    raise RuntimeError("Defina SEGREDO (ou SEGREDO_ARQUIVO) para rodar sem DEBUG.")
ALLOWED_HOSTS = os.environ.get("HOSTS", "localhost,127.0.0.1").split(",")
# Atrás do proxy (Caddy), o Django sabe que a conexão é HTTPS pelo cabeçalho que o proxy põe.
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("ORIGENS", "").split(",") if o]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "painel",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "painel_site.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "painel_site.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": os.environ.get("BANCO", BASE_DIR / "painel.sqlite3")}}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Bahia"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = os.environ.get("ESTATICOS", BASE_DIR / "estaticos")

LOGIN_URL = "admin:login"
LOGIN_REDIRECT_URL = "painel:lista"

# Os extratos de um mês cabem folgados em 10 MB; acima disso, é engano de arquivo.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
X_FRAME_OPTIONS = "DENY"
