# Assets frontend

## Bootstrap 5.3

Se sirve con **django-bootstrap5** (sin CDN). En plantillas:

```django
{% load django_bootstrap5 %}
{% bootstrap_css %}
{% bootstrap_javascript %}
```

Para cargar el bundle con atributo `defer` en el `<script>`, consulta la documentación de la versión instalada de `django-bootstrap5` (p. ej. argumentos con nombre en la etiqueta).

Tras cambios en estáticos de terceros, ejecutar `collectstatic` en entornos con `DEBUG=0`.

## HTMX 2.x (vendoreado)

| Campo | Valor |
|-------|--------|
| Versión fichero | **2.0.4** |
| Ruta en repo | `static/vendor/htmx/htmx.min.js` |
| Origen | Paquete oficial `htmx.org` (`dist/htmx.min.js`) |

Carga en `templates/base.html`:

```django
{% load static %}
<script src="{% static 'vendor/htmx/htmx.min.js' %}" defer></script>
```

### Actualizar HTMX

1. Descargar la nueva `htmx.min.js` desde la release deseada de [htmx.org](https://htmx.org/).
2. Sustituir `static/vendor/htmx/htmx.min.js`.
3. Actualizar la tabla de versiones en este documento y probar vistas con `hx-*`.

## CSS / JS propios

- `static/css/app.css` — sistema de diseño del sitio público y del panel (paleta KimiPOS: chile `#d92d20`, paprika `#f26b1d`, mole `#5a1018`, cacao `#241615`), layout con barra lateral (`templates/base_app.html`), tarjetas KPI y componentes POS.
- `static/css/guest.css` — flujo móvil del comensal (`templates/restaurants/guest/base_guest.html`).
- `static/css/qr_print.css` — hoja de estilos independiente para el sticker imprimible de mesa (`templates/restaurants/dashboard/qr_print.html`).
- `static/js/app.js` — confirmaciones con `<dialog>`, toasts, copiado al portapapeles, filtro en vivo del catálogo POS, conteo animado de KPIs y listeners HTMX (`htmx:afterSwap`, `htmx:afterRequest`, `htmx:confirm`).
- `static/js/home.js` — calculadora interactiva de propinas e inclinación 3D al cursor en la portada (`templates/core/home.html`).
- `static/js/guest.js` — calificación interactiva por estrellas y platillos, preservación de scroll en menú e `IntersectionObserver` de categorías en móvil.
