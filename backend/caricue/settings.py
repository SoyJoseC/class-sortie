"""Django settings for CariCue.

Everything environment-specific is read from environment variables so the same
image can run in development and production. See `.env.example` at the repo
root for the full list.
"""

from __future__ import annotations

from pathlib import Path

from .env import ImproperlyConfigured, env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
DEBUG = env_bool("DJANGO_DEBUG", default=False)

INSECURE_DEV_SECRET = "dev-only-insecure-secret-key-change-me"
SECRET_KEY = env_str("DJANGO_SECRET_KEY", default=INSECURE_DEV_SECRET if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is disabled."
    )
if not DEBUG and SECRET_KEY == INSECURE_DEV_SECRET:
    raise ImproperlyConfigured(
        "Refusing to start with the development SECRET_KEY outside of DEBUG."
    )

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Absolute origin students reach the app on. Used to build QR / join links.
PUBLIC_BASE_URL = env_str("PUBLIC_BASE_URL", default="http://localhost:5173").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "caricue.core",
    "caricue.accounts",
    "caricue.classroom",
    "caricue.activities",
    "caricue.live",
    "caricue.insights",
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

ROOT_URLCONF = "caricue.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "caricue.wsgi.application"

# --------------------------------------------------------------------------- #
# Database
# --------------------------------------------------------------------------- #
# PostgreSQL is the supported engine. SQLite is available strictly as a
# zero-infrastructure escape hatch for running the test suite locally.
if env_str("DJANGO_DB_ENGINE", default="postgres") == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env_str("DJANGO_SQLITE_PATH", default=str(BASE_DIR / "db.sqlite3")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("POSTGRES_DB", default="caricue"),
            "USER": env_str("POSTGRES_USER", default="caricue"),
            "PASSWORD": env_str("POSTGRES_PASSWORD", default="caricue"),
            "HOST": env_str("POSTGRES_HOST", default="localhost"),
            "PORT": env_str("POSTGRES_PORT", default="5432"),
            "CONN_MAX_AGE": env_int("POSTGRES_CONN_MAX_AGE", 60),
            "OPTIONS": {"connect_timeout": 10},
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #
AUTH_USER_MODEL = "accounts.Teacher"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------- #
# Internationalisation
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Static files
# --------------------------------------------------------------------------- #
STATIC_URL = "static/"
STATIC_ROOT = Path(env_str("DJANGO_STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --------------------------------------------------------------------------- #
# Sessions, CSRF and transport security
# --------------------------------------------------------------------------- #
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "caricue_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env_int("DJANGO_SESSION_COOKIE_AGE", 60 * 60 * 12)
CSRF_COOKIE_NAME = "caricue_csrftoken"
CSRF_COOKIE_HTTPONLY = False  # the SPA must read it to set the X-CSRFToken header
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

if DEBUG:
    # The Vite dev server proxies /api, but the browser still sends
    # Origin: http://localhost:5173. Django 4+ rejects that unless the
    # origin is listed here — distinct from ALLOWED_HOSTS.
    _dev_csrf_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        PUBLIC_BASE_URL,
    ]
    CSRF_TRUSTED_ORIGINS = list(
        dict.fromkeys([*_dev_csrf_origins, *CSRF_TRUSTED_ORIGINS])
    )

SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", default=not DEBUG)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE

# Behind Nginx/an HTTPS load balancer these let Django know the real scheme.
USE_X_FORWARDED_HOST = env_bool("DJANGO_USE_X_FORWARDED_HOST", default=not DEBUG)
if env_bool("DJANGO_TRUST_PROXY_SSL_HEADER", default=not DEBUG):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG
)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --------------------------------------------------------------------------- #
# Django REST Framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "caricue.core.pagination.DefaultPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        # Public, unauthenticated endpoints used by students.
        "public_lookup": env_str("THROTTLE_PUBLIC_LOOKUP", default="30/min"),
        "public_join": env_str("THROTTLE_PUBLIC_JOIN", default="20/min"),
        "public_submit": env_str("THROTTLE_PUBLIC_SUBMIT", default="20/min"),
        "auth_attempt": env_str("THROTTLE_AUTH_ATTEMPT", default="10/min"),
    },
    "EXCEPTION_HANDLER": "caricue.core.exceptions.safe_exception_handler",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# --------------------------------------------------------------------------- #
# CariCue domain settings
# --------------------------------------------------------------------------- #
CARICUE = {
    # Activity builder limits (product decision: keep formative checks short).
    "MIN_QUESTIONS_PER_ACTIVITY": env_int("CARICUE_MIN_QUESTIONS", 1),
    "MAX_QUESTIONS_PER_ACTIVITY": env_int("CARICUE_MAX_QUESTIONS", 5),
    "MAX_CHOICES_PER_QUESTION": env_int("CARICUE_MAX_CHOICES", 6),
    "SHORT_CODE_LENGTH": env_int("CARICUE_SHORT_CODE_LENGTH", 6),
    # Insight thresholds.
    "HIGH_CONFIDENCE_THRESHOLD": env_int("CARICUE_HIGH_CONFIDENCE_THRESHOLD", 4),
    "LOW_CONFIDENCE_THRESHOLD": env_int("CARICUE_LOW_CONFIDENCE_THRESHOLD", 2),
    "ATTENTION_SCORE_THRESHOLD": env_int("CARICUE_ATTENTION_SCORE_THRESHOLD", 50),
    "LOW_CORRECTNESS_THRESHOLD": env_int("CARICUE_LOW_CORRECTNESS_THRESHOLD", 60),
    "COMMON_ANSWER_LIMIT": env_int("CARICUE_COMMON_ANSWER_LIMIT", 5),
    # Dashboard polling interval advertised to the frontend (seconds).
    "DASHBOARD_POLL_SECONDS": env_int("CARICUE_DASHBOARD_POLL_SECONDS", 4),
    # Days after a changed-plan reflection before nudging a follow-up on dashboard.
    "FOLLOWUP_NUDGE_DAYS": env_int("CARICUE_FOLLOWUP_NUDGE_DAYS", 2),
}

# Optional AI suggestion layer. Defaults to the deterministic rule-based
# provider so the product works with no API key at all.
INSIGHT_PROVIDER = env_str(
    "CARICUE_INSIGHT_PROVIDER",
    default="caricue.insights.providers.RuleBasedInsightProvider",
)
INSIGHT_LLM_API_KEY = env_str("CARICUE_LLM_API_KEY", default="")
INSIGHT_LLM_MODEL = env_str("CARICUE_LLM_MODEL", default="mock-llm-v1")

# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {
        "handlers": ["console"],
        "level": env_str("DJANGO_LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "caricue": {
            "handlers": ["console"],
            "level": env_str("CARICUE_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
}
