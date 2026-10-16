# Roles y alcance — plataforma de originación

Propuesta de modelo de acceso para cuando se implemente autenticación real
(JWT + autorización). Hoy la sesión solo distingue `asesor` /
`administrador` de forma local; este documento define los roles objetivo
para una operación multi-concesionario + financiera.

## 1. Modelo de tenancy

Dos tipos de organización (`tenant`):

- **Financiera** — Inversiones Pacífico / SUMOTO (una sola).
- **Concesionario aliado** — uno por dealer (Suzuki Palmira, Bajaj Tuluá,
  Hero Cali, …). Cada concesionario tiene sus propios trabajadores.

Regla de segregación: **los datos de una solicitud pertenecen al
concesionario que la radicó**. Nadie de otro concesionario la ve; la
financiera las ve todas.

Implicación técnica: `solicitud_credito` necesita `id_concesionario`
(NOT NULL) y `usuario.id_concesionario` para filtrar cada consulta por
el tenant del token. Los listados (`GET /solicitudes`, panel asesor,
reportes) aplican el filtro siempre server-side —
nunca por parámetro del cliente.

## 2. Roles propuestos

### Financiera

| Rol | Alcance |
|---|---|
| `admin_financiera` | Todo: configura productos/tasas/catálogos, concesionarios y usuarios; ve score, causales, indicadores de buró, auditoría y trazabilidad; re-evalúa con otros parámetros desde el detalle (la "reapertura" de una solicitud rechazada); confirma desembolsos. |
| `analista` | Consulta solicitudes de todos los concesionarios, ve evaluación y auditoría. Sin acciones de negocio (no re-evalúa, no desembolsa). |

> **Sin comité**: la decisión visible es binaria (aprobado/rechazado).
> Las causales internas de estudio/codeudor del motor se presentan como
> rechazo; la alternativa aprobatoria es la re-evaluación del admin con
> otros parámetros, no una resolución manual por comité.

Lo que la financiera **no** necesita: el wizard de originación de 5
pasos ni el simulador operativo (los puede ver, pero su herramienta es
el panel de solicitudes/detalle). La formalización la inicia el asesor;
la financiera solo confirma el desembolso.

### Concesionario

| Rol | Alcance |
|---|---|
| `admin_concesionario` | Gestiona los asesores de su dealer; ve todas las solicitudes de **su** concesionario con decisión binaria y estado; reportes propios. No ve score, causales ni buró (dato sensible del cliente). |
| `asesor` | Wizard de originación completo: radica, captura evidencias, ve resultado binario, reabre una solicitud rechazada corrigiendo datos, formaliza la oferta capturando el vehículo (con firma OTP del pagaré). Solo sus propias solicitudes (o las de su dealer en modo lectura si se define). |

## 3. Matriz permiso × funcionalidad

| Funcionalidad | asesor | admin_conces. | analista | admin_fin. |
|---|---|---|---|---|
| Radicar solicitud (wizard) | ✅ | — | — | — |
| Resultado binario aprobado/rechazado | ✅ | ✅ | ✅ | ✅ |
| Reabrir rechazada (corregir datos) | ✅ | — | — | ✅ |
| Re-evaluar con parámetros | — | — | — | ✅ |
| Seleccionar oferta + datos vehículo | ✅ | — | — | ✅ |
| Firma OTP del pagaré (cliente) | ✅ | — | — | ✅ |
| Ver causales, score, buró, trazabilidad | — | — | ✅ | ✅ |
| Registrar desembolso | — | — | — | ✅ |
| Gestionar usuarios/concesionarios | — | su dealer | — | ✅ |
| Ver solicitudes de otros dealers | — | — | ✅ | ✅ |
| Configurar productos/tasas/políticas | — | — | — | ✅ |

## 4. Permisos atómicos (backend)

Los roles se traducen a scopes del JWT; el middleware verifica scope
por endpoint, no por nombre de rol:

- `solicitud:crear`, `solicitud:leer:propias`, `solicitud:leer:tenant`,
  `solicitud:leer:global`
- `evaluacion:ejecutar`, `evaluacion:parametros`
- `evaluacion:parametros` (reapertura/re-evaluación del admin)
- `oferta:seleccionar`, `desembolso:registrar`
- `datos:sensibles` (score/causales/buró/auditoría)
- `catalogo:administrar`, `usuario:administrar`

## 5. Implementación por fases sugerida

1. **Auth**: JWT con `rol`, `id_usuario`, `id_concesionario` (null para
   financiera). Middleware de scope por endpoint.
2. **Segregación**: columna `id_concesionario` en `solicitud_credito` +
   filtro en `SolicitudRepository` (listar/detalle/evaluar/resolver).
3. **UI**: el switch local `asesor/administrador` se reemplaza por el
   rol del token; las vistas ya están separadas por `useRol`.
4. **Usuarios**: `Ajustes` ya tiene el formulario de usuarios con
   concesionario — se conecta al endpoint real de usuarios.

## 6. Nota sobre la tasa mostrada

La oferta muestra `aliado_producto.tasa_min` (1,5 % m.v. en el seed)
mientras el motor evalúa capacidad al 2 % y el simulador usa 2,16 %.
Definir la tasa comercial real del producto y alinear las tres fuentes
(un solo punto de verdad: el catálogo del producto).
