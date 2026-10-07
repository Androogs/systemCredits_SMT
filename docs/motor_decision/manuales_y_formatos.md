# Formatos de entrada y alcance frente a los manuales

## Reportes que el motor entiende

El motor no acepta cualquier JSON. Los parsers de `backend/integrations/datacredito/parsers`
reconocen:

- **HDC+ (Historia de Crédito+)**: objeto `ReportHDCplus` (o su contenido raíz) con
  `productResult`, `models`, `productValueList`, `liabilities`, `CreditCardList`,
  `savings`, `checkingList`, `globalIndebtedness`, `alerts`.
- **Valor Ingreso**: respuesta con `numero_identificacion_persona_natural`,
  `respuesta_id`, `aportantes[].resultado_pagos`, `indicadores` y
  `resumen_general_ingresos` (de aquí sale `meses_continuidad`).

También se leen PDF que contengan ese JSON impreso (muestras del portal): se quitan
los encabezados y pies del navegador y se procesa en memoria.

Otro proveedor, versión o envoltura necesita un adaptador y ejemplos de esa variante.

## Material de referencia usado por los dos desarrolladores

BRD-Prefiltro_Cliente_InversionesPacifico (actualizado 9-sep-2026), BRD-IMPL-111350,
DICCIONARIO-IMPL-110912, HDC_Path_Campos_JSON_DHWS3, manuales REST de HDC+ y Valor
Ingreso, PPT v4 2026 Motor de Decisión y muestras HC/VI. Estos documentos no están en
el repositorio (contienen datos de clientes o son de uso restringido).

## Brechas conocidas

| # | Brecha | Estado |
|---|--------|--------|
| 1 | Parsers con estructura rígida, sin detección de versión | Abierta |
| 2 | Score sustituido si falta el modelo contratado | **Cerrada**: se usa `codigos_score` y no se sustituye |
| 3 | Calificación histórica: se usa la calificación actual de cada obligación, no la serie mensual de 12 meses | Abierta |
| 4 | Ingreso de independientes (Quanto vs. Valor Ingreso) | Resuelta por PPT v4; pendiente de certificar con negocio |
| 5 | Orientación del vector de comportamiento | Abierta (ver bitácora) |
| 6 | Campos HDC inválidos se convierten en 0 en el parser | Abierta |
| 7 | Parámetros versionados | **Mejorada**: cada evaluación guarda `parametros_usados` en la auditoría |
| 8 | Trazabilidad por regla | **Cerrada**: `trazabilidad` por etapa con causales y detalle |
| 9 | Identidad de solicitud vs. reportes | **Cerrada**: se valida en API y CLI |

## Manejo de archivos y datos personales

- No subir al repositorio reportes reales, solicitudes con cédulas reales, `.env` ni
  bases de datos (`.gitignore` ya lo excluye).
- La auditoría guarda la solicitud y el resultado, **no** las respuestas completas del
  buró.
- Tratamiento conforme a la Ley 1581 de 2012 y a la autorización de consulta en
  centrales de riesgo del cliente.
