# Manual de integración para aliados

**Producto:** Plataforma de originación de crédito — Inversiones Pacífico  
**Versión del contrato documentado:** API actual del repositorio  
**Estado:** Guía técnica preliminar para integración mediada por la plataforma; no sustituye un acuerdo comercial, un contrato de API firmado ni una certificación de seguridad.

## 1. Propósito y alcance

Este manual describe cómo un sistema aliado puede consultar el catálogo publicado por la plataforma y cómo los servicios autorizados de la plataforma registran solicitudes, generan ofertas, seleccionan una oferta y registran un desembolso.

La implementación vigente es una API REST FastAPI bajo el prefijo `/api`. El aliado no se conecta directamente a Experian: la consulta de buró y la evaluación son responsabilidades de la plataforma.

### Importante: capacidades que todavía no existen

- No existe endpoint para que un aliado se registre, gestione sus usuarios, cree productos o edite reglas de elegibilidad. El catálogo lo configura el equipo operador en la base de datos y se publica mediante migraciones/siembra.
- No existe autenticación/autorización de API implementada en las rutas descritas. Los endpoints de solicitudes exponen datos personales y operaciones de crédito. **No exponerlos a Internet ni entregar credenciales de integración como si ya hubiera control de acceso.** Antes de una integración real, el equipo de plataforma debe definir y desplegar autenticación, autorización por aliado, transporte seguro, auditoría y política de secretos.
- No existe webhook, callback ni evento saliente para notificar al aliado cambios de estado, decisión, oferta o desembolso.
- La plataforma genera ofertas desde el catálogo activo y reglas almacenadas; no consulta en tiempo real un motor externo del aliado.
- La API tiene ambientes de configuración `demo` y `produccion`; no hay selector explícito de UAT para Experian. No enviar credenciales reales a través de este manual, tickets o chats.

## 2. Ambientes y direcciones

Usar la URL base que asigne el equipo de plataforma. No usar el valor ficticio de ejemplo en una integración desplegada.

```text
Desarrollo local:  http://localhost:8000
Staging:           https://<host-staging-asignado>
Producción:        https://<host-produccion-asignado>
Prefijo API:       <base-url>/api
OpenAPI interactivo: <base-url>/api-docs
```

Verificar disponibilidad:

```http
GET /api/health
```

Respuesta actual:

```json
{
  "status": "ok",
  "environment": "demo",
  "version": "1.0.0"
}
```

`/api/health` confirma que la aplicación responde; en la implementación actual no certifica por sí solo que PostgreSQL, Experian u otras dependencias estén disponibles.

## 3. Convenciones HTTP

- Codificación: JSON UTF-8.
- `Content-Type: application/json` en solicitudes con cuerpo JSON.
- Fechas de nacimiento: `YYYY-MM-DD`.
- Identificadores de solicitud: UUID.
- Montos: COP, decimales JSON; las respuestas pueden serializar decimales como strings.
- Tasas: porcentaje mensual, no fracción decimal. Por ejemplo, `2.0` representa `2 %` mensual.
- Plazos: meses enteros.
- No enviar números de tarjeta, claves bancarias, contraseñas de Experian ni respuestas completas del buró salvo por el flujo explícito que las requiere.

Los endpoints documentados no requieren actualmente un header `Authorization` porque no hay autenticación de API implementada. Esto **no** significa que deban llamarse públicamente sin protección.

## 4. Catálogo de productos activos

### Consultar productos

```http
GET /api/productos
```

Devuelve únicamente productos activos cuyo aliado también esté activo:

```json
[
  {
    "id_aliado_producto": 1,
    "id_aliado": 1,
    "nombre": "Financiacion de motocicleta",
    "aliado": "INVERSIONES PACIFICO S.A.",
    "tasa_min": "1.5000",
    "tasa_max": "2.2000",
    "plazo_min_meses": 12,
    "plazo_max_meses": 48,
    "monto_min": "500000.00",
    "monto_max": "20000000.00"
  }
]
```

Los valores anteriores ilustran el seed actual del proyecto; no son una oferta comercial vigente ni una promesa de aprobación. Consultar siempre el catálogo del ambiente correspondiente.

El endpoint **no** publica el puntaje mínimo ni las reglas internas de elegibilidad. No inferir elegibilidad solo a partir de tasa, monto o plazo; la respuesta de oferta para una solicitud es la fuente de estado de elegibilidad.

## 5. Flujo funcional disponible

### Paso 1: registrar la solicitud

```http
POST /api/solicitudes
Content-Type: application/json
```

Ejemplo sintético:

```json
{
  "cliente": {
    "tipo_documento": "1",
    "num_cedula": "1000000000",
    "nombre_completo": "EJEMPLO CLIENTE",
    "primer_apellido": "EJEMPLO",
    "fecha_nacimiento": "1990-05-20",
    "ocupacion": "Empleado",
    "nacionalidad": "Colombia"
  },
  "datos_laborales": {
    "tipo_contrato": "Indefinido",
    "meses_continuidad": 24,
    "ingreso_mensual": 3500000,
    "otros_ingresos": 0,
    "anios_camara_comercio": null
  },
  "contacto_vivienda": {
    "estrato": 3,
    "personas_a_cargo": 1,
    "tipo_vivienda": "Arrendada"
  },
  "moneda": "COP",
  "linea_credito": "Motocicleta",
  "destino_credito": "Motocicleta",
  "plazo_deseado_meses": 36
}
```

Tipos de documento (`tipo_documento`) se envían como códigos de la API:

| Código | Tipo |
|---|---|
| `"1"` | CC |
| `"2"` | NIT |
| `"3"` | PJE |
| `"4"` | CE |
| `"5"` | PAS |
| `"6"` | PPT |
| `"7"` | TI |
| `"8"` | DNI |
| `"9"` | PEP |

Ocupaciones admitidas: `Empleado`, `Independiente`, `Pensionado`, `Fuerzas Militares`. Tipos de contrato admitidos: `Indefinido`, `Fijo`, `Obra o Labor`, `NA`; `tipo_contrato` puede ser `null`.

Respuesta `201 Created`:

```json
{
  "id_solicitud": "UUID",
  "num_solicitud": 123,
  "estado": "creada"
}
```

Guardar `id_solicitud` para las operaciones siguientes. `num_solicitud` puede ser `null` en bases de prueba que no implementen la secuencia del esquema de producción.

**Idempotencia:** el endpoint no acepta actualmente una clave de idempotencia. No reintentar una creación tras timeout sin reconciliar antes si la solicitud se registró; `num_cedula` es único para el cliente, pero ello no hace idempotente la creación de solicitudes.

### Paso 2: solicitar evaluación

```http
POST /api/solicitudes/{id_solicitud}/evaluar
Content-Type: application/json
```

Ejemplo para el entorno demo:

```json
{
  "saldo_financiar": 8000000,
  "plazo": 36,
  "tasa": 2.0,
  "primer_apellido": "EJEMPLO",
  "tiene_multas_runt": false,
  "consultar_experian": false,
  "escenario_mock": "aprobado"
}
```

`saldo_financiar` debe ser mayor que cero; `plazo` debe ser un entero mayor que cero; `tasa` es la tasa mensual expresada como porcentaje y no puede ser negativa. `primer_apellido` puede omitirse solo si ya está guardado en los datos del cliente.

`escenario_mock` se usa exclusivamente para pruebas con `ENVIRONMENT=demo`; el catálogo disponible puede consultarse mediante `GET /api/motor/escenarios`. No enviar escenarios mock en UAT ni producción.

Para una consulta online, el cliente de plataforma debe acordar con el operador el ambiente correcto y las credenciales almacenadas de manera segura. El request habilita la consulta mediante `consultar_experian: true`; no enviar credenciales de Experian dentro del JSON. La configuración actual de backend selecciona `demo` o `produccion`, no UAT.

La respuesta incluye `decision` pública (`Aprobado` o `Rechazado`), `decision_interna`, causales, datos de evaluación e identificador de evaluación. No asumir que un valor de decisión interna `Estudio` o `Requiere Codeudor` equivale a aprobación; la decisión pública es binaria. La plataforma genera ofertas automáticamente solo cuando la decisión pública es `Aprobado` y hay productos activos configurados.

### Paso 3: consultar ofertas de una solicitud

```http
GET /api/solicitudes/{id_solicitud}/ofertas
```

Ejemplo de respuesta:

```json
[
  {
    "id_oferta": 45,
    "id_aliado_producto": 1,
    "elegible": true,
    "motivo_no_elegible": null,
    "seleccionada": false,
    "tasa_ofrecida": "1.5000",
    "plazo_ofrecido": 36,
    "cuota_mensual": "289000.00",
    "monto_aprobado": "8000000.00"
  },
  {
    "id_oferta": 46,
    "id_aliado_producto": 2,
    "elegible": false,
    "motivo_no_elegible": "score >= 650 (valor actual: 620)",
    "seleccionada": false,
    "tasa_ofrecida": null,
    "plazo_ofrecido": null,
    "cuota_mensual": null,
    "monto_aprobado": null
  }
]
```

Una respuesta vacía significa que no hay ofertas registradas para la solicitud; por ejemplo, puede no haber productos activos o no haberse generado todavía una aprobación. Una oferta inelegible contiene el motivo y no debe presentarse como aceptable.

Las ofertas se calculan a partir de los productos activos y sus reglas en la base de datos. Las reglas actuales soportan los campos `score`, `perfil_score`, `perfil_ingreso`, `ingreso_final`, `ingreso_final_smmlv`, `endeudamiento`, `capacidad_pago`, `cupo_sugerido`, `edad`, `ocupacion`, `monto_solicitado` y `plazo`; los operadores permitidos son `>=`, `<=`, `=`, `!=`, `IN` y `NOT IN`. La configuración de reglas no forma parte del API público actual.

### Paso 4: registrar la selección del cliente

```http
POST /api/solicitudes/{id_solicitud}/ofertas/seleccionar
Content-Type: application/json
```

```json
{
  "id_oferta": 45,
  "monto": 7500000,
  "plazo": 30
}
```

`monto` y `plazo` son opcionales; si se omiten se conserva el monto/plazo ofrecido. Si se envían, permiten tomar un monto menor o plazo más corto. No se permite superar la capacidad aprobada ni el plazo autorizado. Solo puede quedar una oferta seleccionada por solicitud; seleccionar otra desmarca la previa.

### Paso 5: registrar el desembolso

El endpoint actual permite al proceso operador registrar el desembolso una vez que la solicitud está aprobada y tiene una oferta seleccionada:

```http
POST /api/solicitudes/{id_solicitud}/desembolso
Content-Type: application/json
```

```json
{
  "codigo_ach_banco": "007",
  "numero_cuenta_cliente": "000123456789",
  "titular_cuenta": "EJEMPLO CLIENTE",
  "referencia_pago": "REF-ALIADO-0001",
  "vehiculo": {
    "producto_a_financiar": "Motocicleta",
    "marca": "Marca de prueba",
    "referencia": "Modelo de prueba",
    "modelo": "2026",
    "color": "Negro",
    "valor_moto_iva": 9000000
  }
}
```

`codigo_ach_banco` debe existir y estar activo en el catálogo. La cuenta receptora debe pertenecer al cliente y ser una cuenta de ahorros activa; si aún no está registrada, el flujo crea la cuenta asociada al cliente. El emisor se toma de la cuenta activa del aliado financiero propio configurado por la plataforma; no se proporciona como campo del request.

El registro es idempotente para un crédito que ya tiene desembolso: devuelve el desembolso existente y, si estaba pendiente, lo confirma. El response identifica `id_desembolso`, estado, capital, cuota, tasa, plazo, emisor/receptor y referencia de pago. Este endpoint no es una instrucción bancaria ni ejecuta una transferencia externa por sí solo; requiere que el proceso operativo confirme que el pago ocurrió.

## 6. Consulta y soporte

```http
GET /api/solicitudes?limite=50&offset=0
GET /api/solicitudes/{id_solicitud}
GET /api/bancos
```

- La lista permite filtrar con `estado`, `decision`, `busqueda`, `limite` y `offset`; el backend limita `limite` a 200.
- El detalle incluye datos de cliente, situación laboral, decisión, causales, ofertas y desembolso. Limitar este acceso a usuarios autorizados debido a que contiene información personal.
- `GET /api/bancos` devuelve bancos activos para cuenta receptora y el código ACH.

Contrato OpenAPI interactivo: `<base-url>/api-docs`. La especificación declarada por la aplicación es `<base-url>/api/openapi.json`.

## 7. Errores HTTP

| HTTP | Uso observado | Acción recomendada |
|---:|---|---|
| 201 | Solicitud creada o desembolso registrado | Guardar identificadores de la respuesta. |
| 200 | Consulta, evaluación u operación completada | Procesar el cuerpo según el endpoint. |
| 404 | Solicitud, evaluación u oferta inexistente | Verificar UUID/ID y que la oferta corresponda a esa solicitud. |
| 422 | JSON inválido, datos fuera de rango, identidad/datos faltantes, regla de negocio o solicitud no elegible | Leer el detalle, corregir datos; no reintentar sin cambios. |
| 501 | Regla de negocio pendiente de implementación | Contactar al operador de la plataforma; no reintentar como error transitorio. |
| 502 | Error del servicio de DataCrédito o credenciales/configuración externa faltantes | No repetir en bucle; contactar al operador de la plataforma. |
| 500 | Error interno no controlado | Reportar hora, endpoint e identificador de solicitud; nunca adjuntar secretos o respuestas de buró. |

Las validaciones estándar de FastAPI/Pydantic pueden responder con `{"detail": [...]}`. Las excepciones de negocio controladas usan `{"error": "<codigo>", "detail": "<mensaje>"}`.

No reintentar automáticamente solicitudes de creación, selección o desembolso tras un timeout sin consultar primero el estado mediante el UUID; solo el desembolso existente está expresamente implementado como idempotente.

## 8. Protección de datos y operación

- Usar exclusivamente datos sintéticos en desarrollo y demo.
- Tratar cédula, nombre, fecha de nacimiento, ingresos, decisión y cuenta bancaria como datos personales sensibles/confidenciales.
- Usar la información solo para la finalidad autorizada y conservarla según el acuerdo aplicable y la Ley 1581 de 2012.
- No guardar cuerpos de request/response con PII en logs del aliado. La auditoría del motor registra solicitud y resultado para trazabilidad; no guarda respuestas completas del buró.
- No enviar contraseñas, tokens OAuth, `client_secret`, números reales de cuenta o reportes de crédito por correo sin protección, tickets públicos, repositorios o chats.
- Exigir TLS en staging/producción.
- Hasta que exista autenticación/autorización por aliado y controles de privacidad validados, limitar las rutas de solicitudes a una red de confianza o mantenerlas deshabilitadas para integradores externos.
- El equipo de plataforma debe provisionar productos/reglas/cuentas del aliado y habilitar correctamente el catálogo; la API actual no permite al aliado gestionarlos.

## 9. Criterios de aceptación para una integración

1. El operador asignó base URL y ambiente, y confirmó acceso autenticado y autorizado para el aliado.
2. El ambiente tiene migraciones aplicadas y catálogos/cuentas correctamente provisionados.
3. `GET /api/health` responde; además se verificó la conexión real a base de datos mediante una prueba operativa, pues el health check actual no la valida.
4. `GET /api/productos` devuelve solamente los productos acordados.
5. Se recorrió el ciclo con un cliente y datos sintéticos: crear solicitud, evaluar, consultar ofertas, seleccionar y registrar desembolso de prueba.
6. Se probaron validaciones, identidad no coincidente, decisión no aprobada, oferta inelegible, UUID inexistente, timeout y reintentos.
7. El aliado confirmó manejo seguro de PII, acceso por rol, tiempos de retención y canal de soporte.
8. Si se requiere notificación push, onboarding autónomo o edición remota de productos, se acordó desarrollar primero esos contratos (webhooks/API de administración no están implementados).

## 10. Fuentes del contrato implementado

- [Rutas de solicitudes](../backend/routes/solicitud_routes.py)
- [Rutas de catálogo](../backend/routes/catalogo_routes.py)
- [Modelos de requests/responses](../backend/models/solicitud_models.py)
- [Servicio de solicitudes y ofertas](../backend/services/solicitud_service.py)
- [Elegibilidad de producto](../backend/services/elegibilidad_service.py)
- [Servicio de desembolso](../backend/services/desembolso_service.py)
- [Esquema y restricciones de base de datos](../backend/database/schema.sql)
- [Especificación OpenAPI del proyecto](./openapi.yaml)
