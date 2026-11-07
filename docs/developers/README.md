# Documentación para desarrolladores

Índice de la base **Landing Page Creator** (`landing_page_creator`).

## Contenido

- [Arquitectura](architecture.md) — capas Django, ASGI, Channels, Celery.
- [Assets frontend](frontend-assets.md) — Bootstrap (django-bootstrap5) y HTMX vendoreado.

## Arranque rápido

1. Crear entorno virtual Python 3.12 e instalar dependencias:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements/dev.txt
   ```

2. Copiar variables de entorno:

   ```bash
   copy .env.example .env
   ```

   Para **SQLite** sin Docker, deja `POSTGRES_HOST` vacío en `.env`.

3. Migraciones y servidor de desarrollo:

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

   Para paridad **WebSockets + Channels** con producción, usa **Daphne** (o `docker compose up`).

## Docker (desarrollo)

```bash
copy .env.example .env
docker compose up --build
```

Servicios: Postgres 16, Redis 7, `web` (Daphne), `celery`.

## Docker (producción)

Construir y publicar la imagen, luego en el servidor:

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Ajusta `WEB_IMAGE` y credenciales en `.env` (no commitear secretos).

## Tests

```bash
pytest
```

Settings de test: `config.settings.test` (Channels in-memory, SQLite `pytest.sqlite`).

## Problemas conocidos

- **OneDrive / antivirus y `pip install`:** en Windows, instalar dependencias pesadas dentro de una carpeta sincronizada puede provocar `WinError 32` (archivo en uso). Si ocurre, mueve el `.venv` fuera de OneDrive, desactiva temporalmente el escaneo en la carpeta del proyecto, o vuelve a ejecutar `pip install -r requirements/base.txt` hasta completar sin errores.
- **django-ckeditor:** `manage.py check` puede advertir sobre CKEditor 4 LTS; valorar migración a CKEditor 5 en el roadmap del producto.

## Convenciones

- Apps de dominio bajo `apps/`.
- Settings: `config.settings.base` + `dev` / `prod` / `test`.
- Plantillas globales en `templates/`; parciales HTMX en `templates/partials/`.
