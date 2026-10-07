# INFORME EJECUTIVO DE DECISIONES FUNCIONALES Y TÉCNICAS

**Motor de Decisión – Inversiones Pacífico**  
**Versión:** 1.0  
**Fecha:** 02 de octubre de 2026  
**Proyecto:** Implementación Motor de Decisión de Crédito  
**Dirigido a:** Comité de Crédito / Comité de Tecnología

## 1. RESUMEN EJECUTIVO

Durante la validación final del Motor de Decisión se identificaron criterios funcionales y técnicos con diferencias entre el BRD, la presentación funcional PPT v4 y las reglas implementadas.

Las decisiones críticas descritas en este informe fueron revisadas y aprobadas para implementación. Su aplicación permite que el comportamiento del motor sea consistente, parametrizable, auditable y alineado con las políticas de riesgo definidas para Inversiones Pacífico.

El informe también diferencia las decisiones ya implementadas de los asuntos que todavía requieren certificación operativa antes de la salida a producción.

## 2. IMPACTO DE NO DEFINIR ESTAS REGLAS

La ausencia de definiciones formales puede generar:

- Créditos aprobados incorrectamente.
- Créditos rechazados indebidamente.
- Diferencias entre políticas documentadas y comportamiento real del motor.
- Riesgos de auditoría y dificultades para reconstruir una decisión.
- Incremento de desarrollos correctivos posteriores a producción.
- Pérdida de trazabilidad de las decisiones de riesgo.
- Campañas comerciales que requieran cambios directos en código.
- Resultados diferentes ante una actualización de los servicios de Experian.

## 3. DECISIONES CRÍTICAS PARA SALIDA A PRODUCCIÓN

### 3.1 Edad mínima y máxima

**Situación identificada**

La PPT v4 contempla la causal R13 por edad. El motor ya tenía los parámetros `edad_minima_be` y `edad_maxima_be`, pero no los aplicaba a la decisión.

**Decisión aprobada**

Reactivar la validación R13 con las siguientes condiciones:

- Edad mínima: 18 años, inclusiva.
- Edad máxima: 66 años, exclusiva.
- Rango permitido: edad mayor o igual a 18 y menor de 66.
- Menores de 18 o personas con 66 años o más: R13.
- La edad se calcula en la fecha efectiva de evaluación, considerando si la persona ya cumplió años.

**Estado:** implementado y probado.

**Módulos afectados**

- `backend/services/reglas_filtros_duros.py`
- `backend/services/motor_parametros.py`
- `tests/unit/test_filtros_duros_brd.py`

### 3.2 Manejo de scores 0 y 4

**Situación identificada**

Existía contradicción entre documentos y código respecto al tratamiento de clientes con score 0 o score 4. El código los enviaba directamente a R23, mientras la regla funcional aprobada exige condicionar el resultado al ingreso.

**Decisión aprobada**

Aplicar evaluación condicionada por ingreso:

- Score 0 o 4 no recibe perfil de score ni pasa por la matriz normal.
- Para independiente se compara contra `ingreso_i_2`.
- Para las demás ocupaciones se compara contra `ingreso_e_2`.
- Si el ingreso final en SMMLV alcanza el umbral: E7 – Estudio.
- Si no alcanza el umbral: RC3 – Requiere codeudor.
- La salida pública permanece binaria: cualquier causal genera Rechazado.
- La decisión interna conserva Estudio o Requiere codeudor para trazabilidad.

Los códigos de exclusión se administran mediante `scores_exclusion`, con valor actual `[0, 4]`, y mantienen sus banderas individuales de activación.

**Estado:** implementado y probado para empleado e independiente.

**Módulos afectados**

- `backend/services/reglas_filtros_duros.py`
- `backend/services/motor_decision_service.py`
- `backend/services/motor_parametros.py`
- `tests/unit/test_motor_decision.py`

### 3.3 Gastos personales para ingresos iguales o superiores a 2 SMMLV

**Situación identificada**

El BRD define 40 %, mientras una referencia de la PPT fue interpretada como 50 %.

**Decisión aprobada**

Aplicar 40 % para ingresos iguales o superiores a 2 SMMLV.

Bandas vigentes:

- Menor de 1,6 SMMLV: 50 %.
- Mayor o igual a 1,6 y menor de 2 SMMLV: 45 %.
- Mayor o igual a 2 SMMLV: 40 %.
- Cuando la fuente es Quanto: porcentaje independiente y parametrizable, actualmente 50 %.

**Estado:** implementado, parametrizado y probado.

**Módulos afectados**

- `backend/services/capacidad_pago_service.py`
- `backend/services/motor_parametros.py`
- `tests/unit/test_calculos.py`

### 3.4 Endeudamiento entre 86 % y 90 %

**Situación identificada**

No existía una definición única sobre el tratamiento del rango de endeudamiento intermedio.

**Decisión aprobada**

- Endeudamiento mayor o igual a 86 % y menor o igual a 90 %: Rechazado por R17.
- Endeudamiento superior a 90 %: Rechazado por R17.
- El motor no genera E8 para el rango aprobado.
- `endeu_2` permanece en 86 y `endeu_1` en 90.

**Estado:** implementado y probado en los límites.

**Módulos afectados**

- `backend/services/capacidad_pago_service.py`
- `backend/services/motor_parametros.py`
- `tests/unit/test_calculos.py`

### 3.5 Cálculo de cupo sugerido

**Situación identificada**

BRD, PPT y documentación interna diferían en el plazo, la tasa y el uso de valores fijos o de la solicitud.

**Decisión aprobada**

- Plazo del cupo sugerido: 24 meses.
- Tasa: 2 % mensual.
- Tope máximo: $20.000.000 COP.
- Los tres valores deben ser parametrizables para campañas futuras.
- La cuota de la moto continúa utilizando saldo, tasa y plazo de la solicitud.

Parámetros aprobados:

- `cupo_sugerido_tasa_pct = 2`
- `cupo_sugerido_plazo_meses = 24`
- `cupo_sugerido_tope = 20000000`

**Estado:** implementado, parametrizado y probado.

**Módulos afectados**

- `backend/services/capacidad_pago_service.py`
- `backend/services/motor_parametros.py`
- `parametros.json`
- `tests/unit/test_calculos.py`

## 4. DEFINICIONES DE POLÍTICAS DE BURÓ

### C1. Calificación negativa

**Definición aprobada**

Se aplica la regla descrita por el BRD:

- Obligaciones cerradas: revisar el histórico mensual de los últimos 12 meses.
- Obligaciones abiertas: revisar la calificación vigente.
- Calificaciones negativas: C, D, E y K.
- No se cuentan obligaciones como codeudor ni obligaciones de Telcos para esta política.

La lista de calificaciones se administra mediante `calificaciones_negativas`.

**Estado:** implementado y probado con obligación cerrada histórica, obligación abierta vigente y caso abierto sin calificación negativa vigente.

### C2. Reestructuraciones

**Definición aprobada**

Detectar reestructuraciones por código y por texto:

- Códigos iniciales basados en el manual HDC+: 12, 1, 2, 5 y 6.
- Textos reconocidos: reestructuración, refinanciación y renegociación.
- La evaluación mantiene la ventana de 12 meses y el umbral vigente de dos obligaciones.

Parámetros:

- `codigos_reestructuracion`
- `tokens_reestructuracion`
- `umbral_reestructuraciones`

**Estado:** implementado y probado por código y descripción.

### C3. Cancelaciones por mal manejo

**Definición aprobada según BRD**

- Utilizar exclusivamente la novedad o evento 03: Cancelada por mal manejo.
- Evaluar eventos de los últimos 12 meses.
- Excluir Telcos de esta política.
- El evento se administra mediante `evento_cancelacion_mal_manejo`.

**Estado:** implementado y parametrizado.

### C4. SMMLV vigente

**Valor aprobado:** $1.750.905 COP.

El valor se configura mediante `SMMLV` y debe revisarse en cada vigencia anual. El motor exige que sea mayor que cero y conserva el valor utilizado en el resultado de cada evaluación.

**Estado:** configurado actualmente en $1.750.905.

### C5. Identificador del producto HDC+

**Valor aprobado:** `HDC_PRODUCT_ID=64`.

Este identificador selecciona el producto contratado que Experian procesa en la consulta HDC+. Debe mantenerse parametrizable por ambiente, ya que una modificación contractual o una campaña con otro producto podría requerir un identificador diferente.

**Estado:** aprobado como valor actual y ya parametrizado mediante configuración de entorno.

## 5. PARAMETRIZACIONES APROBADAS

Se aprueba que los valores susceptibles de campañas o cambios contractuales no permanezcan incrustados en la lógica.

### 5.1 Parámetros nuevos o formalizados

| Parámetro | Valor inicial aprobado | Finalidad |
|---|---:|---|
| `scores_exclusion` | `0, 4` | Códigos de score tratados como exclusión condicionada. |
| `estados_buro_embargo` | `06, 07` | Estados usados para detectar embargos. |
| `estados_buro_cartera_castigada` | `45` | Estados de cartera castigada. |
| `estados_buro_dudoso_recaudo` | `47` | Estados de dudoso recaudo. |
| `estados_buro_pago_total` | `03` | Estados que indican pago total/cierre para las reglas. |
| `evento_cancelacion_mal_manejo` | `03` | Evento aprobado para cancelación negativa. |
| `calificaciones_negativas` | `C, D, E, K` | Calificaciones que activan R10; A, AA, B y BB no la activan. |
| `codigos_reestructuracion` | `12, 1, 2, 5, 6` | Códigos HDC+ de reestructuración/refinanciación. |
| `tokens_reestructuracion` | `REESTRUCT, REFINANC, RENEGOCI` | Detección textual complementaria. |
| `quanto_factor` | `1000` | Conversión de miles de pesos HDC+ a pesos. |
| `gastos_personales_pct_quanto` | `50` | Porcentaje de gasto cuando la fuente es Quanto. |
| `cupo_sugerido_tasa_pct` | `2` | Tasa mensual para cupo sugerido. |
| `cupo_sugerido_plazo_meses` | `24` | Plazo para cupo sugerido. |
| `cupo_sugerido_tope` | `20000000` | Tope máximo del cupo sugerido. |

### 5.2 Administración

Los parámetros se cargan en este orden:

1. Valores por defecto del modelo.
2. Archivo `parametros.json`.
3. Variables de entorno `MOTOR_<NOMBRE>`, que tienen la mayor prioridad.

Las listas se configuran por entorno separando valores con comas. El conjunto completo se valida antes de una evaluación o actualización.

**Aprobación:** parametrizar todos los valores anteriores para permitir campañas futuras dirigidas a este tipo de clientes.

## 6. RIESGOS OPERATIVOS IDENTIFICADOS

### Riesgo 1 – Compatibilidad de servicios REST

**Descripción:** el parser depende de estructuras específicas de respuesta HDC+ y Valor Ingreso. Una nueva versión, envoltura o cambio de nombres puede producir datos incompletos o interpretaciones incorrectas.

**Acciones requeridas:**

- Definir estrategia de versionamiento de parsers.
- Conservar muestras anonimizadas por versión contratada.
- Rechazar explícitamente formatos desconocidos en lugar de convertir silenciosamente campos críticos a cero.
- Incorporar pruebas contractuales contra demo de Experian.

### Riesgo 2 – Significado del vector histórico

**Descripción:** el motor interpreta el primer carácter como el mes más reciente y usa los primeros 12 caracteres.

**Acción requerida:** certificar la orientación con Experian y con un caso de comportamiento conocido antes de producción.

### Riesgo 3 – Códigos contractuales de Experian

**Descripción:** estados, eventos y códigos pueden variar por producto o versión.

**Acción requerida:** certificar los parámetros de buró y `HDC_PRODUCT_ID=64` en los ambientes demo y producción.

### Riesgo 4 – Datos incompletos o inválidos

**Descripción:** la ausencia de cuota, fechas, score contratado o datos de identidad cambia cálculos y decisiones.

**Acción requerida:** ejecutar escenarios de respuesta parcial, timeout, token vencido, formato inválido y discrepancia de identidad.

### Riesgo 5 – Actualización anual del SMMLV

**Descripción:** el SMMLV modifica perfiles de ingreso, gastos y tratamiento de exclusiones.

**Acción requerida:** incluir su actualización y aprobación en el procedimiento anual de configuración.

## 7. VALIDACIÓN Y CRITERIOS DE ACEPTACIÓN

Antes de autorizar producción se debe comprobar:

- R13 para 17, 18, 65 y 66 años exactos.
- Score 0 y 4 por encima y por debajo del umbral de ingreso.
- Umbral independiente usando `ingreso_i_2`.
- Gastos personales de 50 %, 45 % y 40 % en sus límites exactos.
- Endeudamiento por debajo de 86 %, exactamente 86 %, exactamente 90 % y superior a 90 %.
- Cupo sugerido a 24 meses, tasa 2 % y tope de $20 millones.
- Calificación histórica negativa para obligación cerrada.
- Calificación vigente negativa para obligación abierta.
- Reestructuración detectada por código y por descripción.
- Cancelación por mal manejo únicamente con evento 03.
- Carga de listas y valores mediante `MOTOR_*`.
- Coincidencia entre `parametros.json` y los valores por defecto.
- Trazabilidad del snapshot de parámetros y SMMLV utilizado.
- Consulta HDC+ exitosa con producto 64 en el ambiente correspondiente.

## 8. ESTADO DE APROBACIÓN

- [x] Reactivar R13 por edad.
- [x] Scores 0 y 4 condicionados por ingreso mediante E7/RC3.
- [x] Gastos personales de 40 % desde 2 SMMLV.
- [x] Endeudamiento entre 86 % y 90 % rechazado por R17.
- [x] Cupo sugerido a 24 meses, 2 % y tope de $20 millones.
- [x] Calificación histórica para cerradas y vigente para abiertas.
- [x] Reestructuración por código y texto.
- [x] Cancelación por mal manejo con evento 03.
- [x] SMMLV de $1.750.905.
- [x] Producto HDC+ 64.
- [x] Parametrización de valores para campañas futuras.
- [ ] Certificación contractual en demo y producción de Experian.
- [ ] Certificación de la orientación del vector histórico.

## 9. CONCLUSIÓN

Las decisiones funcionales críticas quedaron definidas y trasladadas a parámetros y reglas verificables. La salida a producción debe condicionarse a completar la certificación contractual con Experian, especialmente respecto del producto HDC+ 64, la orientación del vector histórico y la estabilidad de las estructuras REST consumidas.
