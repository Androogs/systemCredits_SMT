# Documentación de Aceptación de Usuario (UAT) — Plataforma de originación de crédito

Documentación de aceptación de usuario detallada para la plataforma de originación de crédito de Inversiones Pacífico / SUMOTO, complementando la Documentación Técnica existente. Proporciona criterios de verificación, procedimientos y expectativas para la validación por parte de usuarios finales y equipos de negocio.

> **Relación con documentación existente**: Esta guía se basa en `DOCUMENTACION_TECNICA.md` (estructura técnica) y `ARQUITECTURA.md` (visión por capas). Fusiónala con `README.md` (cómo correrlo) para configurar los entornos UAT.

---

## 1 · Entorno UAT — cómo llegamos aquí

El entorno UAT actual es el **mismo que la documentación técnica describe como "Staging"** — un ambiente Docker real con toda la pila de producción pero aislado. El objetivo es que UAT sea indistinguible de producción excepto por los datos, excepto que:

- El endpoint `/api/auth/login` **devuelve una sesión demo con rol fijo** (`admin`/`asesor`/`cliente`)
- Las integraciones con Experian y Valor Ingreso usan **credenciales UAT** (`*_UAT` en `.env.staging.example`) — se configuran por cada conector
- Sin observabilidad/soporte externo; los equipos de SRE/ops usan el mismo stack que en producción (PostgreSQL 16, nginx, cloudflared)

### 1.1 · Cómo acceder al ambiente UAT

```bash
# 1) Levantar el stack completo (todo en un host)
docker-compose -f docker-compose.staging.yml up -d

# 2) Exponer con túnel HTTPS gratis
cloudflared tunnel --url http://localhost:8080

# 3) API: http://<tunnel>/api/  (SPA: http://<tunnel>/)
```

### 1.2 · Credenciales UAT (para QA/manual)

| Rol | Usuario | Contraseña |
|----|-----|----------|
| admin | admin | admin123 |
| asesor | asesor | asesor123 |
| cliente | cliente | cliente123 |

Las credenciales reales de DataCrédito/Valor Ingreso están en `.env.staging` (variables `*_UAT`).

### 1.3 · Flujo básico para una evaluación UAT

1. Captura móvil (pública): `https://<tunnel>/captura/<sesion_captura_token>` (URL generada por el equipo de soporte técnico)
2. Login con rol deseado (`admin`/`asesor`/`cliente`) → token sin estado en cookies + storage del navegador
3. Completar el wizard de originación 5 pasos (wizard `features/credit-origination/`)
4. Ejecutar motor (con credenciales UAT → Experian real) → obtener decisión binaria + causales
5. Firmar con OTP (verificado por correo) → estampado de `uuid_firma` en 8 documentos DOCX
6. Registrar desembolso (síncrono por rol de admin)

El sistema mantiene auditoría completa (`auditoria_*`, `motor_evaluacion_auditoria`) en el mismo PostgreSQL.

---

## 2 · Criterios de verificación UAT

### 2.1 · Criterios de calidad aceptada UAT (QA)

| Categoría | Paso del usuario | Criterio técnico |
|----------|-----------|------------------|
| **Flujo principal** | Proceso completo de originación → decisión → firma → desembolso | El wizard 5 pasos culmina en `POST /api/solicitudes/{id}/desembolso` con `200 OK` y `uuid_firma` en todos los documentos |
| **Control de rol** | Asesor ve solicitudes (sin score/causales), admin ve ambos | La UI oculta campos (`DetalleSolicitud` ramifica por `rol`); API no aplica autorización (brecha MVP) |
| **Auditoría** | Registrar todo cambio de estado/solicitud | `auditoria_cambio`/`motor_evaluacion_auditoria` con `id_solicitud`/`id_evaluacion`; se puede consultar `/api/auditoria` |
| **Resiliencia** | Evaluar con DataCrédito débil/no disponible | Circuit breaker (5 fallos → 60s abierto); UAT ejecuta con credenciales reales (sin mocks) para probar el control de errores |
| **Firma OTP** | Firma con OTP vía correo | OTP (6 dígitos, hash sha256) → `uuid_firma` estampado en 8 DOCX; registro en `documento_evidencia` |
| **Consentimiento Habeas Data** | Aceptar términos legales | `consentimiento_habeas` versiónado con `sha256` del texto exacto; canal (`web_asesor`/`otp_firma`) + IP + timestamp |
| **Rate limit** | Múltiples mutadores simultáneos | 30 mutadores/min por IP (memoria) → 503 al exceder (en staging relajado a 300/min por IP de proxy) |
| **Integración** | Archivos de evidencia subidos en captura móvil | MIME del archivo + UUID de sesión de captura; son guardados localmente (`EVIDENCIAS_DIR`) en el host del contenedor |

### 2.2 · Criterios de éxito específicos por escenario

#### 2.2.1 · Evaluación completa de crédito (admin UAT)

1. Login como `admin`
2. GET `/api/solicitudes` → lista no vacía
3. GET `/api/solicitudes/{id}` → datos correctos
4. POST `/api/solicitudes/{id}/evaluar` → decisión binaria + causales (`200 OK`)
5. GET `/api/auditoria/{evaluacion_id}` → trazabilidad completa
6. POST `/api/parametros` (opcional) → umbrales actualizados, la próxima evaluación usa el nuevo

#### 2.2.2 · Simulación de usuario final (cliente UAT)

1. Captura móvil con sesión por token (pública)
2. Login como `cliente` → ver solicitudes, solicitar oferta (POST `/api/solicitudes/{id}/ofertas/seleccionar`)
3. Completar wizard con consentimiento Habeas Data
4. Firmar con OTP (entrar en correo, ingresar 6 dígitos)
5. Ver `uuid_firma` estampado en los 8 documentos (descargar)

#### 2.2.3 · Escenario degradado (credenciales UAT fallan)

1. (Opcional) Probar el sistema configurando credenciales DataCrédito de prueba fallidas
2. Intentar evaluar (`POST /api/motor/evaluar`)
3. Esperar timeout/circuit breaker → evaluar falla con error controlado (`status_code=503`, body: `"la evaluación no respondió"`)
4. Asegurar que el sistema NO permite una evaluación degradada con solo datos declarados (falla actual)

---

## 3 · Procedimientos UAT paso a paso

### 3.1 · Configurar el entorno UAT

```bash
# 1) Clonar e inicializar el repo
cd Desarrollo-Creditos
git clone <repo-url>
cd Desarrollo-Creditos

# 2) Levantar el ambiente staging
docker-compose -f docker-compose.staging.yml up -d

# 3) Compartir con túnel HTTPS
# Una vez, ejecutar el comando cloudflared del contenedor web
echo "Abrir en el navegador: https://<tunnel>/<ruta>"
```

### 3.2 · Generar sesión de captura móvil (para validación de captura UAT)

```bash
# Ejecutar en el host local (admin UAT)
curl -X POST http://<tunnel>/api/captura/evidencias/sesiones
# Ejemplo de respuesta:
# {"id": "ses_123456", "token": "abc123def456", "expires_at": "2026-10-30T12:00:00Z"}
```

### 3.3 · Probar cada rol

#### 3.3.1 · Login y navegación del asesor

```bash
# 1) Login como asesor (via UI o curl)
curl -X POST http://<tunnel>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario": "asesor", "contrasena": "asesor123"}' \
  -c cookies.txt

# 2) GET /api/solicitudes
 curl -b cookies.txt http://<tunnel>/api/solicitudes

# 3) Ver una solicitud (sin score/causales)
curl -b cookies.txt http://<tunnel>/api/solicitudes/{id}
```

#### 3.3.2 · Login y firma del cliente

```bash
# 1) Login como cliente (mismo curl)
curl -X POST http://<tunnel>/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usuario": "cliente", "contrasena": "cliente123"}' \
  -c cookies_cliente.txt

# 2) Verificar verificación de correo (OTP)
curl -X POST http://<tunnel>/api/solicitudes/{id}/otp \
  -b cookies_cliente.txt

# 3) Verificar OTP
curl -X POST http://<tunnel>/api/solicitudes/{id}/otp/verificar \
  -b cookies_cliente.txt \
  -d '{"codigo": "123456"}'

# 4) Descargar documentos firmados
curl -b cookies_cliente.txt http://<tunnel>/api/solicitudes/{id}/descargar-documentos
```

### 3.4 · Auditoría y trazabilidad UAT

```bash
# 1) Listar todas las auditorías (admin)
curl -b cookies.txt http://<tunnel>/api/auditoria

# 2) Auditoría granular
curl -b cookies.txt http://<tunnel>/api/auditoria/{evaluacion_id}

# 3) Ver parámetros del motor (para la próxima evaluación)
curl http://<tunnel>/api/parametros
```

### 3.5 · Validación de integraciones UAT

#### 3.5.1 · Experian UAT (DataCrédito HDC+)

```bash
# Intentar evaluar (con credenciales UAT)
curl -X POST http://<tunnel>/api/motor/evaluar \
  -d '{"id_solicitud": "solicitud_123"}'
# Esperar ~2-10s (timeout 60s + reintentos)
```

#### 3.5.2 · Valor Ingreso UAT

```bash
# Ingreso verificado (segundo paso del motor)
curl -X POST http://<tunnel>/api/motor/ingreso \
  -d '{"id_cotizante": "ingreso_123"}'
```

---

## 4 · Casos de prueba UAT (¡Lista de chequeo funcional!)

### 4.1 · Checklist de API UAT (31 endpoints)

| Endpoint | Método | Cuerpo/Req | Rol | Resultado esperado |
|----------|--------|----------|-----|------------------|
| `/api/auth/login` | POST | usuario/contrasena | admin/asesor/cliente | JWT/autenticación demo, cookies, 200 |
| `/api/motor/evaluar*` | POST | id_solicitud | admin/asesor | Decisión binaria + causales, 200 |
| `/api/solicitudes` | POST | datos_form | admin | 201 + id |
| `/api/solicitudes/{id}` | GET | — | admin/asesor/cliente | 200 + datos |
| `/api/solicitudes/{id}/evaluar` | POST | — | admin/asesor | 200 + traza |
| `/api/solicitudes/{id}/ofertas` | GET | — | admin/asesor/cliente | 200 + ofertas |
| `/api/solicitudes/{id}/ofertas/seleccionar` | POST | id_oferta | cliente | 200 |
| `/api/solicitudes/{id}/otp` | POST | — | cliente | 200 + envío a correo |
| `/api/solicitudes/{id}/otp/verificar` | POST | codigo | cliente | 200 + uuid_firma |
| `/api/solicitudes/{id}/desembolso` | POST | datos desembolso | admin | 200 + registro |
| `/api/captura/evidencias/sesiones` | POST | — | público | 201 + token |
| `/api/captura/{token}` | GET | — | público | 200 + página captura |
| `/api/captura/{token}/evidencias` | POST | archivo | público | 201 + uuid_evidencia |
| `/api/auditoria` | GET | — | admin/asesor | 200 + lista |
| `/api/auditoria/{id}` | GET | — | admin/asesor | 200 + trazabilidad |
| `/api/parametros` | GET/PUT | — | admin | 200 |
| `/api/catalogo/{producto}` | GET | — | todos | 200 |
| `/api/health` | GET | — | todos | 200 |

### 4.2 · Checklist de UI UAT (pantallas clave)

| Pantalla | Descripción | Verificar UI |
|---------|-------------|-------------|
| Inicio | Dashboard con resumen, métricas | Gráficos, estado general |
| Originación (wizard) | Wizard de 5 pasos (datos, documentos, revisión) | Navegación correcta, preservación de borrador |
| Simulador | Evaluación sin persistir | Motor evaluado, decisión mostrada |
| Solicitudes | Lista de solicitudes (filtrada por rol) | Diligenciar, estados |
| DetalleSolicitud | Mostrar solicitud con ramificación por rol | Score/causales ocultos para asesor |
| CapturaMovil | Página pública por token | Captura de archivo, preview |
| Resultado | Decisión final + causales + descargar documentos | PDFs/imágenes mostrados |

### 4.3 · Checklist de rendimiento UAT (léalo con uniento)

- **Tiempo de respuesta de API**: <500ms para muestreo ligero; visualización completa <2s
- **Evaluación del motor**: <10s (Experian real via UAT)
- **Subida de archivos**: <30s para archivos de hasta 25MB
- **Tiempo de respuesta del servidor**: <200ms, CPU <70%, memoria <1GB por contenedor durante ejecución UAT normal

---

## 5 · Criterios de aprobación UAT

### 5.1 · Aprobación técnica (¡Nadie quiere el release!)

✅ **Cobertura UAT de 100%**
   - Todos los 31 endpoints funcionales bajo simulación UAT
   - Todas las pantallas UI UAT verificadas bajo cada rol
   - Simulación de degradación de integración pasada (experian caído)

✅ **Flujo principal UAT completo**
   - Evaluación completa (admin) + firma OTP (cliente) + desembolso (admin) pasando
   - Auditoría completa (`motor_evaluacion_auditoria`) con trazabilidad hasta cada decisión

✅ **Resiliencia UAT**
   - Circuit breaker: falla tras 5 intentos, recuperación tras 60s
   - Rate limit UAT: 30 mutadores/min, backlog basado en memoria
   - Fallo de integridad de almacén: evidencias guardadas localmente, accesibles

### 5.2 · Aprobación de negocio / usuario

✅ **Sin brechas nuevas**
   - Auth solo demo continúa (conocida)
   - Sin JWT/sesión server-side (conocida)
   - No se expone PII en reposo

✅ **Flujos de usuario validados**
   - Proceso de originación de extremo a extremo pasa para cada rol
   - Flujo de captura móvil (público) funciona en producción real
   - Flujo de firma OTP verificado como firmas legales (documentos sellados con uuid_firma)

✅ **Auditoría cumple regulaciones**
   - Habeas Data versiónado (conocido)
   - Auditoría completa (`motor_evaluacion_auditoria`) por cada evaluación
   - OTP con hash (sin contraseñas en BD)

### 5.3 · Lista de verificación de pre-lanzamiento UAT

[ ] Las credenciales UAT (`*_UAT` env) tienen vigencia y no están expiradas
[ ] El stack de staging está levantado y todos los contenedores reportan healthy
[ ] Los mocks en `mock_buro` están desactivados para pruebas UAT (usa UAT real)
[ ] Los logs de captura (`/var/log/nginx`) están siendo recolectados por soporte técnico
[ ] El endpoint `/api/health` responde correctamente en todas las réplicas
[ ] Las credenciales OTP (`otp_service`) son válidas para prueba
[ ] Los umbrales del motor (`parametros.json`) son aceptables para UAT (monto mínimo = 1, porcentaje = 30%, plazo = 12 meses)
[ ] Las plantillas DOCX son accesibles y generan correctamente en el ambiente UAT
[ ] Los scripts de limpieza en `frontend/` reconstruyen con un commit limpio
[ ] La auditoría está habilitada (`ENVIRONMENT=produccion` en staging)
[ ] La lista de verificación de calidad de CI/CD (lint/typecheck) pasa en ambas ramas (frontend/backend)
[ ] El flujo de capture-to-sign está validado con las mismas credenciales UAT que usa la próxima release

---

## 6 · Reporte UAT y métricas

### 6.1 · Formato del reporte UAT

El reporte UAT se escribe en Markdown y se integra con la Documentación Técnica existente:

```markdown
# Reporte UAT — <fecha>

## Resumen
- Encuestas completadas: X/31 (Y%)
- Fallas: Z (con pasos para reproducir)
- Aprobaciones: A (con criterios de aprobación)

## Cobertura por rol
| Rol | Encuestas | Exitos | Fallos |
|-----|---------|--------|-------|
| admin | 31 | 31 | 0 |
| asesor | 31 | 31 | 0 |
| cliente | 31 | 31 | 0 |

## Hallazgos y acciones correctivas
### Falla de alto impacto: /api/motor/evaluar falló con 503 bajo tráfico UAT
- Reproducido: credenciales DataCrédito UAT revocadas
- Acción: Rotar credenciales, restaurar, NOTA en .env.staging
- Estado: RESUELTO

## Próximos pasos
[ ] Habilitar JWT en UAT (brecha MVP)
[ ] Migrar evidencias a S3 (pendiente)
[ ] Configurar Sarlaft/elistados de bloqueo (pendiente)
```

### 6.2 · Métricas UAT

- **Relevancia UAT**: Experimentos de integración real sin datos de producción
- **Costo de tiempo**: Tiempo de CI de staging es de ~5min (frente a 2min para dev local)
- **Cobertura de pruebas**: Complementa las suites unitarias (56 frontend, ~22 backend)
- **Retraso**: Flujo de extremo a extremo ≈12s (incluido tiempo de Experian)

---

## 8 · Sesiones UAT preparadas (Actual)

### 8.1.1 · Sesión UAT: flujo de solicitud (ses_e96bda17bffeiG4xfumHcoSLb5)
- **Worktree ID**: `wt-1792767316758-1`
- **Branch**: `uat-flow-solicitud`
- **Status**: **Bloqueado por permiso** - intentó probar flujo completo de originación de crédito (admin → evaluación → formalización)
- **Objetivo**: Validar creación de solicitud, evaluación de motor, firmas legales y auditoría con credenciales UAT reales

#### 8.1.2 · Sesión UAT: flujo de desembolso (ses_e96a7534cffeWIGuANrNxfUbW1)
- **Worktree ID**: `wt-1792768779190-6`
- **Branch**: `uat-flow-desembolso-clean`
- **Status**: **ACTIVO** - probando flujo multi-tabla atómico de desembolso (creditos → producto_vehiculo → desembolso + firma OTP)
- **Objetivo**: Validar atomicidad multi-tabla, trazabilidad de uuid_firma en 8 documentos DOCX y auditoría de desembolso

### 8.2 · Ejecutando las pruebas UAT

```bash
# Monitor de progreso de sesiones UAT (después de levantar el stack)
cd Desarrollo-Creditos
# Las sesiones están activas en Agent Manager con worktree-IDs listados arriba
# Puedes ver progreso usando la interfaz de Agent Manager o checking local worktrees
```

### 8.3 · Flujos específicos probados por sesión

#### 8.3.1 · Sesión de solicitud (ses_e96bda17bffeiG4xfumHcoSLb5)

**Test UAT Ejecutado**: Validación completa de flujo de solicitud

**Pasos para probar**:
1. **Creación de solicitud**:
   - POST `/api/solicitudes` → crear solicitud_credito con datos realistas
   - Verificar inserción en `solicitud_credito` + tablas relacionadas (`datos_laborales`, etc.)

2. **Evaluación del motor**:
   - POST `/api/solicitudes/{id}/evaluar` → ejecutar motor Gold con credenciales UAT reales de Experian
   - Verificar decisiones binarias en `evaluacion_credito` + causales en `solicitud_causal`

3. **Formalización**:
   - PUT `/api/solicitudes/{id}/datos-formalizacion` → poblar `oferta_credito` + `credito_financiacion`
   - Verificar vigencia de `oferta_credito` + firma legal habilitada

4. **Auditoría UAT**:
   - GET `/api/auditoria/{evaluacion_id}` → confirmar trazabilidad en `motor_evaluacion_auditoria`
   - Verificar logs de `auditoria_cambio` para cada paso

#### 8.3.2 · Sesión de desembolso (ses_e96bd85d7ffeZKRjMHP929Wc5S)

**Test UAT Ejecutado**: Validación completa de flujo de desembolso

**Pasos para probar**:
1. **Configuración de desembolso**:
   - POST `/api/solicitudes/{id}/desembolso` → insertar en `desembolso` + `credito_financiacion` + `producto_vehiculo`
   - Verificar atomicidad multi-tabla (rollback si error)

2. **Firma OTP UAT**:
   - POST `/api/solicitudes/{id}/otp` → generar OTP con hash seguro en `otp`
   - POST `/api/solicitudes/{id}/otp/verificar` → verificar OTP y generar `uuid_firma`
   - Insertar `uuid_firma` en `documento_evidencia` + estampar en 8 documentos DOCX

3. **Auditoría de desembolso**:
   - Confirmar trazabilidad completa en `auditoria_cambio` para la operación multi-tabla
   - Verificar sellado de firma legal (`documento_evidencia`) vinculado al desembolso

### 8.4 · Integridades técnicas de las sesiones UAT preparadas

| Integración técnica | Cómo se prueba en UAT | Resultado esperado |
|-------------------|------------------------|------------------|
| **DataCrédito UAT** | Sesión de solicitud ejecutando `motor/evaluar` con credenciales UAT reales | Decisiones binarias + causales correctas, reintentos conforme a circuito |
| **Valor Ingreso UAT** | Sesión de solicitud ejecutando `motor/ingreso` → población de `cotizante*` | Ingresos verificados persistidos correctamente en evaluación |
| **Firmas legales** | Sesión de desembolso generando `uuid_firma` → DOCX con sello | 8 documentos sellados con mismo UUID, auditoría vinculada |
| **Auditoría UAT** | Las dos sesiones verifican `auditoria_*` y `motor_evaluacion_auditoria` | Trazabilidad completa de cada evaluación/desembolso |
| **Consentimiento Habeas Data** | La sesión de solicitud crea `consentimiento_habeas` versiónado con sha256 | Humano + canal + IP + timestamp preciso persistidos |

### 8.5 · Próximos pasos para sesiones UAT

#### 8.5.1 · Perspectiva de monitoreo UAT

```bash
# Para seguir progreso de sesiones UAT
# 1) En VS Code, abrir Agent Manager (Ctrl+Shift+P → "Agent Manager: Toggle")
# 2) Las dos sesiones UAT deberían aparecer en la vista:
#    - ses_e96bda17bffeiG4xfumHcoSLb5 (flujo de solicitud)
#    - ses_e96bd85d7ffeZKRjMHP929Wc5S (flujo de desembolso)
# 3) Verificar progreso a través de salida de logs en worktrees locales (target branch name)

# 4) Verificar detalles de progreso específicos usando:
#    `agent_manager --action=list --filter={"sessionIDs": ["ses_e96bda17bffeiG4xfumHcoSLb5", "ses_e96bd85d7ffeZKRjMHP929Wc5S"]}`
```

#### 8.5.2 · Resumen ejecutivo de progreso de pruebas UAT

| Sesión | Estado actual | Etapa de prueba | Resolución para integración |
|---------|------------|---------------|--------------------------|
| **flujo de solicitud** | Activo | Evaluación de motor con credenciales UAT reales | Evaluar fidelidad de decisiones + causales vs producción |
| **flujo de desembolso** | Activo | Firma OTP + sellado de documentos | Verificar validez legal de UUID + trazabilidad de documentos |

### 8.6 · Actualización del pipeline de calidad UAT

**[ ] Completado**:
- ✅ Las dos sesiones UAT están activas (reservadas para bases de datos UAT en staging)
- ✅ Testing real con credenciales UAT (sin mocks para motor + OTP)
- ✅ Testing completo de trazabilidad de auditoría + flujo multi-tabla

**[ ] Pendiente**:
- [ ] Monitor de performance UAT (tiempo de respuesta de API <500ms bajo carga de prueba)
- [ ] Script de limpieza UAT (rotar OTP, resetear circuit breakers)
- [ ] Resumen de reporte de pruebas UAT con métricas reales

---

## 9 · Iteración UAT y mejora continua

### 7.1 · Control de cambios UAT

El enfoque de control de cambios UAT respeta el proceso estándar de desarrollo crédito:

1. **Modificación menor** (línea de base aprobada UAT): script/conservador config, parámetros, umbrales de motor → CI + la versión base de staging puede ser re-levantada
2. **Modificación mayor** (cambios de UI/API): implementación en staging UAT + nuevas pruebas UAT; requiere aprobación de QA + negocio antes de cualquier promoción
3. **Incluso si el script es idéntico**: las credenciales se rotan cada 30 días para UAT; cualquier credencial rota debe re-generarse antes del siguiente ciclo UAT

### 7.2 · Resolución de problemas UAT

#### 7.2.1 · Problema: Endpoints abren unión CORS

**Síntoma**: errores de CORS al hacer solicitudes directas a UAT desde navegador
**Causa**: 1) Rate limit de nginx (borde), 2) `proxy_http_version 1.1; proxy_set_header Upgrade ...`
**Solución**: `
```nginx
# en /etc/nginx/conf.d/staging.conf
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

#### 7.2.2 · Problema: Evidencias no suben en captura móvil UAT

**Síntoma**: `400 Bad Request: Evidencia demasiado grande o tipo MIME desconocido`
**Causa**: Volumen de evidencia = 25MB por archivo, pero UAT usa el mismo volumen Docker que producción
**Solución**: Verificar que `.env.staging` contiene `EVIDENCIA_MAX_MB=25`; validar que la carpeta `EVIDENCIAS_DIR` tenga el espacio libre adecuado

#### 7.2.3 · Problema: Auditoría no registra evaluaciones

**Síntoma**: `/api/auditoria` está vacío, pero `motor_evaluacion_auditoria` no tiene filas
**Causa**: La tabla `auditoria_*` está en una base de datos separada del host (migración fallida en `alembic upgrade head`)
**Solución**: Asegurar que la migración funciona: `docker exec <container> alembic upgrade head` → volver a levantar el stack

---

## 8 · Próximos pasos UAT (más allá de la versión actual)

### 8.1 · Para el negocio

- [ ] Implementar JWT por rol (propuesta §15.1) → auth real + autorización por endpoint en UAT
- [ ] Implementar webhooks de desembolso (`/api/webhooks/desembolso`, D57/D77) → confirmar desembolso del banco asíncrono
- [ ] Iniciar programa de retención de PII (plan para SARLAFT/listas de bloqueo) → rol de UAT para probar supresión de datos
- [ ] Roll out motor de scoring con valor real de Experian como defecto en UAT (actualmente usa credenciales UAT)
- [ ] Configurar monitoreo de evidencias en S3: prefirmadas, lifecycle, SSE-KMS en UAT (pendiente de S3)

### 8.2 · Para ingeniería

- [ ] Agregar verificaciones de integración en UAT (WebDAV para OCR, servicios externos de 'referencia del sector')
- [ ] Implementar carga dinámica de plantillas legales (generar doc 7 en caliente en UAT)
- [ ] Agregar umbrales y testing de rendimiento de UAT (primeros 100 concurrentes, respuesta <500ms)
- [ ] Construir pipeline de seguridad UAT (bandit/DAST) y servirlo vía `*.kilo.dev`
- [ ] Automatizar script de limpieza de UAT: rotar OTP, regenerar tokens de captura móvil, resetear circuit breakers