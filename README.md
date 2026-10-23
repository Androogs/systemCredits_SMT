# Desarrollo Créditos

Plataforma de financiación de créditos con **frontend en React + TypeScript + Vite** y
**backend en Python + FastAPI**. Incluye el módulo de originación **SOCIP**
(dashboard, solicitudes, simulación y detalle) integrado en la misma SPA.

## Requisitos previos

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+ (probado con PostgreSQL 18)

## Estructura del proyecto

### Visión general

```text
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND  React + TypeScript + Vite (SPA, Feature-Sliced)  │
│  pages → widgets → features → entities → shared             │
│  Cliente HTTP: features/*/api + fetch (timeout, reintentos) │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/JSON  /api/*
        dev: proxy Vite ───┴──► API_PROXY_TARGET (:8001)
        prod: VITE_API_URL (absoluta) o mismo origen
┌──────────────────────────▼──────────────────────────────────┐
│  BACKEND  FastAPI (backend.main:app, todo bajo /api)        │
│  middlewares: RateLimit + CORS + manejadores de error       │
│                                                             │
│  routes (HTTP) → services (negocio) → repositories → ORM    │
│                                                             │
│  Motor de decisión (services, puro):                        │
│  evaluacion_service (orquesta)                              │
│    → datacredito (HDC+/Valor Ingreso o mock/archivos)       │
│    → parsers (raw JSON → modelos normalizados)              │
│    → motor_decision_service: filtros → ingreso → perfiles   │
│      → matriz ocupación → capacidad → decisión binaria      │
│                                                             │
│  Persistencia: SQLAlchemy → PostgreSQL (o SQLite en demo)   │
└─────────────────────────────────────────────────────────────┘
```

### Backend (`backend/`)

| Directorio / archivo | Responsabilidad |
|---|---|
| `main.py` | `crear_app()`: middlewares, manejadores, routers bajo `/api` |
| `config.py` | Settings Pydantic: `.env` — BD, Experian (`HDC_*`, `INCOME_*`, `OKTA_*`), SMMLV, CORS, rate limit, resiliencia, captura |
| **routes/** | Solo HTTP: validan request, llaman services, devuelven response |
| `health_routes.py` | `GET /api/health`, `GET /api/` |
| `auth_routes.py` | `POST /api/auth/login` |
| `motor_routes.py` | `POST /evaluar`, `POST /ingreso`, `GET /escenarios`, `POST /evaluar-con-archivos` (subir JSON HDC/VI) |
| `solicitud_routes.py` | CRUD + ciclo: `POST /solicitudes`, `GET /solicitudes`, `GET /{id}`, `POST /{id}/evaluar`, `GET /{id}/ofertas`, `POST /ofertas/seleccionar`, `PUT /datos-formalizacion`, `POST /otp`, `POST /otp/verificar`, `POST /desembolso`, `POST /{id}/cancelar` (motivo obligatorio; 409 si desembolsada) |
| `auditoria_routes.py` | `GET /auditoria`, `GET /auditoria/{id}` — trazabilidad completa |
| `parametros_routes.py` | `GET/PUT /parametros`, `POST /parametros/reset` |
| `catalogo_routes.py` | `GET /productos`, `GET /bancos` |
| `evidencia_routes.py` | `POST /sesiones-captura`, `GET /captura/{token}`, `POST /captura/{token}/evidencias` (multipart), `GET /evidencias/{id}/contenido` |
| `dependencies.py` | Inyección de repositorios/sesión DB |
| **services/** | Lógica de negocio pura (sin HTTP) |
| `evaluacion_service.py` | **Orquestador**: recupera/crea solicitud, consulta Experian o mock, valida identidad, llama motor, persiste evaluación + auditoría |
| `motor_decision_service.py` | **Pipeline del motor**: score → filtros duros → ingreso final → perfiles → matriz por ocupación → capacidad → decisión. `causales_traza` separa trazabilidad de causales que deciden |
| `reglas_filtros_duros.py` | Causales R1–R23: fallecido, embargos, mora, castigos, cancelaciones por mal hábito (R3), edad, documento |
| `reglas_ingreso.py` | Precedencia de ingreso final: Valor Ingreso > Quanto medio > declarado |
| `reglas_perfil.py` | Perfiles score (escaleras EP/IF) e ingreso (ALTO/MEDIO/BAJO/GRIS), continuidad por contrato, matriz `cruzar_perfiles_*` por ocupación, exclusión 0/4 |
| `valor_ingreso_service.py` | **Cálculos derivados de `resultado_pagos`**: línea de tiempo unificada multi-aportante, continuidad calendario, mediana/promedio/desviación/pendiente/tendencia, indicadores agregados, `respuesta_desde_cotizantes` (BD → modelo) |
| `capacidad_pago_service.py` | Endeudamiento, gastos personales por banda SMMLV, capacidad de pago, cupo/cuota sugeridos, causal E9 |
| `elegibilidad_service.py` | Reglas de aliados/productos → ofertas |
| `solicitud_service.py` | Ciclo de vida de la solicitud (crear, consultar, formalización, cancelación, consentimiento Habeas Data) |
| `otp_service.py` | OTP para firma de pagaré; al verificar dispara el paquete legal |
| `documento_service.py` | Paquete de legalización: 8 documentos DOCX (5 por MERGEFIELD, solicitud de crédito por tokens `{{CAMPO}}`, compromiso por reemplazo literal, asegurabilidad generada con python-docx), todos sellados con `uuid_firma` |
| `desembolso_service.py` | Registro del desembolso |
| `evidencia_service.py` | Sesiones de captura, evidencias en `EVIDENCIAS_DIR` |
| `validaciones_identidad.py` | Cruce identidad solicitud vs. buró |
| `finanzas.py` | Anualidad/cuota |
| `letras.py`, `mapeos_db.py`, `notificacion_service.py`, `autenticacion_service.py`, `seguro_service.py`, `health_service.py`, `textos_legales.py` | Soporte: letras/conversión, mapeo ORM↔DTO, notificaciones, auth, seguros, health, textos legales versionados |
| `motor_parametros.py` | Carga/validación de `parametros.json` → `MotorParametros` |
| `motor_exceptions.py` | Excepciones de dominio |
| **repositories/** | Acceso a datos (SQLAlchemy), sin lógica de negocio |
| `solicitud_repository.py`, `evaluacion_repository.py`, `auditoria_repository.py`, `evidencia_repository.py`, `health_repository.py` | CRUD de cada agregado |
| **models/** | DTOs Pydantic + enums de dominio |
| `enums.py` | `Decision` (interna), `DecisionFinal` (binaria), `PerfilScore`, `PerfilIngreso`, `Ocupacion`, `TipoContrato`, `Causal` (catálogo completo + tipo) |
| `buro_models.py` | Modelos normalizados de Experian: `RespuestaHDC`, `RespuestaValorIngreso`, `Aportante`, `PeriodoPago`, `Indicadores`, `ResumenGeneralIngresos`, cuentas, alertas |
| `motor_models.py` | `Solicitud`, `ResultadoMotor`, `PasoTraza`, responses API |
| `solicitud_models.py`, `auth_models.py`, `health_model.py` | DTOs por módulo |
| **db_models/** | ORM SQLAlchemy |
| `models.py` | `cliente`, `solicitud_credito`, `datos_laborales`, `solicitud_contacto_vivienda`, `otp`, `cotizante`, `cotizante_ingreso_mensual`, `criterio_evaluacion`, `evaluacion_credito`, `evaluacion_detalle`, `solicitud_causal`, `capacidad_pago`, `aliado_*`, `oferta_credito` (con `fecha_vigencia`), `banco`, `cuenta_bancaria`, `aseguradora`, `seguro_producto`, `producto_vehiculo` (incluye desglose de hoja de negocio), `credito_financiacion`, `desembolso`, `consentimiento_habeas` |
| `auditoria_models.py` | `motor_evaluacion_auditoria` (request + resultado completo) |
| `evidencia_models.py` | `sesion_captura`, `documento_evidencia` |
| `session.py`, `base.py` | Engine, SessionLocal, Base declarativo |
| **integrations/datacredito/** | Experian |
| `hdc_client.py`, `income_client.py` | Clientes REST HDC+ y Valor Ingreso |
| `auth.py` | OAuth2/Okta tokens |
| `resiliencia.py` | Timeout, reintentos con backoff, circuit breaker por servicio |
| `mock_buro.py` | Escenarios mock para `ENVIRONMENT=demo` |
| `parsers/hdc_parser.py`, `parsers/income_parser.py` | Raw JSON → modelos normalizados (agregados recalculados, no copiados) |
| **middlewares/** | `rate_limit_middleware.py`, `error_middleware.py` |
| **database/** | `schema.sql` (DDL canónico SUMOTO), `insert.sql` (catálogos), `seed_demo.py` (tablas + seed idempotente, sirve con SQLite) |
| **utils/** | `fechas.py`, `lectura_reportes.py`, `loggers.py` |

### Motor de decisión — flujo interno

```text
POST /api/solicitudes/{id}/evaluar  o  /api/motor/evaluar
  └─ evaluacion_service
       ├─ HDC+ / Valor Ingreso (en línea | archivos | escenario_mock)
       ├─ parsers → RespuestaHDC / RespuestaValorIngreso (normalizados)
       └─ motor_decision_service.evaluar()
            1. filtros_duros    → causales de rechazo (R*/RC*/E*)
            2. ingreso_final    → Valor Ingreso > Quanto > declarado
            3. perfil_score     → A/B/C/D (EP: 750/680/600/500, IF: 770/700/620/520)
            4. perfil_ingreso   → ALTO/MEDIO/BAJO/GRIS (+continuidad/cámara)
            5. matriz_decision  → por ocupación (Empleado+BAJO aprueba con
                                  causal traza; Pensionado/FFMM/Ind+BAJO rechaza)
            6. capacidad_pago   → endeudamiento, capacidad, cuota moto (E9…)
            └─ Decisión BINARIA (interna y pública): Aprobado solo sin
               causales que decidan; cualquier causal → Rechazado.
               'Estudio'/'Requiere Codeudor' solo existen en
               evaluaciones históricas (D185)
       └─ persistencia: evaluacion_credito + detalle + causales + auditoría
```

Parámetros vivos en `parametros.json` (editables por `PUT /api/parametros`):
umbrales de score, perfiles de ingreso por ocupación, continuidad
(`meses_cont_1/2`), años cámara (`anios_cam_1..4`), endeudamiento, SMMLV.

### Frontend (`frontend/src/`) — Feature-Sliced Design

| Capa | Contenido |
|---|---|
| `app/routing/` | `RutasAplicacion.tsx` — rutas protegidas bajo layout + públicas (`/login`, `/captura/:token`) |
| `app/styles/` | Tailwind base |
| **pages/** | `IniciarSesion`, `Resumen` (dashboard), `PanelAsesor`, `Originacion` (wizard), `Simulador`, `Solicitudes`, `DetalleSolicitud`, `Resultado`, `Clientes`, `Riesgo`, `Estados`, `Ajustes`, `CapturaMovil` (página pública del celular) |
| `widgets/app-shell/` | `BarraLateral` (sidebar único), `Encabezado`, `ContenedorPanel` — layout compartido |
| `features/credit-origination/` | Flujo SOCIP completo: `api/originacionApi.ts` (cliente HTTP: timeout 30s/120s evaluar, reintentos solo GET), `model/` (borrador, etapas, mapeos-api, schemas Zod), `schemas/` (validación por paso), `ui/` (pantallas del wizard: ValidacionInicial, CapturaCedula, CrearSolicitud, EvaluacionYResultado, ResultadoCredito, DatosClienteFormalizacion, EvidenciaYDatos, RevisionDatos, AutorizacionDatos, SeguimientoOriginacion) |
| `features/auth/` | Login (`autenticacionApi.ts`) |
| `features/settings/` | `EditorParametros.tsx` — edita `parametros.json` vía API |
| `entities/credit/` | Tipos/estado del crédito (`solicitudesPanel`), UI mínima (`InsigniaEstado`) |
| `shared/` | `lib/` (formatters, finanzas, sesión, toastBus, campoNumerico), `ui/` (UI kit: Boton, Alerta, CampoEntrada, CampoNumerico, Selector, Tarjeta, Toasts, Skeleton) |
| `env.ts` | `VITE_API_URL` validada con Zod; vacío = `/api` mismo origen |

> **Regla FSD:** una capa superior puede importar de capas inferiores, nunca al revés
> (`app → pages → widgets → features → entities → shared`). Esto evita dependencias
> circulares y facilita auditorías.

### Persistencia

- `backend/database/schema.sql` — DDL canónico (esquema SUMOTO); Alembic
  `0001_baseline` lo ejecuta (`alembic upgrade head`).
- `insert.sql` — catálogos + producto semilla; `seed_demo.py` lo aplica
  idempotente y crea tablas auxiliares (`rol`, `concesionario`, `aliado_concesionario`).
- `DATABASE_URL` soporta PostgreSQL (prod) y SQLite (demo/tests).
- Evidencias de captura en `EVIDENCIAS_DIR` (`uploads/`).

### Tests, scripts y docs

| Ruta | Contenido |
|---|---|
| `tests/unit/` | Motor puro: calculos, filtros BRD, parsers, motor, parámetros, perfil ingreso/continuidad, reglas perfil, rate limit, rechazo, resiliencia, elegibilidad, valor ingreso |
| `tests/integration/` | API con SQLite en memoria: `test_api.py` (escenarios mock con decisión+ causales esperadas), auth, documentos, evaluar_local, evidencias, experian en línea |
| `tests/conftest.py`, `tests/modelos.py` | Fixtures compartidas (motor, solicitud, HDC, VI, parámetros demo) |
| `scripts/` | `evaluar_local.py` (evaluar archivos JSON sin API), `probar_api.py`, `probar_hdc.py`, `probar_income.py` |
| `reportes/caso_revision/` | Reportes Experian de prueba (local, no versionado) |
| `docs/` | `manual_integracion_aliados.md`, `roles-y-alcance.md`, `openapi.{json,yaml}`, `motor_decision/` (BRD, reglas de negocio, parámetros, origen de cálculos, bitácora) |
| Raíz | `parametros.json`, `alembic.ini`, `Dockerfile`, `docker-compose`, `package.json` (husky+lint-staged), `.env.example` |

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

#### Usuarios de prueba (seed `insert.sql`)

El seed crea tres cuentas con rol distinto para recorrer el panel —
las claves son de desarrollo, cámbialas antes de exponer el ambiente:

| Correo | Clave | Rol y alcance |
|---|---|---|
| `admin@pacifico.co` | `Admin123!` | Admin: todo, con score y causales del motor |
| `asesor@pacifico.co` | `Asesor123!` | Asesor: opera sobre `SUMOTO SA PALMIRA`, solo ve lo radicado por su cédula, vista binaria |
| `aliado@pacifico.co` | `Aliado123!` | Aliado: solo lectura, solicitudes de su aliado |

Otros roles creados desde Ajustes → Usuarios:

- **concesionario** — administrador de UNA sede (vínculo
  `concesionario_usuario`): ve todas las solicitudes de su sede, filtra
  por asesor, radica a nombre de un asesor elegido y gestiona solo los
  asesores de su sede.
- **Asesor** — la cuenta (correo corporativo) es permanente; la persona
  puede cambiar. La solicitud guarda foto del radicador
  (`asesor_nombre`/`asesor_cedula`) y el alcance es por cédula +
  `persona_desde`: al cambiar el titular, las radicaciones del
  predecesor dejan de verse (historial en `asesor_historial`).

La sesión es JWT (`POST /api/auth/login` → `Authorization: Bearer`).
Fuera de `ENVIRONMENT=demo` el login exige `JWT_SECRETO` configurado
(ver `.env.example`: `JWT_TTL_HORAS`, `AUTH_MAX_INTENTOS`,
`AUTH_BLOQUEO_MINUTOS`, `AUTH_ROLES_PANEL`) y la documentación
interactiva (`/api-docs`, `/redoc`, `/api/openapi.json`) queda
deshabilitada.

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

#### OCR de la cédula (Tesseract)

Al subir la foto frontal de la cédula, el backend corre **Tesseract OCR**
(`backend/services/ocr_service.py`) sobre la imagen, extrae número de
documento, nombres, apellidos y fechas, y los compara contra los datos que
el asesor capturó en el paso 1 (que se envían al crear la sesión). Si algo
no coincide, el paso de **Revisión de Datos** muestra una **advertencia no
bloqueante**: el asesor decide si corrige o continúa. El resultado queda
expuesto en `GET /api/captura/{token}` y `GET /api/sesiones-captura/{id}`.

Se soportan las **dos versiones** de la cédula de ciudadanía colombiana:

- **Amarilla (antigua):** rótulo y valor en la misma línea.
- **Blanca (nueva, ~2020):** rótulos y valores en columnas separadas; el
  parser los empareja por posición. También tolera palabras que el OCR pega
  (`CARLOSMARIO`) y descarta fechas corruptas (`1091`).

El OCR es *best-effort*: si Tesseract no está disponible o la imagen es
ilegible, la subida de la evidencia **no falla**; simplemente no se emiten
advertencias.

Requisito: instalar el binario de **Tesseract** y tenerlo en el PATH, con el
paquete de idioma `spa`. En Windows:

```powershell
winget install UB-Mannheim.TesseractOCR   # marca "Spanish" al instalar
```

Las dependencias Python (`pytesseract`, `Pillow`) ya vienen en
`backend/requirements.txt`. Si Tesseract no está instalado, el backend
arranca igual y el OCR degrada sin advertencias.

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

## Ambiente de pruebas (staging)

Stack completo en un comando — PostgreSQL + API + frontend detrás de
nginx, todo por un solo puerto. `ENVIRONMENT=demo`: login demo y OTP
visible en pantalla (no se envían correos reales). DataCrédito consulta
el UAT si el `.env` trae credenciales `HDC_*`/`INCOME_*`; si están
vacías, cae a `mock_buro`.

```powershell
# 1. Crear el env de staging
copy .env.staging.example .env.staging   # editar las claves

# 2. Levantar el stack (el API corre `alembic upgrade head` al arrancar)
docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

# 3. Cargar datos de prueba (asesores, solicitudes, catálogos)
docker compose -f docker-compose.staging.yml --env-file .env.staging exec api python -m backend.database.seed_demo
```

Abrir `http://localhost:8080` — nginx sirve la SPA y reenvía `/api` al
backend por la red interna (mismo origen → sin CORS). La API y la BD no
quedan expuestas al host.

Notas del staging:

- El contenedor `api` lee `.env` **además** de `.env.staging` (credenciales
  Experian/SMTP se comparten con el dev local). Con credenciales UAT en
  `.env` la evaluación consulta DataCrédito real; sin ellas cae a
  `mock_buro`.
- **Cambiar `POSTGRES_*` exige recrear el volumen** — Postgres solo
  inicializa el usuario/clave la primera vez. Si se edita:
  `docker compose -f docker-compose.staging.yml --env-file .env.staging down -v`
  y volver a subir + seed (borra los datos de prueba).

**Compartirlo**: `cloudflared tunnel --url http://localhost:8080` da una
URL HTTPS gratis (necesaria para la cámara en CapturaMovil); para algo
permanente, el mismo compose en cualquier VM detrás de un dominio con TLS.

Ver también `ARQUITECTURA.md` para el despliegue objetivo en nube.

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