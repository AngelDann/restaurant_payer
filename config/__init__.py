# Exponer la app de Celery cuando esté instalada (evita fallar en entornos incompletos).
try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except ImportError:
    __all__ = ()
