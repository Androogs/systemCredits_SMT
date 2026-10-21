# Reporte de seguridad OWASP Top 10 — D63

Fecha: 2026-10-21 · Alcance: API FastAPI (`/api/*` + `POST /webhook/desembolso`), frontend React, integraciones Experian/PlacaPi.
Metodología: revisión de controles en código, suite de tests de seguridad existente (`test_security_headers`, `test_rate_limit`, `test_autenticacion`, `test_webhook_desembolso`), auditoría de dependencias en CI. No es pentest dinámico — es evaluación de diseño y controles.

## Resumen ejecutivo

| Riesgo OWASP 2021 | Estado | Nota |
|---|---|---|
| A01 Control de acceso roto | 🔴 Hallazgo abierto | Sin auth por endpoint — ver detalle |
| A02 Fallas criptográficas | 🟡 Parcial | OTP/secretos hasheados; falta cifrado en reposo de PII |
| A03 Inyección | 🟢 Cubierto | ORM parametrizado + DTOs Pydantic + escape React |
| A04 Diseño inseguro | 🟢 Cubierto | Idempotencia, pre-filtros, ciclo de estados |
| A05 Configuración insegura | 🟡 Parcial | Headers + CORS allowlist; OpenAPI expuesto en prod |
| A06 Componentes vulnerables | 🟢 Cubierto | pip-audit + npm audit en CI |
| A07 Fallas de autenticación | 🟡 Parcial | OTP robusto; login sin guard real (ver A01) |
| A08 Integridad de software/datos | 🟢 Cubierto | HMAC webhook, uuid verificable, auditoría |
| A09 Logging/monitoreo | 🟢 Cubierto (MVP) | Logs estructurados + auditoría; sin SIEM |
| A10 SSRF | 🟢 Bajo inherente | Sin URLs provistas por el cliente |

## A01 — Control de acceso roto 🔴

**Hallazgo principal.** Ninguna ruta de `/api` exige autenticación: las dependencias (`Depends`) solo inyectan sesión de BD y servicios. `POST /api/auth/login` emite una sesión que la UI usa, pero el backend **no la verifica en ningún endpoint**: quien alcance la red puede crear solicitudes, evaluar, seleccionar ofertas, ver auditoría y evidencias, y registrar desembolsos.

El propio manual de integración lo advierte: *"No exponerlos a Internet ni entregar credenciales de integración como si ya hubiera control de acceso."*

**Mitigaciones actuales**: despliegue en red interna/VPN (MVP interno), rate limit por IP en mutadores, `Referrer-Policy: no-referrer` (no filtra uuid de firma ni tokens por Referer), evidencias por token de sesión de captura.

**Requerido antes de exposición real**: auth por endpoint (JWT/sesión verificada), autorización por rol (asesor/admin/aliado) y scoping por aliado. Excepciones deliberadas que deben seguir públicas: `/api/health`, `/api/verificar-firma/{uuid}`, `/api/evidencias/captura/*` (token), `/api/auth/login`, `/webhook/desembolso` (HMAC en lugar de sesión).

## A02 — Fallas criptográficas 🟡

- **Cubierto**: OTP hasheado `SHA-256(codigo:id_solicitud)` — nunca en claro; firma HMAC-SHA256 del webhook; secreto por env, no en repo; TLS en borde de staging.
- **Pendiente**: cifrado en reposo de PII (evidencias, `consulta_buro.hdc_json`, `resultado_json` contienen datos de buró de terceros). Hoy la protección es el control de acceso a la BD — aceptable en MVP interno, insuficiente si la instancia se comparte.
- Passwords: credenciales demo vienen de env (`DEMO_USER_PASSWORD`); sin usuarios reales en BD todavía.

## A03 — Inyección 🟢

- SQL: todas las consultas van por SQLAlchemy ORM/expresiones parametrizadas; el único SQL literal (`schema.sql`, migraciones) no concatena entrada.
- Payloads: DTOs Pydantic estrictos con `Field` constraints (`ge`, `max_length`, `pattern`) — D65.
- Evidencias servidas con `X-Content-Type-Options: nosniff` — un archivo malicioso no se interpreta como HTML/JS.
- XSS: React escapa salidas por defecto; la verificación de firma renderiza campos de BD sin HTML crudo.

## A04 — Diseño inseguro 🟢

- Idempotencia en mutaciones de dinero: desembolso síncrono y webhook reenvían seguro.
- Ciclo de estados con transiciones restringidas (rechazar solo sobre pendiente; evaluada no editable salvo rechazada).
- Pre-filtro SIMIT antes de gastar la consulta paga; hard rejects de HDC+ no consumen Valor Ingreso.
- Reuso de consulta a centrales con TTL — acota la retención de PII de terceros.

## A05 — Configuración insegura 🟡

- **Cubierto**: `SecurityHeadersMiddleware` (nosniff, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`); CORS por allowlist configurable (`cors_origin_list`), no `*` con credenciales; secretos por env; `.env` fuera del repo.
- **Pendiente**: `/api-docs`, `/redoc` y `/api/openapi.json` expuestos en producción — revelan el contrato completo; cerrar o proteger en despliegue real.

## A06 — Componentes vulnerables 🟢

CI corre `pip-audit -r backend/requirements.txt` y `npm audit --audit-level=high` en cada push (`.github/workflows/ci.yml`). Dependencias pineadas en `requirements.txt` y `package-lock.json`.

## A07 — Fallas de autenticación 🟡

- **OTP robusto**: hash con contexto, TTL (`OTP_TTL_MINUTOS`), consumo único, `OTP_MAX_INTENTOS`, reenvío invalida el anterior.
- **Login**: endpoint demo con credenciales por env; sin lockout por intentos (mitigado por rate limit global 30 mutadores/min/IP) — y sin verificación de sesión en rutas (A01).

## A08 — Integridad de software y datos 🟢

- Webhook: `X-Signature` HMAC-SHA256 de `timestamp.cuerpo` + ventana anti-replay — un evento capturado no es rejugable ni falsificable sin el secreto.
- Firma OTP verificable públicamente por uuid — el documento impreso se contrasta con el registro.
- Auditoría inmutable de evaluaciones (request/resultado + huella de parámetros) y `auditoria_cambio` por tabla.
- Migraciones Alembic versionadas; tests de integridad en CI.

## A09 — Logging y monitoreo 🟢 (MVP)

Logs estructurados JSON por dominio (`creditos.http`, `creditos.webhook`, `motor_decision.errores`) + access log middleware; decisiones y eventos de giro auditados en BD. Sin alertas/SIEM — aceptable en MVP interno; producción necesita destino y umbrales.

## A10 — SSRF 🟢

La app no construye peticiones salientes con URLs del cliente: Experian, Valor Ingreso, PlacaPi y datos.gov.co son endpoints fijos de configuración. Las evidencias se reciben como archivos, no como URLs a descargar. Riesgo inherente bajo.

## Hallazgos accionables (ordenados)

1. **A01 — auth por endpoint + autorización por rol/aliado.** Único bloqueante para exposición fuera de red interna. Públicos deliberados listados arriba.
2. **A02 — cifrado en reposo de PII** (evidencias, reportes de buró) o política de retención/supresión antes de producción.
3. **A05 — cerrar `/api-docs`, `/redoc`, `/api/openapi.json` en producción** (o detrás de auth).
4. **A07 — lockout/backoff en login** cuando existan usuarios reales (hoy rate limit global cubre fuerza bruta básica).
5. **A09 — destino de logs + alertas** (errores de webhook, rechazos de firma) en el despliegue real.

## Rendimiento (complemento del reporte)

Ver `BENCHMARK_MOTOR.md`: motor puro ~0.5 ms/evaluación (p99 2.5 ms), endpoint `/evaluar` ~33 ms p50 con persistencia completa. Guard anti-regresión en `tests/perf/test_benchmark_motor.py` (p95 < 500 ms motor / 1500 ms endpoint). La capacidad sobra por órdenes de magnitud a 70 créditos/día.
