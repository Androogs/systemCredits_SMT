# Parámetros e insumos del motor de decisión

## 1. Objetivo y criterio de lectura

Este documento consolida los parámetros, datos de entrada, reglas, configuración técnica y dependencias necesarias para que el motor de decisión de Inversiones Pacífico funcione correctamente. Se elaboró contrastando los archivos de `Manuales/` con la implementación disponible al 2 de octubre de 2026.

No se declara una única fuente como definitiva cuando existen contradicciones. Cada diferencia se presenta como una brecha que debe resolver Negocio o el responsable funcional.

Estados usados:

- **Implementado:** el código lo ejecuta actualmente.
- **Documentado:** aparece en BRD, PPT o manuales, pero no necesariamente se ejecuta así.
- **Pendiente de confirmar:** hay contradicción, falta de evidencia o dependencia del contrato/configuración de Experian.

## 2. Fuentes revisadas

### 2.1 Documentación funcional

- `2026 Motor de Decisión v4.pptx`: matrices de score e ingreso, exclusiones, políticas, capacidad de pago y decisiones.
- `BRD-Prefiltro_Cliente_InversionesPacifico_22012026.docx`: flujo funcional, variables, políticas de buró, fórmulas y causales.

### 2.2 Diccionarios y formatos

- `DICCIONARIO-IMPL-110912.xlsx`: hojas Entrada, Salida Comercial, Salida Analista y Salida Certificación.
- `HDC_Path_Campos_JSON_DHWS3_20251216.xlsx`: rutas de campos del JSON HDC+.
- `AMBIENTE DEMO VALOR INGRESO inv.xlsx`: formato de prueba de Valor Ingreso, valores de referencia y escenarios demo.
- `Copia de FORMATO AMBIENTE DEMO VALOR INGRESO mmm 20251222.xlsx`: variante histórica del formato demo.
- `Formato_Valor_Ingreso_INVERSIONES_PACIFICO.xlsx`: formato y valores de referencia de Valor Ingreso.

### 2.3 Manuales técnicos Experian

- `HDC+ PN - Manual Insumos XML v1.6.4.PDF`.
- `HDC+ PN - Manual de Implementacion WS SOAP v1.9 WSS (DHWS3).PDF`.
- `HDC+ PN - Manual de Implementacion WS Servicio Rest_2507.PDF`.

Los manuales SOAP sirven como referencia de estructura y códigos, pero la integración implementada usa REST. Las hojas de cálculo de Valor Ingreso son insumos de prueba/referencia; el motor productivo consume la respuesta normalizada del servicio.

## 3. Precondiciones mínimas para evaluar

Una evaluación necesita:

1. Una solicitud válida con identificación, ocupación, fecha de nacimiento y datos del crédito.
2. Un reporte HDC+ normalizado, real o mock.
3. Una respuesta de Valor Ingreso normalizada o `null`.
4. Un `SMMLV` mayor que cero.
5. Un conjunto coherente de parámetros de negocio.
6. Si la consulta es en línea, credenciales, URLs, producto e IP registrados ante Experian.
7. Si se persiste la evaluación, una base de datos disponible y con el esquema correspondiente.

El núcleo del motor es puro: recibe `Solicitud`, `RespuestaHDC`, `RespuestaValorIngreso`, `MotorParametros` y una fecha; las consultas externas y la persistencia se realizan antes o después por la capa de evaluación.

## 4. Datos de la solicitud

| Campo | Tipo / unidad | Obligatorio efectivo | Uso actual |
|---|---|---:|---|
| `tipo_id` | Enum de tipo de identificación | Sí | Identidad y detección de persona jurídica (NIT/PJE). |
| `numero_id` | Texto, 1–20 caracteres | Sí | Consulta, validación de identidad y auditoría. |
| `primer_apellido` | Texto, 1–60 caracteres | Sí | Insumo exigido por HDC+. |
| `ocupacion` | Empleado, pensionado, independiente o fuerzas militares | Sí | Selecciona escalas, continuidad y matriz. |
| `tipo_contrato` | Indefinido, fijo, obra/labor u otro enum | Condicional | Para empleado; sin tipo válido no cumple continuidad. |
| `antiguedad_meses` | Meses, entero no negativo | No | Informativo; el motor usa continuidad de Valor Ingreso. |
| `anios_camara_comercio` | Años, número no negativo | Para independiente | Sin dato dispara R16; insuficiente dispara R24. |
| `fecha_nacimiento` | Fecha | Sí | Calcula edad; fuera de `[18, 66)` dispara R13 con los parámetros vigentes. |
| `nacionalidad` | Texto | Sí lógico; default Colombia | Distinta de Colombia/colombiana/colombiano/CO/COL dispara R21. |
| `tiene_multas_runt` | Booleano | Sí lógico; default `false` | `true` dispara R22. No existe integración RUNT. |
| `ingresos_mensuales` | COP, no negativo | No; default 0 | Respaldo si no hay Valor Ingreso ni Quanto. |
| `otros_ingresos` | COP, no negativo | No; default 0 | Se suma a la base de capacidad de pago. |
| `saldo_financiar` | COP, mayor que 0 | Sí en API | Capital para calcular la cuota de la moto. |
| `plazo` | Meses, mayor que 0 | Sí en API | Plazo de la cuota de la moto. |
| `tasa` | Porcentaje mensual, no negativo | Sí en API | Tasa mensual; `2` significa 2 %, no 0,02. |
| `consultar_experian` | Booleano | No | En producción la consulta se fuerza; en demo permite mock o consulta. |
| `escenario_mock` | Texto | Solo demo | Selecciona un escenario predefinido sin consulta real. |

Validaciones operativas adicionales:

- La identidad de la solicitud debe coincidir con la persona de HDC+ y Valor Ingreso.
- En evaluación de una solicitud almacenada, `primer_apellido` debe enviarse si no existe en el cliente.
- No deben utilizarse datos personales reales en fixtures, archivos versionados o logs.

## 5. Insumos HDC+ que afectan la decisión

El parser espera `ReportHDCplus` o su contenido raíz. Una envoltura o versión diferente requiere adaptador. Los grupos relevantes son:

| Grupo HDC+ | Datos usados |
|---|---|
| Persona | Tipo y número de identificación, estado del documento y datos para validación de identidad. |
| `models` | Código del modelo, puntaje, razones y fecha. |
| `productValueList` / Quanto | Valor medio; HDC+ lo expresa en miles y el motor multiplica por 1.000. |
| `liabilities` | Estado, sector, calidad de deudor, saldo, saldo en mora, cuota, vector de comportamiento, calificación, evento, fechas y reestructuración. |
| `CreditCardList` | Estado, cupo, saldo, cuota, comportamiento, mora, sector y calidad de deudor. |
| `savings` / `checkingList` | Estado 06/07 para detectar embargos. |
| `globalIndebtedness` | Se normaliza y expone en detalle, pero no alimenta directamente las fórmulas actuales. |
| `alerts` | Se normaliza y expone; no dispara por sí sola una causal actual. |

Si falta el score de un modelo configurado, no se sustituye por cualquier otro score: queda sin perfil, se agrega advertencia y el motor termina en R20 si ninguna regla más justifica el rechazo.

### Supuestos de interpretación por confirmar

- El código asume que el carácter 0 del vector de comportamiento es el mes más reciente.
- Los primeros `meses_ventana_buro` caracteres representan la ventana evaluada.
- Un dígito `1`–`6` representa 30–180 días de mora; `N` equivale a cero.
- Campos numéricos HDC inválidos pueden terminar normalizados como cero; se debe definir si eso debe producir error en lugar de continuar.
- La calificación negativa histórica se deriva de la calificación actual, no de una serie mensual completa.

## 6. Insumos de Valor Ingreso

La respuesta esperada contiene, como mínimo funcional:

- Identificación de la persona y `respuesta_id`.
- `aportantes[].resultado_pagos` con año, mes, indicador de pago e ingreso.
- `resumen_general_ingresos.meses_continuidad`.
- Indicadores y datos del aportante para trazabilidad.

Cálculo implementado:

1. Se consideran como máximo `max_aportantes` (5).
2. Por cada aportante se toman los `meses_promedio_valor_ingreso` períodos más recientes (3).
3. Se calcula el promedio por aportante y se suman los promedios.
4. La continuidad del empleado se toma de `resumen_general.meses_continuidad`, no de `antiguedad_meses`.

Debe certificarse con los formatos de Experian si los períodos sin pago deben incluirse como cero o excluirse: la documentación interna no es completamente consistente en este punto.

## 7. Parámetros de negocio configurables

Orden de precedencia, de menor a mayor:

1. Defaults de `MotorParametros`.
2. `parametros.json` indicado por `PARAMETROS_PATH`.
3. Variables `MOTOR_<NOMBRE_EN_MAYÚSCULAS>`.

Las variables de entorno bloquean el valor frente a cambios por API. `codigos_score` se configura como lista separada por comas.

### 7.1 Política, exclusiones y score

| Parámetro | Valor actual | Unidad | Efecto |
|---|---:|---|---|
| `edad_minima_be` | 18 | años | Límite inferior inclusivo; menor dispara R13. |
| `edad_maxima_be` | 66 | años, límite exclusivo | Igual o mayor dispara R13. |
| `activar_exclusion_persona_juridica` | `true` | booleano | NIT/PJE dispara E1. |
| `activar_exclusion_score_0` | `true` | booleano | Score 0 se trata como exclusión. |
| `activar_exclusion_score_3_fallecido` | `true` | booleano | Score 3 dispara R1. |
| `activar_exclusion_score_4_codeudor` | `true` | booleano | Score 4 se trata como exclusión. |
| `scores_exclusion` | 0, 4 | lista de enteros | Scores sometidos a E7/RC3 según ingreso. |
| `saldo_mora_be` | 300.000 | COP | Telcos cuenta solo si saldo en mora es estrictamente mayor. |
| `estados_buro_embargo` | 06, 07 | lista de códigos | Estados que identifican embargo. |
| `estados_buro_cartera_castigada` | 45 | lista de códigos | Estados que identifican cartera castigada. |
| `estados_buro_dudoso_recaudo` | 47 | lista de códigos | Estados que identifican dudoso recaudo. |
| `estados_buro_pago_total` | 03 | lista de códigos | Estados de pago total o cierre usados por las reglas. |
| `evento_cancelacion_mal_manejo` | 03 | código | Novedad aprobada por el BRD para R3. |
| `calificaciones_negativas` | C, D, E, K | lista | Calificaciones que activan R10; A, AA, B y BB no la activan. |
| `codigos_reestructuracion` | 12, 1, 2, 5, 6 | lista | Códigos HDC+ para detectar reestructuración/refinanciación. |
| `tokens_reestructuracion` | REESTRUCT, REFINANC, RENEGOCI | lista | Detección textual complementaria. |
| `score_ep_1` | 750 | puntos | Perfil A de empleado/pensionado desde este valor. |
| `score_ep_2` | 680 | puntos | Perfil B de empleado/pensionado desde este valor. |
| `score_ep_3` | 600 | puntos | Perfil C de empleado/pensionado desde este valor. |
| `score_ep_4` | 500 | puntos | Perfil D de empleado/pensionado desde este valor. |
| `score_if_1` | 770 | puntos | Perfil A de independiente/FFMM desde este valor. |
| `score_if_2` | 700 | puntos | Perfil B de independiente/FFMM desde este valor. |
| `score_if_3` | 620 | puntos | Perfil C de independiente/FFMM desde este valor. |
| `score_if_4` | 520 | puntos | Perfil D de independiente/FFMM desde este valor. |
| `score_piso_experiencia` | 150 | puntos | Menor a 150 dispara R23; entre piso y corte D dispara R14. |
| `codigos_score` | 67, Z0, BF, DF, 04 | códigos ordenados | Orden de preferencia para seleccionar score. |
| `quanto_factor` | 1.000 | multiplicador | Convierte el Quanto reportado en miles a COP. |

### 7.2 Perfil de ingreso y continuidad

| Parámetro | Valor actual | Unidad | Efecto |
|---|---:|---|---|
| `ingreso_e_1` | 1,6 | SMMLV | Perfil alto de empleado desde este valor. |
| `ingreso_e_2` | 1,4 | SMMLV | Perfil medio de empleado desde este valor. |
| `ingreso_e_3` | 1,0 | SMMLV | Piso del perfil bajo de empleado. |
| `ingreso_pf_1` | 1,6 | SMMLV | Perfil alto de pensionado/FFMM desde este valor. |
| `ingreso_pf_2` | 1,4 | SMMLV | Perfil medio de pensionado/FFMM desde este valor. |
| `ingreso_pf_3` | 1,0 | SMMLV | Piso del perfil bajo de pensionado/FFMM. |
| `ingreso_i_1` | 2,5 | SMMLV | Perfil alto de independiente desde este valor. |
| `ingreso_i_2` | 2,0 | SMMLV | Perfil medio de independiente desde este valor. |
| `ingreso_i_3` | 1,6 | SMMLV | Perfil bajo de independiente desde este valor. |
| `ingreso_i_4` | 1,4 | SMMLV | Perfil gris solo si el ingreso es estrictamente mayor; igual o menor dispara R15. |
| `meses_cont_1` | 5 | meses | Continuidad mínima de contrato indefinido. |
| `meses_cont_2` | 10 | meses | Continuidad mínima de contrato fijo u obra/labor. |
| `anios_cam_1` | 1 | años | Cámara mínima para perfil de ingreso alto. |
| `anios_cam_2` | 2 | años | Cámara mínima para perfil de ingreso medio. |
| `anios_cam_3` | 3 | años | Cámara mínima para perfil de ingreso bajo. |
| `anios_cam_4` | 4 | años | Cámara mínima para perfil gris o score D. |

### 7.3 Buró

| Parámetro | Valor actual | Unidad | Efecto |
|---|---:|---|---|
| `meses_ventana_buro` | 12 | meses | Longitud del vector y ventana temporal aproximada. |
| `umbral_mora_30_historica` | 2 | eventos | R7 al alcanzar el umbral. |
| `umbral_mora_60_historica` | 1 | eventos | R8 al alcanzar el umbral. |
| `umbral_mora_90_historica` | 1 | eventos | R9 al alcanzar el umbral. |
| `umbral_reestructuraciones` | 2 | obligaciones | R11 al alcanzar el umbral. |

### 7.4 Capacidad de pago

| Parámetro | Valor actual | Unidad | Efecto |
|---|---:|---|---|
| `gastos_personales_pct_bajo` | 50 | % | Banda inferior a 1,6 SMMLV. |
| `gastos_personales_pct_medio` | 45 | % | Banda desde 1,6 y menor de 2,0 SMMLV. |
| `gastos_personales_pct_alto` | 40 | % | Banda desde 2,0 SMMLV. |
| `gastos_personales_umbral_medio` | 1,6 | SMMLV | Inicio de banda media. |
| `gastos_personales_umbral_alto` | 2,0 | SMMLV | Inicio de banda alta. |
| `gastos_personales_pct_quanto` | 50 | % | Gasto personal fijo cuando la fuente es Quanto. |
| `endeu_1` | 90 | % | Código actual rechaza si supera 90 %. |
| `endeu_2` | 86 | % | Código actual rechaza también entre 86 % y 90 %. |
| `capacidad_pago_pct` | 70 | % | Porcentaje del disponible convertido en capacidad. |
| `cupo_sugerido_tasa_pct` | 2 | % mensual | Tasa aprobada para calcular cupo sugerido. |
| `cupo_sugerido_plazo_meses` | 24 | meses | Plazo aprobado para calcular cupo sugerido. |
| `cupo_sugerido_tope` | 20.000.000 | COP | Tope aprobado del cupo sugerido. |
| `tasa_gasto_financiero_pct` | 2 | % mensual | Estimación de cuotas faltantes. |
| `plazo_rotativo_default_meses` | 36 | meses | Plazo de rotativos sin cuota. |
| `max_aportantes` | 5 | aportantes | Máximo usado en Valor Ingreso. |
| `meses_promedio_valor_ingreso` | 3 | meses | Períodos usados por aportante. |

### 7.5 Valores de negocio no parametrizados actualmente

Los valores aprobados para campañas quedaron parametrizados. Permanecen fijos los sectores económicos del catálogo HDC+, los tipos de cuenta rotativa, los marcadores textuales de obligación cerrada, el score 3 como indicador de fallecimiento y la normalización de la decisión pública a Aprobado/Rechazado.

## 8. Validaciones de coherencia de parámetros

La carga se rechaza por completo si:

- Las escaleras de score o ingreso no son estrictamente descendentes.
- `anios_cam_1 <= anios_cam_2 <= anios_cam_3 <= anios_cam_4` no se cumple.
- `score_piso_experiencia` supera cualquiera de los cortes D.
- La edad mínima no es menor que la máxima.
- El umbral medio de gastos no es menor que el alto.
- `endeu_2` no es menor que `endeu_1`.
- `codigos_score` está vacío.
- Un porcentaje validado queda fuera de 0–100.
- Un mínimo definido por Pydantic queda por debajo de cero o una cantidad requerida queda por debajo de uno.
- El JSON contiene campos desconocidos (`extra="forbid"`) o tipos inválidos.

Un archivo incoherente debe detener la evaluación mediante `ParametrosError`; no debe decidirse con parámetros parciales.

## 9. Reglas que usan los parámetros

### 9.1 Filtros de solicitud y buró

| Causal | Regla implementada |
|---|---|
| R1 | Score entero 3 y exclusión activa. |
| E1 | NIT/PJE y exclusión de persona jurídica activa. |
| R21 | Nacionalidad no reconocida como colombiana. |
| R22 | Multas RUNT informadas. |
| R2 | Al menos una cuenta de ahorro/corriente con estado iniciado por 06/07. |
| R3 | Evento 03 dentro de ventana, excluyendo Telcos. |
| R4 | Estado 45 o `C` en vector; Telcos solo sobre `saldo_mora_be`. |
| R5 | Estado 47 o `D` en vector; misma regla Telcos. |
| R6 | Mora máxima de 60+ en la ventana, obligación no bloqueada ni pagada. |
| R7/R8/R9 | Conteos de mora 30/60/90 contra umbrales configurados. |
| R10 | Calificación C/D/E/K, sin Telcos ni codeudor. |
| R11 | Reestructuración/refinanciación/renegociación contra umbral. |
| R12 | Estado de documento distinto de los códigos aceptados. |
| E2 | Mora 30+ en la ventana, obligación propia, abierta y no bloqueada. |

### 9.2 Ingreso final

Precedencia implementada: Valor Ingreso positivo → Quanto medio positivo → ingreso declarado positivo → cero y E3.

`ingreso_final_smmlv = ingreso_final / SMMLV`.

### 9.3 Matrices

- Score A/B/C/D se determina según la escala de la ocupación.
- Empleado requiere continuidad; sin ella queda GRIS.
- Pensionado y FFMM usan escala de ingreso PF sin continuidad.
- Independiente requiere Cámara de Comercio y años mínimos por perfil.
- Score D dispara R25 en la matriz.
- Perfiles de ingreso bajo generan E4/E5/E6 según score A/B/C.

Advertencia: aunque algunas funciones construyen un resultado interno denominado “Aprobado” junto con una causal E4/E5/E6, cualquier causal convierte la salida pública en Rechazado. Por tanto, el comportamiento público efectivo debe analizarse por causales, no solo por el valor temporal de la matriz.

### 9.4 Capacidad de pago

```text
base = ingreso_final + otros_ingresos
gastos_totales = no_rotativos + rotativos + gastos_personales
endeudamiento = gastos_totales / base * 100
disponible = base - gastos_totales
capacidad_pago = disponible * capacidad_pago_pct / 100
```

Solo cuentan obligaciones propias, no bloqueadas y consideradas vigentes. Si falta la cuota:

- Rotativa: anualidad sobre cupo, valor inicial o saldo, con tasa parametrizada y plazo rotativo.
- No rotativa: anualidad sobre saldo, con tasa parametrizada y plazo apertura-vencimiento; sin fechas se toma cero.

La cuota de la moto usa saldo, tasa mensual y plazo de la solicitud.

## 10. Configuración técnica

### 10.1 Motor y aplicación

| Variable | Requerida | Descripción |
|---|---:|---|
| `ENVIRONMENT` | Sí | `demo` o `produccion`; producción consulta Experian. |
| `SMMLV` | Sí | Valor vigente en COP, mayor que cero. Debe actualizarse anualmente. |
| `PARAMETROS_PATH` | Sí lógico | Ruta del JSON; default `./parametros.json`. |
| `LOG_LEVEL` | No | Nivel de logging. |
| `API_HOST`, `API_PORT` | Para API | Dirección y puerto de escucha. |
| `DATABASE_URL` | Para persistencia | PostgreSQL en producción o SQLite local. |
| `DB_CREAR_TABLAS` | Sí operativo | `false` en producción si se administran esquema/migraciones. |

### 10.2 HDC+

Para consulta real deben existir:

- `HDC_USERNAME`, `HDC_PASSWORD`.
- `HDC_TOKEN_USERNAME`, `HDC_TOKEN_PASSWORD`.
- `HDC_CLIENT_ID`, `HDC_CLIENT_SECRET`.
- `HDC_TOKEN_URL_DEMO/PROD` o URL OAuth de respaldo.
- `HDC_BASE_URL_DEMO/PROD`.
- `HDC_PRODUCT_ID` (actual: 64; confirmar producto contratado).
- `SERVER_IP_ADDRESS` registrada ante Experian.

### 10.3 Valor Ingreso

- `INCOME_USERNAME`, `INCOME_PASSWORD`.
- `INCOME_CLIENT_ID`, `INCOME_CLIENT_SECRET`.
- `INCOME_SCOPE` (actual: `expco_incomes`).
- `INCOME_SUBSCRIBER_NAME` con el nombre contractual exacto.
- `INCOME_TOKEN_URL_DEMO/PROD`.
- `INCOME_BASE_URL_DEMO/PROD`.

### 10.4 OAuth y comunicaciones

- `OKTA_TOKEN_URL_DEMO/PROD` y `OKTA_REVOKE_URL_DEMO/PROD` cuando apliquen.
- `TIMEOUT_EXPERIAN_SEGUNDOS` (actual: 60).
- Certificados, TLS, conectividad, allowlist de IP y permisos del producto deben corresponder al ambiente.
- Las credenciales deben permanecer en `.env` o gestor de secretos; nunca en el repositorio.

## 11. Salida mínima y trazabilidad

Para auditar una decisión deben conservarse:

- Identificador y fecha de evaluación.
- Ambiente.
- Solicitud evaluada.
- Decisión pública, decisión interna y todas las causales.
- Score y código de modelo seleccionado.
- Perfiles de score e ingreso.
- Valor Ingreso, Quanto, ingreso final, fuente y equivalencia SMMLV.
- Gastos, endeudamiento, disponible, capacidad, cupo y cuotas.
- Indicadores derivados del buró.
- Trazabilidad por etapa y advertencias.
- Snapshot `parametros_usados` y valor `smmlv`.
- Tiempo de ejecución.

No se deben guardar respuestas completas del buró en auditoría permanente salvo que exista una política explícita de tratamiento de datos que lo autorice.

## 12. Contradicciones y decisiones pendientes

| Tema | Manuales / documentos | Código actual | Decisión requerida |
|---|---|---|---|
| Edad | PPT indica `>=18` y `<66`. | Se evalúa el rango `[18, 66)` y se dispara R13 fuera de él. | Aprobado e implementado. |
| Score 0/4 | Documentación funcional indica E7/RC3 según ingreso. | Se compara con `ingreso_e_2` o `ingreso_i_2`. | Aprobado e implementado. |
| Gastos personales altos | BRD histórico 40 %; bitácora menciona una versión PPT con 50 %. | JSON y código usan 40 % desde 2 SMMLV. | Aprobado e implementado. |
| Endeudamiento intermedio | Documentos internos mencionan E8 desde 75 % o desde 86 %. | Entre 86 % y 90 % dispara R17; no se genera E8. | Aprobado e implementado. |
| Cupo sugerido | PPT/BRD/documentos difieren entre 24 y 48 meses. | 2 % mensual, 24 meses y tope parametrizado de $20 millones. | Aprobado e implementado. |
| Perfil bajo de empleado | Algunas notas dicen aprobado; otras Estudio E4/E5/E6. | Se crea causal E4/E5/E6, por lo que públicamente resulta Rechazado. | Confirmar salida pública deseada. |
| Decisiones Estudio/Codeudor | PPT maneja estados intermedios. | La salida pública es Rechazado, pero se conserva Estudio/Codeudor internamente. | Aprobado e implementado para trazabilidad. |
| Ingreso declarado | PPT permite respaldo después de Valor Ingreso y Quanto. | Se usa como última fuente positiva; queda trazado como `ingresos_declarados`. | Aprobado e implementado. |
| Valor Ingreso | Se requieren períodos recientes consecutivos. | El promedio conserva los períodos en cero y no los reemplaza por meses positivos más antiguos. | Aprobado e implementado. |
| Vector HDC | Orientación depende del manual/versión contratada. | Posición 0 = mes más reciente. | Certificar con Experian. |
| R6 vigente | “Vigente” puede significar mes actual. | Busca cualquier mora 60+ en toda la ventana. | Definir alcance temporal. |
| Telcos | Umbral consolidado en 300.000. | La comparación es estricta `>`; exactamente 300.000 no cuenta. | Confirmar inclusividad. |
| SMMLV | Configuración de ejemplo: 1.750.905. | Default idéntico. | Verificar contra decreto vigente antes de cada despliegue. |
| Producto HDC | Configuración usa producto 64. | Es el default actual. | Confirmar que coincide con el contrato y los códigos de score. |
| Parser rígido | Manuales contemplan variantes/versiones. | Espera una estructura concreta. | Versionar adaptadores y fallar explícitamente ante formato desconocido. |

## 13. Lista de verificación antes de producción

- [ ] Negocio firma los valores y contradicciones de la sección 12.
- [ ] `SMMLV` coincide con el decreto vigente.
- [ ] `parametros.json` pasa todas las validaciones y queda versionado por despliegue.
- [ ] Los códigos en `codigos_score` corresponden al producto contratado y su prioridad.
- [ ] Se certifica la orientación del vector HDC+ con un reporte conocido.
- [ ] Se certifican estados, sectores, calidad de deudor y periodicidades contra la versión REST contratada.
- [ ] Se prueban score 0, 3, 4, ausencia de score y score decimal.
- [ ] Se prueban las cuatro ocupaciones y todos los límites exactos de score e ingreso.
- [ ] Se prueban continuidad, Cámara de Comercio y ausencia de datos condicionales.
- [ ] Se prueban Telcos por debajo, igual y por encima de $300.000.
- [ ] Se prueban obligaciones propias/codeudor, abiertas/cerradas, bloqueadas y sin cuota.
- [ ] Se certifican tasa, plazo y tope del cupo sugerido.
- [ ] Se valida identidad entre solicitud, HDC+ y Valor Ingreso.
- [ ] Credenciales, URLs, scopes, subscriber, producto e IP se validan en demo y producción.
- [ ] Producción usa PostgreSQL/esquema aprobado y `DB_CREAR_TABLAS=false` si hay migraciones.
- [ ] Se prueba el manejo de timeout, token vencido, respuesta parcial y formato inesperado.
- [ ] La auditoría conserva parámetros y SMMLV sin almacenar indebidamente reportes completos.
- [ ] Se ejecutan pruebas unitarias, integración, API y casos de certificación de Negocio.

## 14. Estado actual del desarrollo

El proyecto ya dispone de:

- Modelos Pydantic de entrada y salida.
- Motor lineal con acumulación de causales y trazabilidad.
- Parámetros validados, editables por JSON/API y bloqueables por entorno.
- Parsers HDC+ y Valor Ingreso para la estructura conocida.
- Clientes REST/OAuth de Experian.
- Cálculo de Valor Ingreso, perfiles, filtros, matrices y capacidad de pago.
- Validación de identidad.
- Persistencia y auditoría.
- API FastAPI y una interfaz Streamlit en desarrollo.
- Pruebas unitarias existentes.

El riesgo principal ya no es la ausencia de estructura técnica, sino la certificación funcional de las contradicciones listadas y la rigidez ante variantes reales de las respuestas de Experian.
