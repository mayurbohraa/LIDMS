"""SQLite before connection; one shared Neon database for local and hosted use."""

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .environment import load_environment

BASE_DIR = Path(__file__).resolve().parent.parent
load_environment(BASE_DIR)
ON_VERCEL = os.getenv("VERCEL") == "1"
DEBUG = os.getenv("DJANGO_DEBUG", "false" if ON_VERCEL else "true").lower() == "true"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG or ON_VERCEL:
        raise ImproperlyConfigured("Set DJANGO_SECRET_KEY before running in production.")
    SECRET_KEY = "local-development-only-do-not-use-in-production-9s7h4k2j"
if ON_VERCEL and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false on Vercel.")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]").split(",")
    if h.strip()
]
for key in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    if os.getenv(key):
        ALLOWED_HOSTS.append(os.environ[key])
CSRF_TRUSTED_ORIGINS = [
    v.strip() for v in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if v.strip()
]
for key in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
    if os.getenv(key):
        CSRF_TRUSTED_ORIGINS.append("https://" + os.environ[key])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "inventory.apps.InventoryConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "lidms.urls"
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
                "inventory.context_processors.workspace",
            ]
        },
    }
]
WSGI_APPLICATION = "lidms.wsgi.application"
ASGI_APPLICATION = "lidms.asgi.application"
database_url = os.getenv("DATABASE_URL", "")
if (ON_VERCEL or os.getenv("LIDMS_REQUIRE_POSTGRES") == "true") and not database_url:
    raise ImproperlyConfigured("Connect a PostgreSQL database and set DATABASE_URL on Vercel.")
DATABASES = {
    "default": dj_database_url.parse(
        database_url, conn_max_age=0, conn_health_checks=True, ssl_require=not DEBUG
    )
    if database_url
    else {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
if ON_VERCEL and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Vercel requires a persistent PostgreSQL DATABASE_URL.")
if database_url and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("DATABASE_URL must be a PostgreSQL connection string.")
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "login"
# Public demonstration credentials are opt-in and belong only to a sample database.
SHOW_DEMO_ACCOUNTS = os.getenv("LIDMS_SHOW_DEMO_ACCOUNTS", "false").lower() == "true"
DEMO_MODE = os.getenv("LIDMS_DEMO_MODE", "false").lower() == "true"
DEMO_PASSWORD = os.getenv("LIDMS_DEMO_PASSWORD", "")
AUTHENTICATION_BACKENDS = ["inventory.backends.EmailOrUsernameBackend"]
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
