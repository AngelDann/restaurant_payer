"""
Base Django settings. Environment-specific modules import from here.
"""
from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="change-me-in-production")

DEBUG = config("DEBUG", default=False, cast=bool)

ALLOWED_HOSTS = list(config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv()))

CSRF_TRUSTED_ORIGINS = list(
    config("CSRF_TRUSTED_ORIGINS", default="http://127.0.0.1:8000,http://localhost:8000", cast=Csv())
)

SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=False, cast=bool)
CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=False, cast=bool)

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_bootstrap5",
    "django_htmx",
    "ckeditor",
    "ckeditor_uploader",
    "captcha",
    "channels",
    "apps.core",
    "apps.ai_chat",
    "apps.docs",
    "apps.legal",
    "apps.billing",
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
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

POSTGRES_HOST = config("POSTGRES_HOST", default="")
if POSTGRES_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("POSTGRES_DB", default="landing_page_creator"),
            "USER": config("POSTGRES_USER", default="postgres"),
            "PASSWORD": config("POSTGRES_PASSWORD", default="postgres"),
            "HOST": POSTGRES_HOST,
            "PORT": config("POSTGRES_PORT", default="5432"),
            "OPTIONS": {"connect_timeout": 10},
        }
    }
else:
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

LANGUAGE_CODE = "es-es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

USE_S3 = config("USE_S3", default=False, cast=bool)

STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

if USE_S3:
    AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
    AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
    AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
    AWS_S3_ENDPOINT_URL = config("AWS_S3_ENDPOINT_URL", default="")
    AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="auto")
    AWS_S3_CUSTOM_DOMAIN = config("AWS_S3_CUSTOM_DOMAIN", default="")
    _acl = config("AWS_DEFAULT_ACL", default="")
    if _acl:
        AWS_DEFAULT_ACL = _acl
    AWS_QUERYSTRING_AUTH = config("AWS_QUERYSTRING_AUTH", default=True, cast=bool)

    STORAGES["default"] = {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"}
else:
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("CHANNELS_REDIS_URL", default="redis://127.0.0.1:6379/0")],
        },
    },
}

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default="redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="webmaster@localhost")

OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
OPENAI_BASE_URL = config("OPENAI_BASE_URL", default="")
OPENAI_MODEL = config("OPENAI_MODEL", default="gpt-4o-mini")
OPENAI_CHAT_MODEL = config("OPENAI_CHAT_MODEL", default="")
AI_OPENAI_TRANSPORT = config("AI_OPENAI_TRANSPORT", default="chat")
AI_CHAT_SYSTEM_INSTRUCTIONS = config("AI_CHAT_SYSTEM_INSTRUCTIONS", default="")
AI_CHAT_SYSTEM_PROMPT_PATH = config(
    "AI_CHAT_SYSTEM_PROMPT_PATH",
    default=str(BASE_DIR / "prompts" / "main_system.md"),
)
AI_CHAT_ENFORCE_QUOTA = config("AI_CHAT_ENFORCE_QUOTA", default=False, cast=bool)

STRIPE_PUBLIC_KEY = config("STRIPE_PUBLIC_KEY", default="")
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

DATA_UPLOAD_MAX_MEMORY_SIZE = config(
    "DATA_UPLOAD_MAX_MEMORY_SIZE",
    default=2621440,
    cast=int,
)
FILE_UPLOAD_MAX_MEMORY_SIZE = config(
    "FILE_UPLOAD_MAX_MEMORY_SIZE",
    default=2621440,
    cast=int,
)

CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "full",
        "height": 300,
        "width": "100%",
    },
}

CAPTCHA_LENGTH = config("CAPTCHA_LENGTH", default=6, cast=int)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
