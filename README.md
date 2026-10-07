# Desarrollo Créditos

Plataforma de financiación de créditos con **frontend en React + TypeScript + Vite** y
**backend en Python + FastAPI**. Incluye el módulo de originación **SOCIP**
(dashboard, solicitudes, simulación y detalle) integrado en la misma SPA.

## Requisitos previos

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (probado con PostgreSQL 18)

## Estructura del proyecto

```text
.env.example
.gitignore
alembic.ini
alembic/
package.json
package-lock.json
.husky/
README.md

parametros.json               # Parámetros del motor (score, endeudamiento, SMMLV)
tests/                        # Suite pytest del motor (unit/ + integration/)
ejemplos/                     # Payloads de ejemplo (solicitud_ejemplo.json)
reportes/                     # Reportes Experian de prueba (CLI evaluar_local)
scripts/                      # evaluar_local.py, probar_api.py, probar_hdc.py…
docs/motor_decision/          # Documentación funcional del motor (BRD/PPT v4)

backend/                      # API FastAPI + motor de decisión integrado
  main.py                     # App FastAPI (CORS, /api, lifespan)
  config.py                   # Settings (.env): BD, Experian, SMMLV, CORS
  requirements.txt
  database/
    schema.sql                # DDL canónico del esquema SUMOTO
    insert.sql                # Catálogos + producto semilla
  routes/                     # solicitudes, motor, parametros, auditoria, health
  services/                   # motor, evaluación, elegibilidad, finanzas, reglas
  repositories/               # acceso a solicitud/evaluación/auditoría
  models/                     # DTOs Pydantic + enums de dominio
  db_models/                  # ORM SQLAlchemy (models, auditoria, session)
  integrations/datacredito/   # HDC+, Valor Ingreso, parsers, mock_buro
  middlewares/
  utils/

frontend/                     # SPA React + Vite (Feature-Sliced Design)
  .env.example
  eslint.config.js
  .prettierrc.json
  .prettierignore
  package.json
  vite.config.ts
  postcss.config.js
  tailwind.config.js
  tsconfig*.json
  index.html
  public/
    brand/                    # Única fuente de logos (iconográfico + Pacífico)
  src/
    app/                      # Configuración global
      routing/                # React Router (público/protegido)
      styles/                 # Estilos globales, Tailwind base
    pages/                    # Vistas (Login, Dashboard, Clientes, etc.)
    widgets/                  # Composición de features
      app-shell/              # Layout, Sidebar único, Header
    features/                 # Acciones de usuario
      credit-origination/     # Flujo SOCIP: dashboard, solicitudes, simulación
    entities/                 # Modelos de negocio
      credit/
        model/                # Tipos y estado (LoanStatus, InterestRate)
        ui/                   # Componentes mínimos (CreditRow, StatusBadge)
    shared/                   # Reutilizable sin lógica de negocio
      api/                    # Cliente HTTP, interceptores
      lib/                    # Formatters (currency, dates, interés)
      styles/
      ui/                     # UI Kit (Button, Input, Modal, Table…)
```

> **Regla FSD:** una capa superior puede importar de capas inferiores, nunca al revés
> (`app → pages → widgets → features → entities → shared`). Esto evita dependencias
> circulares y facilita auditorías.

## Variables de entorno

Copia los archivos de ejemplo y ajusta los valores locales:

```powershell
Copy-Item .env.example .env
Copy-Item frontend\.env.example frontend\.env
```

Edita `.env` en la raíz con tu contraseña de PostgreSQL:

```text
DATABASE_URL=postgresql+psycopg://postgres:TU_PASSWORD@localhost:5432/DB
CORS_ORIGINS=http://localhost:5173
APP_TITLE=Creditos API
APP_VERSION=1.0.0
ENVIRONMENT=demo
SMMLV=1750905
DB_CREAR_TABLAS=false
```

- **Backend:** valida todas las variables con Pydantic Settings
  (`backend/config.py`), incluidas las credenciales de DataCrédito Experian
  (`HDC_*`, `INCOME_*`, `OKTA_*` — ver `.env.example`). En `ENVIRONMENT=demo`
  el motor corre contra escenarios mock sin consultar Experian.
- **Frontend:** valida `VITE_API_URL` con Zod (`frontend/src/env.ts`).

## Calidad de código

Desde la raíz (una vez):

```powershell
npm install
```

Esto instala **Husky**. En cada commit, `lint-staged` ejecuta ESLint y Prettier
sobre los archivos de `frontend`.

Desde `frontend`:

```powershell
npm run lint
npm run format
```

## Desarrollo local

### Backend

Desde la raíz del proyecto:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Asegúrate de que la base de datos exista:

```sql
CREATE DATABASE "DB";
```

Aplica las migraciones:

```powershell
alembic upgrade head
```

Carga datos iniciales (solo la primera vez):

```powershell
& "C:\Program Files\PostgreSQL\<versión>\bin\psql.exe" -U postgres -h localhost -d DB -f backend\database\insert.sql
```

Inicia el backend:

```powershell
python -m uvicorn backend.main:app --reload
```

### Frontend

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

- Frontend: <http://localhost:5173>
- Docs interactivas API: <http://localhost:8000/api-docs> (ruta personalizada)

Las peticiones a `/api` se redirigen al backend durante el desarrollo.
`GET /api/health` funciona sin PostgreSQL; el resto de rutas requieren
`DATABASE_URL` válida.

## Navegación principal

El **sidebar único** (en `widgets/app-shell`) agrupa todas las secciones:

- **Dashboard**
- **Originación (SOCIP):** solicitudes, simulación y detalle
- **Clientes**
- **Reportes**
- **Configuración**

No hay barras laterales duplicadas: el flujo SOCIP reutiliza el mismo
`DashboardLayout`.

## Recursos de marca

Todos los logos viven en `frontend/public/brand/`:

```text
logo-iconografico.svg
pacifico-azules.png
pacifico-blancos.png
```

`dist/` es la salida generada por `npm run build` (Vite copia `public/` allí
automáticamente). No se edita a mano; se regenera.

## Pruebas

Desde la raíz, con el venv activo:

```powershell
python -m pytest tests -q
```

La suite cubre el motor de decisión completo (unit) y los endpoints `/api`
contra SQLite en memoria (integration).

## Despliegue

### Frontend (Cloudflare Pages)

Configura `VITE_API_URL` en **Settings → Environment variables** con la URL
pública del backend (ej. `https://tu-backend.onrender.com`). Sin esta variable,
el build usa `http://localhost:8000` y no funcionará en producción.

### Backend (Render / Railway / Fly.io)

FastAPI no se puede publicar como contenido estático. Publícalo como servicio
Python:

```text
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

Configura `CORS_ORIGINS` con el dominio de Pages
(p. ej. `https://desarrollo-creditos.pages.dev`). Health check:
`https://TU-BACKEND/api/health`.

## Migraciones de base de datos

La revisión `0001_baseline` ejecuta `backend/database/schema.sql`. Para crear
una nueva migración tras cambiar los modelos:

```powershell
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head
```

Comandos útiles desde la raíz (venv activo):

```powershell
alembic current   # revisión aplicada
alembic history   # revisiones disponibles
```

Los datos iniciales se cargan aparte con `backend/database/insert.sql`.

## Convenciones de código

- **Rutas:** `kebab-case` para carpetas (`credit-origination`, `app-shell`).
- **Componentes:** `PascalCase` (`DashboardLayout.tsx`).
- **Imports:** siempre con alias `@/…` apuntando a `src/` (configurado en
  `tsconfig.app.json` y `vite.config.ts`).
- **Estilos:** Tailwind con la paleta Pacífico centralizada en
  `tailwind.config.js` (no usar colores hardcodeados).
- **Sin código muerto:** antes de mergear, verificar que no queden archivos
  sueltos en `features/*/ui/` que no estén importados desde `pages/` o
  `widgets/`.