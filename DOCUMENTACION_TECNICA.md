# Documentación técnica — Plataforma de originación de crédito

Inversiones Pacífico / SUMOTO. Inventario completo del sistema **tal como
existe en el repositorio**: stack, estructura, comunicación, datos, seguridad,
despliegue y mantenimiento. Pensado para revisión arquitectónica — cada afirmación
es verificable en el código.

> Complementa a `ARQUITECTURA.md` (visión por capas + brechas) y `README.md`
> (cómo correrlo).

---

## 1 · Stack tecnológico (versiones reales)

### Frontend

| Pieza | Versión | Rol |
|---|---|---|
| React | 19.2 | UI declarativa (SPA) |
| TypeScript | ~6.0 | Tipado estricto end-to-end |
| Vite | 8.3 | Dev server + build (rolldown-vite) |
| React Router | 6.27 | Enrutado de 13 páginas |
| TanStack Query | 5.104 | Estado de servidor: fetch/cache/refetch |
| Zod | 3.25 | Validación de esquemas en cliente |
| Recharts | 2.13 | Tabla de amortización / gráficos del simulador |
| qrcode | 1.5 | QR del link de captura móvil |
| lucide-react | 0.454 | Iconografía |
| Tailwind CSS | 3.4 | Utilidades de estilo (+ CSS por componente) |
| Vitest | 5.0 | Tests unitarios (56 tests, 7 archivos) |
| Playwright | 1.63 | E2E (`e2e/`, fuera de Vitest) |
| ESLint 9 + Prettier 3 | — | `eslint --fix` + `prettier` vía lint-staged |

### Backend

| Pieza | Versión | Rol |
|---|---|---|
| Python | 3.14 | Runtime |
| FastAPI | 0.141–0.143 | Framework API (OpenAPI en `/api-docs`) |
| Uvicorn `[standard]` | 0.53+ | ASGI server |
| SQLAlchemy | 2.0–2.1 | ORM (5 repositorios, único punto de SQL) |
| psycopg `[binary]` | 3.3 | Driver PostgreSQL (v3) |
| Alembic | 1.20 | Migraciones (7 versiones aplicadas) |
| Pydantic + pydantic-settings | 2.x | Modelos de request/response + config por env |
| httpx | 0.28 | Cliente HTTP a DataCrédito |
| python-multipart | — | Upload de evidencias (`UploadFile`) |
| docx-mailmerge + python-docx | — | Paquete legal (MERGEFIELDs en plantillas DOCX) |
| num2words | — | Montos en letras en documentos legales |
| pypdf | — | Lectura de reportes Experian en PDF |
| pytest 8 + respx | — | Suite: SQLite en memoria + mocks HTTP de Experian |

### Infraestructura / herramientas

| Herramienta | Uso |
|---|---|
| Docker + Docker Compose | Imagen única del API; stacks `docker-compose.yml` (dev) y `docker-compose.staging.yml` (QA completo) |
| PostgreSQL 16 (alpine) | BD real; contenedor propio o instancia local |
| SQLite | Tests y demo sin dependencias |
| nginx 1.27 | En staging: sirve la SPA y hace reverse-proxy `/api` |
| cloudflared | Túnel HTTPS gratis para compartir el ambiente y probar la cámara del celular |
| GitHub Actions | CI: 3 jobs (backend, frontend, docker build) |

---

## 2 · Estructura del monorepo

```
Desarrollo Creditos/
├── backend/                    # API FastAPI (monolito modular)
│   ├── main.py                 # app factory, lifespan, middlewares, routers
│   ├── config.py               # Settings (pydantic-settings, .env, demo/prod)
│   ├── routes/                 # 8 routers → 31 endpoints bajo /api
│   ├── services/               # 24 servicios/módulos de dominio
│   ├── repositories/           # 5 repositorios — único SQL
│   ├── db_models/              # ORM (models, session, evidencia, auditoria)
│   ├── models/                 # Pydantic: contratos de request/response
│   ├── middlewares/            # rate limit + errores de dominio
│   ├── integrations/datacredito/  # auth, hdc_client, income_client,
│   │                            # parsers/, resiliencia, mock_buro
│   ├── documentos/plantillas/  # 7 plantillas DOCX del paquete legal (8 documentos generados)
│   ├── database/               # schema.sql (42 CREATE TABLE), seed_demo.py
│   └── utils/                  # fechas, lectura de reportes, loggers
├── alembic/versions/           # 0001…0010 migraciones
├── scripts/generar_plantilla_solicitud.py  # transforma el formato real
│                                # del doc 7 a tokens {{CAMPO}} (una vez)
├── frontend/
│   ├── src/pages/              # 13 pantallas
│   ├── src/features/           # credit-origination · auth · settings
│   ├── src/entities/credit/    # modelos de dominio + tests
│   ├── src/widgets/app-shell/  # layout/sidebar único
│   ├── src/shared/             # lib (formato, campos) + ui (componentes)
│   ├── nginx.conf              # proxy /api + SPA fallback (staging)
│   └── Dockerfile              # build Vite → nginx
├── tests/                      # pytest: unit/ + integration/ (22 archivos test_*)
├── parametros.json             # umbrales del motor (se crea con defaults)
├── docker-compose.yml          # dev: API contra Postgres local
├── docker-compose.staging.yml  # QA: web+api+db en un stack
├── .env.example / .env.staging.example
└── .github/workflows/ci.yml
```

---

## 3 · Frontend — arquitectura (Feature-Sliced Design)

`src/` se organiza por capas FSD, no por tipo de archivo:

| Capa | Contenido | Regla |
|---|---|---|
| `pages/` | 13 pantallas: Originacion (wizard 5 pasos), Simulador, Solicitudes, DetalleSolicitud, Resultado, PanelAsesor, CapturaMovil (pública), IniciarSesion, Estados, Clientes, Resumen, Riesgo, Ajustes | Composición de features/widgets; sin lógica de dominio |
| `features/credit-origination/` | `api/` cliente REST · `model/` reglas y mapeos (`resultado-evaluacion.ts`, `datos-formalizacion.ts`, `borrador.ts`, `etapas-originacion.ts`, `concesionarios.ts`) · `schemas/` validación Zod · `ui/` 10 componentes del wizard | El núcleo del negocio en el front |
| `features/auth/` + `features/settings/` | login, parámetros del motor | |
| `entities/credit/` | tipos de dominio compartidos | |
| `widgets/app-shell/` | layout + sidebar único de la app | |
| `shared/` | `lib/` (`campoNumerico`, formatos COP/fechas) · `ui/` (botones, inputs base) | Lo reusable sin dominio |

**Estado**: TanStack Query maneja el estado de servidor (fetch, caché,
invalidación tras mutaciones). Estado local de formularios con hooks;
borrador de originación en `model/borrador.ts`.

**Control de rol — solo visual**: el mismo endpoint devuelve todo; el
asesor no ve score/causales porque la UI no los renderiza
(`DetalleSolicitud` ramifica por `rol`). No hay guards en el API todavía
(ver §8 brechas).

---

## 4 · Backend — capas internas (monolito modular)

```
routes/ (HTTP, validación Pydantic de entrada/salida)
   │  — 8 routers, 31 endpoints
   ▼
services/ (orquestación + reglas de negocio; reciben Session por Depends)
   │  — 24 servicios/módulos
   ▼
repositories/ (ÚNICO punto de SQL — usan flush(), nunca commit())
   │  — 5 repositorios
   ▼
db_models/ (ORM sobre las 42 tablas del schema.sql)
```

| Servicio | Responsabilidad |
|---|---|
| `solicitud_service` | Crear/detallar solicitud, datos de formalización, estados |
| `evaluacion_service` | Obtener reportes (Experian o mock) y correr el motor; persiste versión |
| `motor_decision_service` + `reglas_*` | Pipeline del motor Gold |
| `capacidad_pago_service` | Capacidad de pago versionada |
| `documento_service` | Paquete legal DOCX → 8 documentos (MERGEFIELD, tokens `{{CAMPO}}`, copia+literal y generación python-docx); todos sellados con `uuid_firma` |
| `textos_legales` | Texto Habeas Data versionado + `sha256` para `consentimiento_habeas` |
| `otp_service` | OTP: 6 dígitos `secrets`, solo `sha256` en BD |
| `notificacion_service` | SMTP; fallback a log en demo |
| `desembolso_service` | Registro de desembolso multi-tabla (atómico) |
| `evidencia_service` | Sesiones de captura por token, archivos, MIME |
| `valor_ingreso_service` | Ingreso verificado → `cotizante*` |
| `autenticacion_service` | Login demo (compare_digest) |
| `elegibilidad`, `finanzas`, `letras`, `seguro`, `health`, `mapeos_db`, `validaciones_identidad` | Soporte |

**Transaccionalidad** — `db_models/session.py::get_db`: una sesión por
request → `commit()` al final del request, `rollback()` ante excepción,
`close()` siempre. Los repositorios solo hacen `flush()`, así que una
operación multi-tabla (ej. desembolso que toca 6 tablas) es atómica.
`pool_pre_ping=True` en Postgres; `StaticPool` para SQLite en memoria
(tests).

**Arranque (`lifespan`)**: carga `parametros.json` y **falla temprano** si
es incoherente; `db_crear_tablas` solo para bootstrap local (producción
usa Alembic).

---

## 5 · Motor de decisión (Motor_desicion_Gold integrado)

Pipeline de 7 etapas auditables, ejecutado por `motor_decision_service` +
`reglas_filtros_duros`/`reglas_ingreso`/`reglas_perfil`:

```
filtros duros (BRD) → ingreso final (VI verificado vs declarado,
mediana de cotizantes, continuidad calculada de resultado_pagos real)
→ exclusión por score → perfil score → perfil ingreso
→ matriz de decisión → capacidad de pago (tasa del motor, seguro 0,35% m.v.)
→ decisión binaria + causales + trazabilidad
```

- **Resultado externo binario** (aprobado/rechazado); internamente guarda
  `decision_interna`, perfiles, score y causales — todo en
  `motor_evaluacion_auditoria` (request + resultado completos).
- **Versionado**: cada evaluación es `evaluacion_credito.version` nueva
  (`vigente`), con `capacidad_pago` igual. `solicitud_causal` usa
  `activa` (soft-delete) — una re-evaluación admin nunca borra el porqué
  del rechazo original.
- **Parámetros vivos**: umbrales en `parametros.json` (`GET/PUT
  /api/parametros`, `POST /reset`) — editables por admin sin redeploy.
- **Dos puertas**: `POST /api/motor/evaluar*` evalúa **sin persistir**
  (simulador, con `escenario_mock` en demo); `POST
  /api/solicitudes/{id}/evaluar` es el flujo real que persiste y audita.
  En demo sin `consultar_experian` usa `mock_buro` (escenarios
  deterministas); con credenciales UAT consulta Experian de verdad.

---

## 6 · Comunicación frontend ↔ backend

| Enlace | Protocolo | Detalle |
|---|---|---|
| SPA → API | **REST · JSON** sobre `/api/*` | Cliente en `features/*/api/*Api.ts`; `VITE_API_URL` vacío = mismo origen (proxy en dev, nginx en staging) |
| Auth | `POST /api/auth/login` | **Demo**: credenciales fijas `.env`, `compare_digest`, devuelve usuario+rol. **No hay JWT/sesión server-side** — los endpoints no exigen token |
| Captura móvil | HTTPS + **token de un solo uso** | `sesion_captura` con `CAPTURA_TTL_MINUTOS=30`; el cliente no tiene login — el link lo autentica por posesión |
| API → PostgreSQL | SQL · SQLAlchemy · psycopg | Solo repositorios |
| API → Experian | REST · HTTPS · OAuth2 client credentials | HDC+ (buró) e Valor Ingreso; SPLA-UAT en demo |
| API → correo | SMTP · TLS | OTP y notificaciones; sin host → demo-log |

**Contrato**: OpenAPI auto-generado en `/api-docs` (Swagger) y `/redoc`.
Requests validados con Pydantic en backend y Zod en frontend
(`schemas/solicitud-schema.ts`). Errores de dominio → HTTP semánticos por
`error_middleware` (excepciones de dominio → `JSONResponse` con `error` +
`detail`; handler global para no controladas).

### Contrato API — 31 endpoints

| Router | Endpoints |
|---|---|
| `/api/auth` | `POST /login` |
| `/api/motor` | `POST /evaluar` · `POST /evaluar-con-archivos` · `POST /ingreso` · `GET /escenarios` |
| `/api/solicitudes` | `POST /` · `GET /` · `GET /{id}` · `POST /{id}/evaluar` · `GET /{id}/ofertas` · `POST /{id}/ofertas/seleccionar` · `PUT /{id}/datos-formalizacion` · `POST /{id}/otp` · `POST /{id}/otp/verificar` · `POST /{id}/desembolso` · `POST /{id}/cancelar` |
| captura/evidencias | `POST /sesiones-captura` · `GET /sesiones-captura/{id}` · `GET /captura/{token}` · `POST /captura/{token}/evidencias` · `GET /solicitudes/{id}/evidencias` · `GET /evidencias/{id}/contenido` |
| `/api/auditoria` | `GET /auditoria` · `GET /auditoria/{evaluacion_id}` |
| `/api/parametros` | `GET` · `PUT` · `POST /reset` |
| `/api/catalogo` | `GET /productos` · `GET /bancos` |
| `/api/health` | `GET /health` · `GET /` |

---

## 7 · Datos — PostgreSQL 16 (42 tablas en schema.sql, 10 migraciones)

| Dominio | Tablas clave |
|---|---|
| Identidad | `cliente`, `usuario`, `rol`, `otp` |
| Solicitud | `solicitud_credito`, `solicitud_contacto_vivienda`, `datos_laborales`, `solicitud_causal`, `estado_historial` |
| Evaluación | `evaluacion_credito` (versionada) · `evaluacion_detalle` · `criterio_evaluacion` · `capacidad_pago` (versionada) |
| Formalización | `oferta_credito` (`fecha_vigencia`) · `credito_financiacion` · `producto_vehiculo` (desglose hoja de negocio: descuento, accesorios, matrícula, SOAT, impuestos, `aval_pct`) · `desembolso` · `cuenta_bancaria` · `banco` |
| Cumplimiento | `consentimiento_habeas` (versión del texto + `sha256` + canal + IP + `fecha_aceptacion` con hora exacta) |
| Evidencias | `sesion_captura` · `documento_evidencia` |
| Auditoría | `motor_evaluacion_auditoria` · `auditoria_cambio` · `auditoria_usuario` |
| Ingreso verificado | `cotizante*` (Valor Ingreso) |
| Soporte | seguros · aliados/catálogos · `metricas_reporte` |

**Decisiones de datos**: evaluaciones y capacidades **versionadas**
(`version`/`vigente`); causales con `activa` (historial preservado);
`alembic/versions` 0001 baseline → 0010 desglose hoja de negocio
(`ADD COLUMN IF NOT EXISTS` para instalaciones previas); 0008 vigencia
de ofertas, 0009 consentimiento Habeas Data.

---

## 8 · Seguridad y protección de datos

| Control | Estado |
|---|---|
| Autenticación | **Solo demo** — fija en `.env`; `ENVIRONMENT=produccion` → login 503. **Sin JWT ni auth middleware** |
| Autorización | Por rol **solo en UI**; API abierta — brecha alta |
| OTP | 6 dígitos `secrets.randbelow`; solo `sha256(codigo:id_solicitud)` en BD; TTL 10 min; máx 3 intentos; invalida pendientes anteriores. Al verificar, `uuid_firma` se estampa en los 8 documentos del paquete |
| Consentimiento Habeas Data | `consentimiento_habeas`: `version_texto` + `hash_texto` (sha256 del cuerpo exacto) + `canal` (`web_asesor`/`otp_firma`) + `ip` + `fecha_aceptacion` con hora exacta; texto versionado en `textos_legales.py` |
| Captura móvil | Token de un solo uso (30 min); público pero acotado a la solicitud; máx 25 MB/archivo |
| Rate limit | 30 mutadores/min por IP, ventana deslizante **en memoria** — 1 réplica; con N réplicas → Redis (D94). En staging se relaja a 300/min porque nginx comparte la IP del proxy |
| Secretos | `compare_digest` (timing-safe); claves solo por env, nunca en código |
| Auditoría | `auditoria_*` + `motor_evaluacion_auditoria` (quién/cuándo/qué) |
| PII en evidencias | Disco local `EVIDENCIAS_DIR` — pendiente S3 + cifrado + retención |

---

## 9 · Configuración y entornos

`Settings` (pydantic-settings) lee `.env` en la raíz. `ENVIRONMENT`
(`demo` | `produccion`) conmuta las URLs/credenciales de Experian
(`*_DEMO`/`*_PROD`). `configuracion_experian_faltante()` lista las
variables vacías — la evaluación falla explícitamente si falta config.

Parametrizable por env: `SMMLV`, `OTP_TTL_MINUTOS/MAX_INTENTOS`,
`CAPTURA_TTL_MINUTOS`, `EVIDENCIA_MAX_MB`, `DOCUMENTOS_CIUDAD_FIRMA`,
`DOCUMENTOS_DIA_PAGO` (día de pago del pagaré), `DOCUMENTOS_PLANTILLAS_DIR`,
`OFERTA_VIGENCIA_DIAS` (caducidad de la oferta), `TIMEOUT_EXPERIAN_*`,
`EXPERIAN_REINTENTOS/CIRCUITO_*`, `RATE_LIMIT_*`, `SMTP_*`.

**Tres ambientes hoy**: dev local (`uvicorn :8001` + Vite `:5173`),
staging (`docker-compose.staging.yml` → `localhost:8080` + túnel
cloudflared), y producción = pendiente.

## 10 · Resiliencia e integraciones externas

| Integración | Contrato | Resiliencia |
|---|---|---|
| DataCrédito **HDC+** (buró) | REST · OAuth2 SPLA | timeout 60 s · 2 reintentos backoff 2ⁿ · circuit breaker 5 fallos → abierto 60 s |
| **Valor Ingreso** (ingresos) | REST · OAuth2 Okta | idem; parsers → `cotizante*` |
| SMTP | TLS | sin `SMTP_HOST` → notificaciones a log (no bloquea) |
| `mock_buro` | — | escenarios deterministas para dev/tests sin credenciales |

El circuito abierto degrada — el endpoint sigue respondiendo, no tumba el
flujo.

## 11 · Paquete legal (documentos)

Firma por OTP → `documento_service` produce **8 documentos** DOCX, todos
sellados por `_estampar_firma` con el párrafo `Identificador único de
firma electrónica (OTP): {uuid_firma}` (mismo UUID en los 8, vía
`python-docx`) y registrados en `documento_evidencia`:

| # | Documento | Técnica |
|---|---|---|
| 1 | `autorizacion` | MERGEFIELD + literal (correo/teléfono autorizados) |
| 2 | `carta_aprobacion` | MERGEFIELD + literal (consecutivo `XXXX→No.`, campos del asesor en blanco a mano) |
| 3 | `pagaré` | MERGEFIELD + literal (`“Consecutivo”`=num_solicitud, blanco de tasa partido en runs) |
| 4 | `instrucciones` | MERGEFIELD + literal (`No 001`→consecutivo) |
| 5 | `prenda` | MERGEFIELD |
| 6 | `asegurabilidad` | generada con `python-docx` — datos del asegurado en tabla |
| 7 | `solicitud_credito` | copia + tokens `{{CAMPO}}` — formato real de Inversiones Pacífico: titular, contacto, residencia, personal, financiero, laboral y hoja de negocio con el desglose persistido en `producto_vehiculo` (descuento, accesorios, matrícula, SOAT, aval) — los totales cuadran con `saldo_financiar` |
| 8 | `compromiso` | copia + reemplazo literal — la plantilla venía diligenciada con datos de muestra que se sustituyen por el titular |

El doc 7 se generó transformando el formato comercial real a tokens con
`scripts/generar_plantilla_solicitud.py` (script de una sola vez). La carpeta
`Informes Pacifico/Plantillas/` es la fuente legal: al cambiar un texto
se re-edita el `.docx` conservando MERGEFIELDs/tokens.

## 12 · Calidad y CI/CD

| Capa | Verificación |
|---|---|
| Backend | `pytest tests -q` — 22 archivos de tests (unit/ + integration/); SQLite en memoria + `respx` (mocks httpx de Experian) + `TestClient` |
| Frontend | `tsc --noEmit` · `eslint` · `vitest` (56 tests) · `vite build`; `playwright` para e2e (`test:e2e`) |
| CI (GitHub Actions) | 3 jobs: *backend* (py3.14: pytest + `pip-audit` no-bloqueante), *frontend* (node 22: tsc+lint+vitest+build+`npm audit --audit-level=high`), *docker* (build de la imagen) |
| Convenciones | `lint-staged` (eslint --fix + prettier); commits sin trailers de agente (AGENTS.md) |

## 13 · Despliegue

| Ambiente | Cómo corre |
|---|---|
| Dev | `uvicorn :8001 --reload` + `npm run dev` (proxy `/api`); SQLite o Postgres local |
| Staging | `docker-compose.staging.yml`: `web` (nginx: SPA + proxy `/api`) + `api` (`alembic upgrade head` al arrancar) + `db` (postgres:16) — todo por `:8080`; compartir con `cloudflared tunnel --url http://localhost:8080` |
| Objetivo (aún no) | CloudFront+S3 (SPA) · ALB+ECS Fargate (API) · RDS · S3 evidencias — ver `ARQUITECTURA.md` §5 |

`Dockerfile` del backend: `python:3.14-slim`, usuario no-root (`app`,
uid 1001), `alembic upgrade head` + uvicorn en el CMD. `frontend/Dockerfile`:
multi-stage node-build → nginx.

## 14 · Mantenimiento — qué tocar para qué

| Tarea | Dónde |
|---|---|
| Nuevo endpoint | `routes/<dominio>_routes.py` + `services/` + `models/` (Pydantic) + registrar en `main.py` |
| Cambiar reglas del motor | `parametros.json` (umbrales, sin código) o `services/reglas_*` (lógica) |
| Migración de BD | `alembic revision` + `upgrade head` (el Dockerfile ya la aplica al arrancar) |
| Nueva página front | `pages/` + cliente en `features/*/api/` + schema Zod |
| Nueva plantilla legal | `backend/documentos/plantillas/*.docx` (MERGEFIELDs o tokens `{{CAMPO}}`) + entrada en `_DOCS` de `documento_service` — el sello de `uuid_firma` es automático |
| Secretos | solo `.env` — nunca en código ni en git (`.env*` gitignored) |

## 15 · Preguntas esperadas en la revisión — con respuestas

### 1. "¿Cómo se autentica la API?"

**Hoy**: solo login demo (`POST /api/auth/login` compara credenciales del
`.env` con `compare_digest` y devuelve usuario+rol). No hay JWT ni
middleware de auth — los endpoints están abiertos y el rol se aplica solo
en la UI. Es una brecha conocida del MVP.

**Propuesta**: JWT de corta duración emitido en el login
(`pyjwt`/`python-jose`) + una dependencia `require_role("Administrador")`
en FastAPI aplicada por router. Las tablas `usuario`/`rol` ya existen.
IdP corporativo (Cognito/Entra) solo si el negocio lo exige — con 2 devs
y bajo volumen, JWT propio es suficiente y no agrega un proveedor.

**Decisión necesaria**: ¿auth propia o IdP de la empresa?

### 2. "¿Cómo escala? ¿Cuántas solicitudes/día soporta?"

**Hoy**: 1 proceso uvicorn, sin estado de sesión server-side → la API ya
es casi stateless. Los únicos estados en memoria son: rate limit (por
IP), circuit breaker de Experian, y `parametros.json` (archivo en disco).

**Para N réplicas**: rate limit → Redis (D94); `parametros.json` → tabla
en BD (ya existe `auditoria_parametros`, falta mover la fuente de verdad);
evidencias → S3. Con eso, el API escala horizontal detrás de un ALB sin
más cambios — Postgres queda como único estado compartido.

**Decisión necesaria**: volumen esperado → define si basta 1 réplica
con `--workers 2` o si se justifica multi-réplica.

### 3. "¿RPO/RTO y retención de datos personales?"

**Hoy**: Postgres en volumen Docker — respaldo manual, sin política de
retención. Habeas Data: el consentimiento **ya se persiste versionado** —
`consentimiento_habeas` guarda `version_texto`, `hash_texto` (sha256 del
texto exacto en `textos_legales.py`), `canal` (`web_asesor`/`otp_firma`),
`ip` y `fecha_aceptacion` con hora exacta; se registra en la captura del
asesor y en la firma OTP del cliente.

**Propuesta**: RDS con backups automáticos (RPO ≈5 min con WAL, RTO
≈30 min single-AZ; Multi-AZ solo si el negocio lo paga). Lo pendiente de
Habeas Data es la política de retención y el procedimiento de supresión
de PII (derecho de borrado de la Ley 1581).

**Decisión necesaria**: política de retención y procedimiento de borrado
(derecho de supresión de la Ley 1581).

### 4. "¿Dónde quedan las evidencias con PII?"

**Hoy**: disco local `EVIDENCIAS_DIR` (volumen Docker en staging). Cédulas
y videos de clientes sin cifrado en reposo ni ciclo de vida.

**Propuesta**: S3 privado + URLs prefirmadas de corta duración +
`SSE-KMS` + lifecycle policy de retención. El punto de cambio es único:
`evidencia_service`/`evidencia_repository` (el API ya guarda solo
metadatos en `documento_evidencia` — la migración a S3 es acotada).

### 5. "¿Qué pasa si Experian está caído?"

**Hoy**: timeout 60 s → 2 reintentos con backoff → circuit breaker (5
fallos, abierto 60 s). La evaluación falla con error controlado
("la evaluación no respondió") — no tumba el sistema, pero **no hay
fallback**: sin Experian no hay evaluación en línea.

**Decisión necesaria (negocio)**: ¿permitir evaluar solo con datos
declarados marcándola como "evaluación degradada" y exigiendo re-consulta
posterior, o bloquear hasta que Experian responda? La primera mantiene la
operación andando; la segunda es más segura pero detiene ventas.

### 6. "¿El OTP cuenta como firma electrónica?"

**No** — el OTP prueba *posesión del correo*, no es firma criptográfica.
Lo que sí tenemos como evidencia: OTP verificado + hash + timestamp + IP
+ `uuid_firma` estampado en los 8 documentos DOCX generados post-firma
+ consentimiento versionado en `consentimiento_habeas`. Para firma con valor legal pleno
(D163) hace falta un proveedor (en Colombia: Certicámara, ANDI SCDE,
o DocuSign/Clerk como integrables) — queda como integración futura; el
punto de extensión ya existe en `otp_service` + `documento_service`.

### 7. "¿Cómo llega el desembolso del banco? (webhooks)"

**Hoy**: dos vías. Síncrona — el admin registra el desembolso
(`POST /api/solicitudes/{id}/desembolso`, transacción atómica
multi-tabla). Y asíncrona — `POST /webhook/desembolso` para el emisor
del giro (tesorería/core bancario): firma HMAC-SHA256 del cuerpo con
`WEBHOOK_SECRETO` compartido (`X-Signature: sha256=<hex>`) +
`X-Timestamp` en ventana anti-replay (`WEBHOOK_VENTANA_SEGUNDOS`,
default 300 s; sin secreto → 503). Ciclo del giro: `en_transito` crea el
desembolso pendiente, `confirmado` lo acredita (idempotente) y
`rechazado` solo aplica sobre un pendiente. Identifica por
`id_solicitud` o `num_solicitud`; cada evento queda en el log
`creditos.webhook`. Contrato para el integrador:
`docs/manual_integracion_aliados.md` §5.1.

**Pendiente real**: eventos **salientes** (notificar al aliado cambios
de estado/decisión/oferta) — no existen; el webhook es entrante.

### 8. "¿Hay pipeline de despliegue (CD)?"

**Hoy**: CI completo (tests backend/frontend + build docker + auditoría
de dependencias en ambos), pero el despliegue es manual
(`docker compose up` / `cloudflared`).

**Propuesta mínima**: job extra en `ci.yml` que haga `docker build` +
`push` a un registry (ECR/GHCR) con tag del SHA, y un `compose pull && up -d`
en el host destino (vía SSH o Watchtower). IaC (Terraform) solo si se
adopta AWS como nube definitiva.

---

### Resumen de decisiones que necesitamos del negocio

| # | Decisión | Opción recomendada |
|---|---|---|
| 1 | Auth propia vs IdP corporativo | JWT propio (menos piezas, 2 devs) |
| 2 | Volumen/réplicas | Confirmar volumen; el camino a N réplicas está identificado |
| 3 | Retención PII | Consentimiento ya persistido (`consentimiento_habeas`); falta la política de retención/supresión |
| 5 | Experian caído | Evaluación degradada con re-consulta, o bloqueo — es de riesgo/negocio |
| 6 | Firma legal | Proveedor externo cuando el volumen lo justifique |
| — | Nube definitiva | AWS si es la corporativa; el diseño no depende del proveedor |

---

## 16 · Cobertura funcional contra un LMS de referencia

Un sistema de gestión de préstamos (Loan Management System) estándar —
la guía de AppMaster lo descompone en 6 módulos — cubre el ciclo de vida
completo del crédito. Así quedamos nosotros:

| Módulo LMS de referencia | Qué pide | Estado en el sistema |
|---|---|---|
| **Originación** | Procesamiento automatizado de solicitudes, scoring, workflow de aprobación | **Cubierto**: wizard de 5 pasos, motor Gold con pipeline auditable, decisión binaria + causales versionadas. El "workflow de aprobación" es decisión automática del motor + re-evaluación admin (sin comité) |
| **Servicing** (gestión del crédito activo) | Programación de pagos, cálculo de intereses, comunicación con el cliente | **Parcial**: la tabla de amortización y `credito_financiacion`/`desembolso` existen; la gestión de pagos/cobranza activa es **fuera de alcance** del MVP (hay documento `compromiso_cartera`). Decisión de alcance, no omisión accidental |
| **Reportes y analítica** | Informes parametrizables, dashboards | **Parcial**: `metricas_reporte` + páginas Estados/Resumen/Riesgo; sin reportes parametrizables ni BI |
| **Gestión documental** | Repositorio digital, control de versiones | **Parcial**: repositorio de evidencias por solicitud + paquete legal DOCX generado; control de versiones de documentos pendiente |
| **Seguridad y cumplimiento** | Cifrado en tránsito/reposo, control de acceso, normativa | **Parcial**: TLS en borde (staging), OTP hash, rate limit, auditoría, consentimiento Habeas Data versionado (`consentimiento_habeas` — Ley 1581); faltan auth por endpoint, cifrado en reposo de evidencias, retención/supresión de PII y listas SARLAFT |
| **Integración API** | Burós de crédito, pasarelas de pago, sistemas internos | **Cubierto**: DataCrédito HDC+ y Valor Ingreso integrados con resiliencia + reuso de consulta vigente (`consulta_buro`); webhook entrante de desembolso firmado HMAC (`POST /webhook/desembolso`); SARLAFT y eventos salientes pendientes |

### Lectura honesta para el arquitecto

- **El núcleo duro (originación + decisión auditable) está completo** — es
  lo que más difícil es de conseguir bien.
- **Lo parcial es deliberado**: servicing, reportes avanzados y firma
  electrónica real quedaron fuera del MVP; cada uno tiene punto de
  extensión identificado.
- **Las brechas de cumplimiento** (auth real, PII en reposo, retención de
  datos, SARLAFT) están enumeradas en §15 — no son desconocidas.

### De la guía de plataformas financieras (Innowise) que ya aplicamos

- **"Seguridad y cumplimiento se integran, no se añaden"** → auditoría
  nativa (`motor_evaluacion_auditoria` guarda request+resultado de cada
  evaluación), causales históricas soft-deleted, OTP con hash.
- **"Empezar con monolito simple, evolucionar a microservicios si escala"**
  → ADR #1/#2: monolito modular con límites por dominio.
- **"Arquitectura modular basada en API"** → REST `/api` desacoplado del
  frontend; la captura móvil ya es un cliente API independiente.
- **RegTech**: Habeas Data ya quedó con evidencia versionada
  (`consentimiento_habeas`); el cumplimiento pendiente (SARLAFT/listas)
  tiene candidatos identificados (Truora/aliados).

### Pirámide de pruebas (estado)

| Nivel | Cobertura |
|---|---|
| Unitarias | `pytest` backend + `vitest` frontend — reglas del motor, parsers, servicios |
| Integración | `tests/integration/` — endpoints completos con TestClient + respx |
| UAT | El ambiente staging Docker existe precisamente para esto |
| Rendimiento | **Pendiente** — sin pruebas de carga; con el volumen de un concesionario no es bloqueante, pero hay que medir la consulta Experian (latencia ~s) |
| Seguridad | **Pendiente** — `pip-audit`/`npm audit` en CI; sin pentest ni análisis estático (bandit/DAST) |

---

_Fuente: código real — `backend/` (main, config, session, routes,
services, repositories, integrations, middlewares), `schema.sql`,
`alembic/versions/`, `frontend/` (package.json, vite.config, src/),
`docker-compose*.yml`, `.github/workflows/ci.yml`, `.env*.example`._
