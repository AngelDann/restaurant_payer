# PlavPay (RestaurantPayment)

> **Plataforma web para cobro en mesa mediante códigos QR, división inteligente de cuentas y pagos digitales instantáneos en restaurantes.**

---

## 📋 Tabla de Contenidos

1. [Acerca del Proyecto](#-acerca-del-proyecto)
2. [¿Para quién está dirigido?](#-para-quién-está-dirigido)
3. [¿Cómo funciona? (Flujo de Operación)](#-cómo-funciona-flujo-de-operación)
4. [Características Principales](#-características-principales)
   - [Experiencia del Comensal (Guest Hub)](#1-experiencia-del-comensal-guest-hub)
   - [Panel de Administración y POS (Dashboard)](#2-panel-de-administración-y-pos-dashboard)
   - [Arquitectura de Pagos (Stripe Connect)](#3-arquitectura-de-pagos-stripe-connect)
5. [Stack Tecnológico](#-stack-tecnológico)
6. [Estructura del Proyecto](#-estructura-del-proyecto)
7. [Requisitos Previos](#-requisitos-previos)
8. [Guía de Instalación y Setup](#-guía-de-instalación-y-setup)
   - [Opción A: Instalación Local con Entorno Virtual](#opción-a-instalación-local-con-entorno-virtual)
   - [Opción B: Despliegue con Docker Compose](#opción-b-despliegue-con-docker-compose)
9. [Variables de Entorno (`.env`)](#-variables-de-entorno-env)
10. [Ejecución de Pruebas](#-ejecución-de-pruebas)
11. [⚠️ Advertencias y Notas Especiales](#️-advertencias-y-notas-especiales)

---

## 🍽️ Acerca del Proyecto

**PlavPay** es una solución integral diseñada para modernizar y agilizar la experiencia de consumo y cobro en establecimientos gastronómicos. Elimina la fricción tradicional del proceso de pago en restaurantes: el comensal ya no tiene que esperar a que el mesero le lleve la cuenta ni esperar una terminal física TPV (Point of Sale).

Cada mesa cuenta con un código QR único con token seguro. Al escanearlo con la cámara de su teléfono móvil (sin descargar aplicaciones nativas ni registrarse obligatoriamente), el cliente accede al portal de su mesa, visualiza la comanda en tiempo real, elige cómo dividir la cuenta, añade propina y paga en segundos utilizando **Apple Pay**, **Google Pay** o **tarjetas de débito/crédito**.

---

## 🎯 ¿Para quién está dirigido?

- **Dueños y Administradores de Restaurantes, Bares, Terrazas y Cafeterías:**
  - Reducción drástica en tiempos de rotación de mesas (hasta 15-20 minutos ahorrados por servicio).
  - Mayor volumen de propinas para el personal gracias a selectores rápidos e intuitivos.
  - Automatización de cobros y liquidación directa a su cuenta bancaria mediante **Stripe Connect Express**.
  - Panel de control para gestionar menú, disponibilidad de platillos y mesas en tiempo real.
- **Meseros y Personal de Salón:**
  - Eliminación de traslados innecesarios llevando y trayendo terminales bancarias o dividiendo cuentas manualmente en caja.
  - Visualización inmediata en el POS cuando una mesa o platillo ha sido pagado.
- **Comensales y Clientes:**
  - Control total sobre su consumo, transparencia de precios e inmediatez.
  - Libertad para pagar la cuenta completa, dividir en partes iguales o pagar únicamente los platillos consumidos individualmente.
  - Comprobantes digitales y canal directo para dejar opiniones sobre los platillos degustados.

---

## 🔄 ¿Cómo funciona? (Flujo de Operación)

```
[Mesa Física] ──> Escaneo de Código QR
      │
      ▼
[Guest Hub: /r/<slug>/t/<mesa>/]
      ├── 1. Consulta la comanda abierta en tiempo real (vía WebSockets)
      ├── 2. Puede explorar el menú digital y ordenar platillos adicionales
      ├── 3. Selecciona la modalidad de división (Total / Partes / Por platillos / Custom)
      ├── 4. Elige el porcentaje de propina deseado (0%, 10%, 15%, 20%)
      └── 5. Procesa el pago con Stripe (Apple Pay, Google Pay, Tarjeta)
            │
            ▼
      [Webhook / Confirmación Inmediata]
            ├── Actualiza saldo de la mesa en el POS del restaurante en vivo
            └── Desbloquea módulo de feedback y reseña de platillos degustados
```

---

## ✨ Características Principales

### 1. Experiencia del Comensal (Guest Hub)
- **Cero Fricción:** Funciona 100% en el navegador web móvil; no requiere descargar apps de tiendas (App Store/Play Store) ni cuentas obligatorias.
- **División Inteligente de Cuentas (Split Bill):**
  - **Cuenta Completa:** Pago del total restante de la mesa en una sola transacción.
  - **Partes Iguales:** Cálculo automático para dividir el saldo entre $N$ personas.
  - **Por Platillos:** Selector interactivo donde cada comensal elige exactamente los platillos que consumió y solo paga por ellos (descontando las unidades ya pagadas).
  - **Monto Personalizado:** Posibilidad de abonar un importe específico libre.
- **Gestión de Propinas:** Selectores accesibles para calcular propina sugerida (10%, 15%, 20%) o personalizada en tiempo real con recálculo dinámico vía HTMX y JavaScript.
- **Calificación de Platillos y Google Reviews:**
  - El comensal puede dar calificación positiva (👍) o negativa (👎) a cada platillo de su comanda.
  - Deja una calificación general del servicio (1 a 5 estrellas) con comentarios.
  - **Filtro de Reseñas:** Si la calificación es excelente (≥ 4 estrellas) y el restaurante tiene configurada su URL de Google Maps, el sistema invita al cliente a publicar su reseña pública con un solo clic.
- **Recibo Digital:** Comprobante desglosado con desglose de subtotal, propina, método de pago y fecha.

### 2. Panel de Administración y POS (Dashboard)
- **Gestión Multi-restaurante:** Panel para administrar la información de la marca, logotipo, divisa (por defecto MXN), comisión de plataforma y enlace de Google Maps.
- **Punto de Venta (POS) en Vivo:**
  - Monitoreo en tiempo real del estado de cada mesa (`Abierta`, `Pago Parcial`, `Pagada`, `Cancelada`).
  - Apertura rápida de órdenes por mesa asignando mesero y número de comensales.
  - Adición de platillos a la comanda con notas personalizadas.
  - Barra de progreso que ilustra el porcentaje pagado de la cuenta en vivo.
- **Generador e Impresor de Códigos QR:**
  - Generación automática de tokens criptográficos únicos por mesa.
  - Vista optimizada de impresión (`/dashboard/<slug>/qr-print/`) con tarjetas visuales listas para imprimir, recortar y colocar como stickers o portarretratos en las mesas físicas.
- **Gestor de Catálogo y Menú:**
  - Organización por categorías jerárquicas con ordenamiento personalizado.
  - Configuración de platillos con precio, foto, descripción detallada y gramaje/volumen.
  - Conmutador rápido de disponibilidad (apagar/encender platillos si se agotan en cocina).
- **WebSockets / Actualización en Vivo:** Integración con Django Channels para refrescar comensales y POS de manera inmediata ante cualquier evento.

### 3. Arquitectura de Pagos (Stripe Connect)
- Implementación de **Stripe Connect Express** (especialmente optimizado para transferencias directas a cuentas bancarias mexicanas).
- Flujo de onboarding guiado para que los dueños de restaurantes conecten su cuenta en Stripe de manera segura y verifiquen sus datos fiscales/bancarios.
- **Comisión de Plataforma Automática:** En cada pago procesado, la plataforma deduce su comisión porcentual (`platform_fee_percent`, por defecto 2.5%) a través del parámetro `application_fee_amount` de Stripe, transfiriendo el resto directamente al restaurante.
- Compatibilidad oficial con **Apple Pay** mediante la ruta estándar `.well-known/apple-developer-merchantid-domain-association`.

---

## 🛠️ Stack Tecnológico

| Capa | Tecnologías |
|---|---|
| **Lenguaje** | Python 3.12+ |
| **Framework Backend** | Django 6.0 |
| **Servidor ASGI / WebSockets** | Daphne 4.x + Django Channels 4.x + channels-redis |
| **Tareas Asíncronas** | Celery 5.x + Redis |
| **Base de Datos** | PostgreSQL 16 (Producción/Docker) / SQLite 3 (Desarrollo local sin configuración extra) |
| **Frontend & UI** | Django Templates, HTML5 semántico, Bootstrap 5.3 (empaquetado localmente vía `django-bootstrap5`), HTMX local (`django-htmx`), CSS3 modular (`guest.css`, `qr_print.css`, `app.css`), JavaScript Vanilla moderno |
| **Gestión de Estáticos** | WhiteNoise con compresión Brotli/Gzip |
| **Pasarela de Pagos** | Stripe API SDK (Stripe Connect Express, PaymentIntents) |
| **Almacenamiento Cloud** | Soporte opcional para AWS S3 o Cloudflare R2 (`django-storages[s3]`, `boto3`) |
| **Testing** | pytest, pytest-django, pytest-asyncio |
| **Contenedores** | Docker & Docker Compose |

---

## 📂 Estructura del Proyecto

```text
ResstaurantPayment/
├── apps/
│   ├── restaurants/          # NÚCLEO: Modelos de restaurante, mesas, comandas, platillos,
│   │                         # vistas POS, flujo de comensal, WebSockets y generación QR.
│   ├── billing/              # Facturación, Stripe Connect, servicios de pago y webhooks.
│   ├── core/                 # Landing page principal, vistas base y health check.
│   ├── ai_chat/              # [PREPARADO] Asistente de IA con Pydantic-AI y streaming WS.
│   ├── docs/                 # [PREPARADO] Portal de documentación del producto y ayuda.
│   └── legal/                # [PREPARADO] Páginas legales (Términos, Privacidad, Cookies).
├── config/
│   ├── settings/
│   │   ├── base.py           # Configuración transversal, apps instaladas, middleware.
│   │   ├── dev.py            # Configuración para entorno de desarrollo local.
│   │   ├── prod.py           # Configuración con directivas estrictas de seguridad.
│   │   └── test.py           # Configuración optimizada para ejecución rápida de tests.
│   ├── asgi.py               # Enrutador ASGI (HTTP + WebSockets con Channels).
│   ├── urls.py               # Enrutamiento global de la plataforma.
│   └── wsgi.py               # Entrada estándar WSGI.
├── static/
│   ├── css/                  # Estilos: guest.css, qr_print.css, app.css.
│   └── js/                   # Scripts interactivos: guest.js, home.js, app.js.
├── templates/
│   ├── restaurants/          # Plantillas del comensal (/guest/) y del POS (/dashboard/).
│   ├── partials/             # Componentes HTMX reutilizables (mensajes, modales).
│   ├── core/                 # Plantilla de la página de aterrizaje (home.html).
│   └── base.html             # Shell HTML principal.
├── requirements/
│   ├── base.txt              # Dependencias fundamentales del sistema.
│   └── dev.txt               # Herramientas de desarrollo y testing.
├── docker-compose.yml        # Orquestación de desarrollo (Postgres, Redis, Web, Celery).
├── docker-compose.prod.yml   # Orquestación lista para producción.
├── Dockerfile                # Imagen base con Python y dependencias de sistema.
└── manage.py                 # CLI de gestión Django.
```

---

## 💻 Requisitos Previos

- **Python 3.12 o superior** instalado en el sistema.
- **Git** para control de versiones.
- **Docker y Docker Compose** *(opcional, pero recomendado si se desea utilizar PostgreSQL y Redis localmente)*.
- **Cuenta de Stripe** (con modo de prueba activado) para pruebas de cobro real o simulado.

---

## 🚀 Guía de Instalación y Setup

### Opción A: Instalación Local con Entorno Virtual

Esta opción permite iniciar el proyecto de forma inmediata usando **SQLite** (sin necesidad de levantar bases de datos externas):

1. **Clonar el repositorio:**
   ```bash
   git clone git@github.com:AngelDann/restaurant_payer.git
   cd restaurant_payer
   ```

2. **Crear y activar el entorno virtual:**
   - En Windows (PowerShell):
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - En Linux / macOS:
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

3. **Instalar dependencias del proyecto:**
   ```bash
   pip install -r requirements/dev.txt
   ```

4. **Configurar las variables de entorno:**
   Copia el archivo `.env.example` como `.env`:
   ```bash
   # En Windows:
   copy .env.example .env

   # En Linux / macOS:
   cp .env.example .env
   ```
   > 💡 **Tip:** Para utilizar **SQLite** automáticamente en local, asegúrate de dejar la variable `POSTGRES_HOST=` vacía en tu archivo `.env`.

5. **Aplicar las migraciones de la base de datos:**
   ```bash
   python manage.py migrate
   ```

6. **Crear un superusuario administrador:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Iniciar el servidor de desarrollo:**
   ```bash
   python manage.py runserver
   ```
   Abre tu navegador en `http://127.0.0.1:8000/`.

---

### Opción B: Despliegue con Docker Compose

Si prefieres contar con la arquitectura completa (PostgreSQL 16, Redis 7, worker de Celery y Daphne):

1. **Configurar el entorno:**
   ```bash
   copy .env.example .env
   ```
   *(Asegúrate de que `POSTGRES_HOST=db` y `REDIS_URL=redis://redis:6379` estén definidos en `.env`)*.

2. **Construir y levantar los contenedores:**
   ```bash
   docker compose up --build
   ```

3. **Ejecutar migraciones en el contenedor:**
   ```bash
   docker compose exec web python manage.py migrate
   ```

4. **Crear superusuario:**
   ```bash
   docker compose exec web python manage.py createsuperuser
   ```

---

## ⚙️ Variables de Entorno (`.env`)

A continuación se describen las variables principales disponibles en `.env.example`:

| Variable | Descripción | Valor por Defecto / Ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave secreta criptográfica de Django. | *Modificar en producción* |
| `DEBUG` | Activa/desactiva modo debug (`1` o `0`). | `1` en dev |
| `ALLOWED_HOSTS` | Hosts permitidos separados por comas. | `127.0.0.1,localhost,web` |
| `POSTGRES_HOST` | Host de PostgreSQL. **Si se deja vacío, usa SQLite.** | `db` (o vacío para SQLite) |
| `POSTGRES_DB` | Nombre de la base de datos PostgreSQL. | `landing_page_creator` |
| `POSTGRES_USER` | Usuario de PostgreSQL. | `postgres` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL. | `postgres` |
| `POSTGRES_PORT` | Puerto de conexión a PostgreSQL. | `5432` |
| `REDIS_URL` | URL de conexión al servidor Redis. | `redis://redis:6379` |
| `STRIPE_PUBLIC_KEY` | Clave pública de Stripe (`pk_test_...`). | Requerido para pagos |
| `STRIPE_SECRET_KEY` | Clave secreta de Stripe (`sk_test_...`). | Requerido para Stripe Connect |
| `STRIPE_WEBHOOK_SECRET` | Secreto para validar webhooks de Stripe (`whsec_...`). | Opcional en dev local |
| `OPENAI_API_KEY` | Clave de API de OpenAI para el módulo `ai_chat`. | Opcional (módulo inactivo) |
| `USE_S3` | Habilitar almacenamiento en AWS S3 o Cloudflare R2 (`1` o `0`). | `0` |

---

## 🧪 Ejecución de Pruebas

El proyecto cuenta con un entorno de pruebas configurado con `pytest`, utilizando SQLite en memoria y un Channel Layer aislado:

```bash
pytest
```

Para ejecutar pruebas con detalle y cobertura de un módulo en particular:
```bash
pytest apps/restaurants/tests/
pytest apps/billing/tests/
```

---

## ⚠️ Advertencias y Notas Especiales

> [!NOTE]
> ### 1. Módulo de Inteligencia Artificial (`apps/ai_chat`) — En Espera / No Integrado
> Dentro del directorio `apps/ai_chat/` existe una arquitectura completa basada en `pydantic-ai[openai]`, con runtime de agentes, gestión de dependencias y streaming por WebSockets. **Actualmente este módulo NO está conectado al flujo principal de restaurantes ni al comensal.** Permanece en el repositorio como base tecnológica preparada para futuras capacidades (como recomendaciones de platillos por IA o asistente de comandas), pero no interfiere en la operativa diaria del cobro en mesa.

> [!NOTE]
> ### 2. Módulos de Documentación (`apps/docs`) y Legal (`apps/legal`)
> Las aplicaciones `apps/docs` y `apps/legal` ya se encuentran estructuradas, registradas en `INSTALLED_APPS` y enlazadas en el enrutador global (`/docs/` y `/legal/`). Actualmente contienen respuestas iniciales (placeholders) listas para incorporar los textos oficiales de Términos del Servicio, Política de Privacidad, Protección de Datos y Centro de Ayuda al Cliente.

> [!IMPORTANT]
> ### 3. Pagos con Stripe Connect y Comisiones
> - Para que un restaurante pueda aceptar pagos mediante el flujo de comensal, debe haber configurado sus credenciales de Stripe y completado el proceso de onboarding (`stripe_onboarding_completed=True`).
> - Si las variables `STRIPE_SECRET_KEY` o `STRIPE_PUBLIC_KEY` no están presentes en `.env`, el sistema arroja una excepción controlada (`StripeGatewayError`) sin colapsar el sistema.

> [!TIP]
> ### 4. WebSockets y Servidor ASGI (Daphne)
> Para que las actualizaciones en tiempo real (como el refresco del estado de las mesas cuando un cliente paga o se agregan platillos) funcionen correctamente en desarrollo y producción, la aplicación debe ser servida por un servidor ASGI compatible con Channels (**Daphne**). Al ejecutar `python manage.py runserver`, Daphne asume el control del servidor automáticamente gracias a la configuración de `channels`.

> [!WARNING]
> ### 5. Entornos Windows / OneDrive / Antivirus
> En sistemas operativos Windows donde el directorio del proyecto se encuentre alojado dentro de una carpeta sincronizada por **OneDrive** o con un software antivirus de escaneo en tiempo real, la ejecución de `pip install` dentro de `.venv` puede generar errores de tipo `WinError 32: El proceso no tiene acceso al archivo porque está siendo utilizado por otro proceso`. Si esto ocurre, se recomienda crear el entorno virtual `.venv` fuera de la ruta sincronizada o excluir la carpeta `.venv` del antivirus.
