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
- **Resiliencia Experian** (todas opcionales, con defaults en `config.py`):
  `EXPERIAN_TIMEOUT_SEGUNDOS` (60s), `EXPERIAN_REINTENTOS` (2 reintentos extra
  con backoff exponencial solo ante fallos de red o HTTP 408/429/5xx),
  `EXPERIAN_ESPERA_REINTENTO_SEG` (1s base), `EXPERIAN_CIRCUITO_FALLOS` (5
  fallos consecutivos abren el circuito) y `EXPERIAN_CIRCUITO_ESPERA_SEG`
  (60s abierto, evita golpear Experian caído). Implementado en
  `backend/integrations/datacredito/resiliencia.py` con un circuit breaker por
  servicio (HDC+ y Valor Ingreso).
- **Frontend:** valida `VITE_API_URL` con Zod (`frontend/src/env.ts`).
  El cliente HTTP aplica timeout 30s (120s en `/evaluar`) y reintenta solo
  peticiones GET ante timeout o fallo de red.

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

Para desarrollo o demos sin PostgreSQL, `backend/database/seed_demo.py` crea las
tablas sobre la `DATABASE_URL` configurada (funciona también con SQLite),
agrega las tablas auxiliares no mapeadas por el ORM (`rol`, `concesionario`,
`aliado_concesionario`) y ejecuta `insert.sql` de forma idempotente:

```powershell
python -m backend.database.seed_demo
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

### Captura remota de evidencias (paso 3 del wizard)

El paso "Captura del Documento de Identidad" genera un enlace con token
(opcionalmente QR) para que el cliente suba desde su celular —sin
autenticarse— la cédula frontal/posterior y un video de prueba de vida
(rostro + cédula al lado, cámara frontal). La página pública es
`/captura/:token`; el token caduca en `CAPTURA_TTL_MINUTOS` (30 por
defecto) y solo autoriza esa sesión. Las evidencias se guardan en
`EVIDENCIAS_DIR` (storage local del MVP; la migración a S3 queda detrás
de `EvidenciaService`) y se enlazan a la solicitud cuando esta se crea
con el token (`sesion_captura` en `POST /api/solicitudes`).

Para probar desde un celular real, el navegador **exige HTTPS** para la
cámara (`getUserMedia` solo funciona en contexto seguro). La forma
recomendada es un túnel gratuito — no requiere cuenta:

```powershell
# 1. Backend (localhost basta; solo el proxy de Vite lo contacta)
.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001 --reload-dir backend

# 2. Frontend (sin --host; el túnel entra por localhost)
cd frontend
npm run dev

# 3. Túnel HTTPS público hacia el dev server
cloudflared tunnel --url http://localhost:5173
```

El túnel imprime una URL `https://<random>.trycloudflare.com`. **Abre esa
URL en el PC del asesor** — el QR del paso 3 se genera con el origen del
navegador, así el celular recibe el link HTTPS y la cámara funciona. Las
llamadas `/api` son relativas al mismo origen y el proxy de Vite las
reenvía al backend (`API_PROXY_TARGET` en `frontend/.env`), así el
celular nunca toca el backend directo ni hay temas de CORS.

Alternativa en la misma Wi-Fi (solo fotos — el video requiere HTTPS):
`npm run dev -- --host`, abrir la app por la IP LAN y ajustar
`VITE_API_URL`/`CORS_ORIGINS` a esa IP.

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

Frontend, desde `frontend/`:

```powershell
npx tsc --noEmit
npm run lint
npm test
npm run build
```

### E2E con navegador real (Playwright)

```powershell
cd frontend
npm run test:e2e
```

`playwright.config.ts` levanta todo automáticamente: siembra una SQLite
temporal con `seed_demo.py`, arranca FastAPI en `:8010` y Vite en `:5199`,
y corre los specs de `frontend/e2e/` en Chromium. El flujo cubre radicación
→ evaluación con `escenario_mock=aprobado` → detalle, oferta elegible,
resultado y dashboard. Los artefactos (`playwright-report/`, `test-results/`,
`e2e.db`) están ignorados en git.

## Despliegue

### Integración para aliados

El contrato REST actualmente implementado, los ejemplos de ciclo de solicitud y
las limitaciones de seguridad/capacidades están documentados en
[Manual de integración para aliados](docs/manual_integracion_aliados.md).
Revisar especialmente sus prerrequisitos de autenticación antes de exponer rutas
que contienen datos personales.

### Frontend (Cloudflare Pages)

Configura `VITE_API_URL` en **Settings → Environment variables** con la URL
pública del backend (ej. `https://tu-backend.onrender.com`). Si se deja vacía,
el frontend llama a `/api` del mismo origen — útil solo si el backend se sirve
detrás del mismo dominio.

### Backend (Docker — recomendado)

El `Dockerfile` de la raíz construye la imagen del backend; al arrancar aplica
`alembic upgrade head` y levanta uvicorn en `:8000` como usuario no-root.

```powershell
docker build -t creditos-api .
docker run --env-file .env -p 8000:8000 creditos-api
```

O el stack completo local (Postgres + API, con volúmenes para la BD y las
evidencias de `uploads/`):

```powershell
docker compose up --build
```

La imagen es la unidad de despliegue para AWS App Runner/ECS, Render,
Railway o Fly.io.

### Backend (servicio Python, sin Docker)

FastAPI no se puede publicar como contenido estático. Publícalo como servicio
Python con `backend/requirements.txt` como dependencias:

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

## Trabajo en equipo (Git)

Regla de oro: **nunca hacer `pull` con cambios sin commitear**. Commitear
primero, bajar después.

### Bajar cambios del remoto

```powershell
git pull --rebase origin main
```

Si el pull dice que hay cambios locales que impiden continuar:

```powershell
git stash push -u -m "wip"     # guarda el trabajo sin commitear
git pull --rebase origin main
git stash pop                  # restaura el trabajo encima
```

### Si aparecen conflictos al hacer `stash pop` o `rebase`

Git marca las zonas en conflicto dentro de los archivos:

```text
<<<<<<< Updated upstream     ← lo que llegó del remoto
(código de la versión remota)
=======                      ← separador
(código de tu versión local)
>>>>>>> Stashed changes      ← tu trabajo guardado
```

Para resolverlos:

1. Abrir cada archivo marcado (VS Code los muestra con botones
   *Accept Current / Accept Incoming / Accept Both*).
2. Elegir o combinar el código correcto y borrar los marcadores
   `<<<<<<<`, `=======`, `>>>>>>>`.
3. Verificar que no queden marcadores:

   ```powershell
   git diff --check          # sin salida = limpio
   ```
4. Verificar que el proyecto siga compilando:

   ```powershell
   cd frontend
   npx tsc --noEmit
   npm run lint
   ```

5. Marcar los archivos resueltos y continuar:

   ```powershell
   git add -A
   git rebase --continue     # si estaba en medio de un rebase
   ```

### Convención

- Antes de empezar a trabajar: `git pull --rebase origin main`.
- Antes de subir: commitear todo y `git push origin main`.
- Cambios grandes: rama propia (`git checkout -b feature/...`) y merge por
  Pull Request en GitHub.