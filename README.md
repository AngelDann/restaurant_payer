# Landing Page Creator

Base de proyecto Django (ASGI + Channels + Celery + Redis + Postgres) alineada con el stack definido en la planificación interna.

**Documentación para desarrolladores:** [docs/developers/README.md](docs/developers/README.md)

## Requisitos

- Python 3.12
- Docker (opcional, recomendado para Postgres/Redis/Celery)

## Inicio rápido

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

## Stack principal

- Django 6.x, Daphne, django-bootstrap5, HTMX local, WhiteNoise
- Channels + Redis, Celery + Redis
- PostgreSQL (Docker) o SQLite si `POSTGRES_HOST` está vacío
- Integraciones preparadas: S3/R2, OpenAI (pydantic-ai), Stripe, CKEditor, captcha

## Licencia

Proyecto privado — ajustar según necesidad.
