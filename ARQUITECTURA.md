# Arquitectura — Plataforma de originación de crédito

Inversiones Pacífico / SUMOTO. Este documento describe el sistema **tal como
existe en el repositorio** (no una arquitectura aspiracional): qué tecnología
vive en cada capa, cómo se comunican los componentes, qué decisiones se
tomaron y qué preguntas quedan abiertas para la revisión arquitectónica.

**Stack**: React 19 + Vite 8 + TypeScript · FastAPI 0.141 + Python 3.14 +
SQLAlchemy 2.0 + Pydantic 2 · PostgreSQL 16 (SQLite en tests/demo) ·
Docker · Alembic · Vitest/Pytest.

---

## 1 · Diagrama por capas

```text
        ┌─────────────────────────────┐
        │          usuario            │   asesor (resultado binario)
        └─────────────┬───────────────┘   administrador (score + causales)
                      │ https             cliente móvil (link con token, sin login)
                      ▼
        ┌─────────────────────────────┐
        │  perímetro: cors whitelist  │   hoy: CORS + rate limit + errores
        │  rate limit · dominio errs  │   de dominio (middlewares FastAPI)
        └─────────────┬───────────────┘
                      │
 ════ visual ═════════╪═════════════════════════════════════════════════════
                      │
  ┌───────────────────▼────────────────────┐   ┌──────────────────────────┐
  │ frontend — react 19 · vite 8 · ts      │   │ hoy corre en:            │
  │ spa · react router · tanstack query    │   │ `npm run dev` → :5173    │
  │                                        │   │ vite proxy /api → :8001  │
  │ pages: originación 5 pasos · simulador │   │ (build estático)         │
  │ solicitudes · detalle · panel asesor   │   │                          │
  │ captura móvil (pública, por token)     │   │ objetivo: s3+cloudfront  │
  └───────────────────┬────────────────────┘   └──────────────────────────┘
                      │
        restful · json · https · sesión demo (sin JWT todavía)
                      │
 ════ aplicación ═════╪═════════════════════════════════════════════════════
                      │
  ┌───────────────────▼────────────────────┐   ┌──────────────────────────┐
  │ backend api — fastapi 0.141 · docker   │   │ hoy corre en:            │
  │                                        │   │ uvicorn :8001            │
  │ 8 routers /api:                        │   │ (docker-compose)         │
  │  solicitudes · motor · evidencias      │   │                          │
  │  auth · auditoría · parámetros         │   │ objetivo: ecs fargate ·  │
  │  catálogos · health                    │   │ ec2 · lightsail          │
  │                                        │   └──────────────────────────┘
  │ servicios dominio (monolito modular):  │
  │  solicitud · evaluación · capacidad ·  │
  │  otp · documento docx · desembolso ·   │
  │  notificación · evidencia              │
  │                                        │
  │ motor decisión (pipeline interno):     │
  │  filtros duros→ingreso→score→perfiles  │
  │  →matriz→capacidad→decisión+causales   │
  └─┬──────────┬──────────┬────────┬───────┘
    │          │          │        │
════ datos ════╪══════════╪════════╪═══════════════════════════════════════
    │          │          │        │
    │          │          │ smtp tls          ┌──────────────────────────┐
    │          │          ▼                   │ externos:                │
    │          │  ┌──────────────┐            │  datacrédito experian →  │
    │          │  │ smtp         │            │  hdc+ (buró) · valor     │
    │          │  │ otp 6 dígitos│            │  ingreso (ingresos)      │
    │          │  │ correos demo │            │  smtp → otp / correos    │
    │          │  └──────────────┘            └──────────────────────────┘
    │          │
    │          │ oauth2 client credentials · rest https
    │          │ timeout 60s · retry x2 backoff 2^n · circuit breaker 5/60s
    │          ▼
    │     ┌──────────────────┐
    │     │ datacrédito      │
    │     │ hdc+ · valor     │
    │     │ ingreso          │
    │     └──────────────────┘
    │
    │ sql · sqlalchemy 2.0 · psycopg  (solo los 5 repositorios tocan la bd)
    ▼
  ┌──────────────────────────┐          ┌──────────────────────────┐
  │ postgresql 16            │      ──▶ │ hoy: contenedor docker   │
  │ 42 tablas                │────────▶ │ postgres:16 + volumen    │
  │                          │          │                          │
  │ evaluación versionada ·  │          │ objetivo: rds ·          │
  │ causales históricas ·    │          │ ec2-postgres             │
  │ auditorías · otp ·       │          └──────────────────────────┘
  │ evidencias · financiación│
  └──────────────────────────┘
                │
                │ fs local
                ▼
  ┌──────────────────────────┐          ┌──────────────────────────┐
  │ evidencias (disco)       │      ──▶ │ hoy: EVIDENCIAS_DIR      │
  │ docx legales + fotos     │────────▶ │ objetivo: s3             │
  └──────────────────────────┘          └──────────────────────────┘
```

## 2 · Cómo se comunican las capas

| Enlace | Protocolo | Detalle real en el repo |
|---|---|---|
| Navegador → API | REST · JSON · HTTPS | `/api/*` · CORS por lista blanca (`CORS_ORIGINS`) · rate limit middleware |
| Login (asesor/admin) | `POST /api/auth/login` | **Demo**: credenciales contra `DEMO_USER_*` con `compare_digest`; devuelve usuario+rol fijo. **No hay JWT ni middleware de auth** — los endpoints quedan abiertos; el rol lo aplica solo el frontend |
| Cliente móvil → API | HTTPS + token de un solo uso | `sesion_captura` con `CAPTURA_TTL_MINUTOS=30`; acceso público sin login, scope limitado a subir evidencias de esa solicitud |
| API → PostgreSQL | SQL · SQLAlchemy 2.0 · psycopg | Una sesión por request (`get_db`); solo los 5 repositorios emiten SQL |
| API → Experian | REST · HTTPS · OAuth2 client credentials | `hdc_client` (HDC+/buró) e `income_client` (Valor Ingreso); timeout 60 s, 2 reintentos con backoff 2ⁿ, circuit breaker (5 fallos → abierto 60 s) |
| API → correo | SMTP · TLS | `NotificacionService`; sin `SMTP_HOST` cae a modo demo-log |
| Dev: Vite → API | proxy `/api` → `:8001` | `API_PROXY_TARGET` en dev; `VITE_API_URL` en prod |

## 3 · Contrato API (31 endpoints reales)

| Router | Endpoints | Dominio |
|---|---|---|
| `/api/auth` | `POST /login` | Sesión demo |
| `/api/motor` | `POST /evaluar` · `POST /evaluar-con-archivos` · `POST /ingreso` · `GET /escenarios` | Motor Gold standalone (no persiste) |
| `/api/solicitudes` | `POST /` · `GET /` · `GET /{id}` · `POST /{id}/evaluar` · `GET /{id}/ofertas` · `POST /{id}/ofertas/seleccionar` · `PUT /{id}/datos-formalizacion` · `POST /{id}/otp` · `POST /{id}/otp/verificar` · `POST /{id}/desembolso` · `POST /{id}/cancelar` | Ciclo completo: crear → evaluar → ofertar → formalizar → firmar → desembolsar (o cancelar con motivo) |
| `/api/sesiones-captura`, `/api/captura`, `/api/evidencias` | `POST /sesiones-captura` · `GET /sesiones-captura/{id}` · `GET /captura/{token}` · `POST /captura/{token}/evidencias` · `GET /solicitudes/{id}/evidencias` · `GET /evidencias/{id}/contenido` | Captura remota de documentos por link tokenizado |
| `/api/auditoria` | `GET /auditoria` · `GET /auditoria/{evaluacion_id}` | Trazabilidad del motor y del flujo |
| `/api/parametros` | `GET · PUT · POST /reset` | Parámetros del motor (admin) |
| `/api/catalogo` | `GET /productos` · `GET /bancos` | Catálogos de negocio |
| `/api/health` | `GET /health` · `GET /` | Liveness |

Distinción importante: `/motor/*` evalúa **sin persistir** (el simulador);
`/solicitudes/*` es el flujo que persiste y audita.

## 4 · Qué hay dentro de cada caja

### visual — frontend (`frontend/src`, Feature-Sliced Design)

- `pages/` — 13 pantallas: Originación (5 pasos), Simulador, Solicitudes,
  DetalleSolicitud, Resultado, PanelAsesor, CapturaMovil…
- `features/credit-origination/` — `api` (cliente REST) · `model`
  (reglas/formatos) · `schemas` (validación) · `ui` (componentes)
- `entities/credit` · `shared` (lib + ui) · `widgets` (app-shell, auth…)
- **El control de rol es solo visual**: el asesor no ve score/causales
  porque el frontend no los pinta — el API los devuelve igual. Medida
  pendiente: scopes por endpoint.

### aplicación — backend (FastAPI, monolito modular)

| Subcapa | Contenido real |
|---|---|
| `routes/` (8 routers) | los 31 endpoints de la tabla anterior |
| `services/` (24) | orquestación (solicitud, evaluación, desembolso, documento DOCX, otp, notificación, textos legales) + motor (filtros duros, ingreso, perfil, matriz, capacidad) + integración (valor_ingreso, seguro 0,35 %) |
| `repositories/` (5) | solicitud · evaluación · auditoría · evidencia · health — único punto de SQL; usan `flush()`, nunca `commit()` |
| `db_models/` | ORM sobre las 42 tablas |
| `integrations/datacredito/` | auth · hdc_client · income_client · parsers · resiliencia · mock_buro |
| middlewares | `RateLimitMiddleware` (30 mutadores/min/IP, en memoria) · `CORSMiddleware` · `registrar_manejadores` (errores de dominio → HTTP + handler de excepción no controlada) |

**Transaccionalidad** — una transacción por request
(`get_db`: `yield` → `commit()` al final, `rollback()` ante excepción,
`close()` siempre). Los servicios coordinan `flush()` entre repositorios,
así una operación multi-tabla (ej. desembolso que toca 6 tablas) es
atómica: o completa o no queda nada parcial.

**Motor de decisión** (pipeline interno, 7 etapas auditables):
filtros duros → ingreso final → exclusión score → perfil score →
perfil ingreso → matriz decisión → capacidad de pago →
decisión binaria + causales + trazabilidad + `motor_evaluacion_auditoria`.
Cada evaluación persiste request + resultado: es reproducible.

### datos — PostgreSQL 16 (42 tablas, 10 migraciones Alembic)

identidad (`cliente`, `usuario`, `rol`, `otp`) · solicitud
(`solicitud_credito`, `contacto_vivienda`, `datos_laborales`, `causal`,
`estado_historial`) · evaluación (`evaluacion_credito` versionada,
`evaluacion_detalle`, `criterio_evaluacion`, `capacidad_pago`) ·
formalización (`oferta_credito`, `credito_financiacion`,
`producto_vehiculo`, `desembolso`, `cuenta_bancaria`, `banco`) ·
evidencias (`sesion_captura`, `documento_evidencia`) · auditoría
(`motor_evaluacion_auditoria`, `auditoria_cambio`, `auditoria_usuario`) ·
seguros · aliados/catálogos · ingreso verificado (`cotizante*`) ·
`metricas_reporte`.

**Patrón de versionado** — `evaluacion_credito` y `capacidad_pago` llevan
`version`/`vigente`; `solicitud_causal` usa `activa` (soft-delete). Una
re-evaluación nunca borra la anterior: marca la vieja como no vigente e
inserta la nueva, preservando el historial de causas de rechazo.

## 5 · Seguridad y protección de datos

| Control | Estado real |
|---|---|
| Autenticación | **Solo demo** — credenciales fijas en `.env`; en `ENVIRONMENT=produccion` el login devuelve 503. No hay JWT, ni refresh, ni middleware de auth |
| Autorización | Por rol pero **solo en UI**; el API no exige rol por endpoint |
| OTP (firma pagaré) | 6 dígitos `secrets`, en BD solo `sha256(codigo:id_solicitud)`; TTL 10 min, máx. 3 intentos, invalida los pendientes anteriores. Al verificar: `uuid_firma` se estampa en los 8 documentos del paquete legal |
| Consentimiento Habeas Data | `consentimiento_habeas`: versión del texto + `sha256` del cuerpo exacto + canal (`web_asesor`/`otp_firma`) + IP + `fecha_aceptacion` con hora exacta (Ley 1581) |
| Captura móvil | Token de un solo uso (`CAPTURA_TTL_MINUTOS=30`); acceso público pero limitado a esa solicitud; límite 25 MB/archivo |
| Rate limit | 30 mutadores/min por IP, ventana deslizante en memoria — **suficiente para 1 réplica; con N réplicas requiere Redis** (ver D94) |
| PII / evidencias | En disco local `EVIDENCIAS_DIR` — pendiente S3 + retención |
| Comparaciones de secretos | `compare_digest` (timing-safe) |
| Auditoría | `auditoria_*` y `motor_evaluacion_auditoria` registran quién/cuándo/qué |

**Brecha explícita**: hoy la API no valida que el llamante sea asesor ni
admin — cualquier petición alcanza `/api/*`. El login solo compuerta la
SPA. Antes de producción hace falta JWT + guards por endpoint.

## 6 · Configuración y entornos

- `Settings` (pydantic-settings) lee `.env` en la raíz; `ENVIRONMENT=demo|produccion` conmuta URLs/credenciales de Experian (`*_DEMO`/`*_PROD`).
- `configuracion_experian_faltante()` lista las variables vacías — el arranque puede fallar temprano si falta config.
- `parametros.json` (umbrales del motor) se carga en `lifespan` y **falla el arranque si es incoherente**.
- `SMMLV`, `DOCUMENTOS_CIUDAD_FIRMA`, `DOCUMENTOS_DIA_PAGO` (día de pago del pagaré), `OFERTA_VIGENCIA_DIAS` (caducidad de la oferta), `OTP_TTL_MINUTOS`, `CAPTURA_TTL_MINUTOS`, `EVIDENCIA_MAX_MB` — todo parametrizable por env.
- BD: `sqlite:///…` en dev/tests (StaticPool en memoria para la suite), `postgresql+psycopg://` en real; `DB_CREAR_TABLAS` solo para bootstrap, en producción se usan las migraciones Alembic.

## 7 · Resiliencia e integraciones externas

| Integración | Patrón |
|---|---|
| DataCrédito HDC+ (buró) | OAuth2 SPLA · timeout 60 s · 2 reintentos backoff 2ⁿ · circuit breaker 5 fallos/60 s · `mock_buro` para dev/tests sin credenciales |
| Valor Ingreso (ingresos) | OAuth2 Okta · mismo patrón de resiliencia · parsers a `cotizante*` |
| SMTP | TLS; si no hay `SMTP_HOST`, las notificaciones caen a modo demo-log (no bloquean el flujo) |

Fallbacks: el motor puede evaluar con datos declarados cuando Experian
está caído (el circuito abierto degrada, no tumba el endpoint).

## 8 · Despliegue y CI/CD

- **Imagen**: `Dockerfile` único del backend; `docker-compose.yml` levanta
  `api` (:8000) contra Postgres local vía `host.docker.internal`, o un
  `postgres:16-alpine` propio con el perfil `db-local` (:5433). Volumen
  `evidencias` separa los archivos del contenedor.
- **CI** (`.github/workflows/ci.yml`, 3 jobs en `ubuntu-latest`):
  - *backend*: Python 3.14 · `pytest tests -q` (SQLite en memoria, sin
    Postgres) + `pip-audit` (reporta CVEs, no bloquea)
  - *frontend*: Node 22 · `tsc --noEmit` + `lint` + `vitest` + `build` +
    `npm audit --audit-level=high`
  - *docker*: `docker build` de la imagen del backend
- **CD**: pendiente — no hay pipeline de despliegue aún.

## 9 · Decisiones de arquitectura (ADRs)

| # | Decisión | Porqué |
|---|---|---|
| 1 | **Monolito modular**, no microservicios | Equipo pequeño, bajo volumen; los dominios (originación, motor, evidencias, formalización) son módulos con límites claros (routes→services→repositories) que pueden extraerse si escala |
| 2 | Motor Gold integrado como módulo, no servicio aparte | Evita latencia/red entre decisión y persistencia; el pipeline ya es una frontera limpia por si se extrae |
| 3 | Evaluaciones **versionadas**, no sobrescritas | Trazabilidad regulatoria: cada decisión queda con su request/resultado/causales; un rechazo re-evaluado conserva por qué fue rechazado |
| 4 | Resultado **binario** al asesor | Causales/score son sensibles; solo el admin los ve. Reduce riesgo de que el asesor "aprenda" a esquivar filtros |
| 5 | Transacción por request | Simplicidad + atomicidad; los repos solo `flush()` |
| 6 | OTP propio (hash+TTL) en vez de firma electrónica de terceros | Suficiente para la formalización del MVP; firma electrónica real (D163) queda como integración futura |
| 7 | Captura por **token de un solo uso**, sin login del cliente | El cliente no tiene cuenta; el link lo autentica por posesión |
| 8 | Rate limit en memoria | Sin infraestructura extra en el MVP; migrar a Redis al escalar réplicas |
| 9 | SQLite↔PostgreSQL por `DATABASE_URL` | Suite de tests sin infraestructura; mismo ORM corre ambos dialectos |

## 10 · Brechas y preguntas abiertas para la revisión

### Brechas (con severidad)

| Brecha | Nivel | Acción propuesta |
|---|---|---|
| Sin auth real — endpoints abiertos | **Alta** | JWT + IdP corporativo + guards por rol |
| Perímetro inexistente | **Alta** | WAF + TLS terminado en borde al desplegar |
| Evidencias PII en disco local | **Alta** | S3 privado + URLs prefirmadas + retención |
| OTP/notificaciones en modo demo-log | Media | SMTP productivo o SES |
| Sin webhooks de desembolso (D57/D77) | Media | `/webhook/*` firmados para el banco |
| Observabilidad solo logs | Media | Stack de métricas/trazas + alarmas + SLO |
| Firma electrónica = OTP, no criptográfica | Media | Proveedor de firma (D163) |
| Sin CD | Media | Pipeline de despliegue |

### Preguntas que el arquitecto probablemente hará

1. **Autenticación**: ¿adoptamos un IdP (Cognito/Entra/Keycloak) o JWT
   propio? ¿RBAC por endpoint?
2. **Escala**: ¿volumen esperado de solicitudes/día? ¿réplicas del API
   (implica mover rate-limit a Redis y sesiones fuera del proceso)?
3. **Datos**: ¿RPO/RTO de PostgreSQL? ¿retención y borrado de PII?
   (Habeas Data: el consentimiento ya se persiste versionado en
   `consentimiento_habeas` — texto + hash + canal + IP + hora exacta;
   falta la política de retención y el procedimiento de supresión)
4. **Evidencias**: ¿cifrado en reposo, antivirus, ciclo de vida?
5. **Experian**: ¿qué pasa cuando el circuito está abierto — evaluar con
   datos declarados o rechazar el request?
6. **Motor**: ¿los umbrales de `parametros.json` cambian con auditoría
   suficiente? ¿quién puede editarlos?
7. **Despliegue**: ¿AWS único o multi-nube? ¿IaC (Terraform/CDK) o manual?
8. **Observabilidad**: ¿CloudWatch/X-Ray, ELK/ECK, o Grafana stack?

---

_Fuente: código real del repo (`backend/main.py`, `config.py`,
`db_models/session.py`, `routes/`, `services/`, `repositories/`,
`middlewares/`, `schema.sql`, `alembic/`, `frontend/src`,
`docker-compose.yml`, `.github/workflows/ci.yml`)._
