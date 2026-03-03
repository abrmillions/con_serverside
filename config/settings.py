from pathlib import Path
import os
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None
from .patches import apply_patches

BASE_DIR = Path(__file__).resolve().parent.parent
apply_patches()

if load_dotenv:
    try:
        load_dotenv(str(BASE_DIR / ".env"))
    except Exception:
        pass

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY") or "change-me-in-production"

DEBUG = (os.environ.get("DJANGO_DEBUG") or os.environ.get("DEBUG") or "1") == "1"

_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS") or os.environ.get("ALLOWED_HOSTS") or ""
ALLOWED_HOSTS = _hosts.split(",") if _hosts else []

# CSRF trusted origins: accept both DJANGO_* and unprefixed envs
_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS") or os.environ.get("CSRF_TRUSTED_ORIGINS") or ""
CSRF_TRUSTED_ORIGINS = [o for o in _csrf.split(",") if o] if _csrf else []

if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "[::1]",
    ]
    if not CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS = [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]

# Safe defaults for Render if not explicitly configured
if not DEBUG:
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS = [
            ".onrender.com",
            "localhost",
            "127.0.0.1",
            "[::1]",
        ]
    if not CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS = [
            "https://backend-te21.onrender.com",
            "https://digital-licensing.vercel.app",
        ]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "users",
    "licenses",
    "vehicles",
    "partnerships",
    "payments",
    "applications",
    "documents",
    "systemsettings",
    "contact",
    "companies.apps.CompaniesConfig",
    "license_history.apps.LicenseHistoryConfig",
]

# Use custom user model
AUTH_USER_MODEL = os.environ.get("AUTH_USER_MODEL", "users.CustomUser")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database: Use SQLite as the primary database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Only apply WhiteNoise middleware outside of development AND when STATIC_ROOT exists
try:
    if not DEBUG and STATIC_ROOT.exists():
        MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
except Exception:
    pass

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# REST framework and JWT
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),
}

from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.environ.get("JWT_ACCESS_MINUTES", "60"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.environ.get("JWT_REFRESH_DAYS", "1"))),
    "ROTATE_REFRESH_TOKENS": False,
}

# CORS
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if os.environ.get("CORS_ALLOWED_ORIGINS") else []
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
]

# In development, allow the frontend origin by default
if DEBUG and not CORS_ALLOW_ALL_ORIGINS and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:8000",
    ]

# In production, default to known frontend origin if not configured
ADMIN_IP_WHITELIST = [ip.strip() for ip in (os.environ.get("ADMIN_IP_WHITELIST") or "").split(",") if ip.strip()]
if not DEBUG and not CORS_ALLOW_ALL_ORIGINS and not CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS = [
        "https://digital-licensing.vercel.app",
    ]

# QR token max age (seconds). Default 7 days; can be overridden via env var.
# Shorter default reduces exposure if tokens are leaked. Override with `QR_TOKEN_MAX_AGE_SECONDS` env var.
QR_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('QR_TOKEN_MAX_AGE_SECONDS', str(60 * 60 * 24 * 7)))

# Ensure correct scheme on Render behind proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
