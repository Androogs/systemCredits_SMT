# Reglas de negocio del motor

Estrategia **Prefiltro_Cliente** (Inversiones Pacífico). Fuentes: BRD-Prefiltro_Cliente
(robustez: estructura, políticas adicionales y validaciones) y **PPT v4 2026 Motor de
Decisión** (valores y matrices vigentes). Cada valor está en `parametros.json` y se
edita por API; nada de lo que aparece aquí está “quemado” en el código salvo los
códigos de estado del manual HDC+.

## 1. Flujo (lineal)

Se evalúan **todas** las etapas y se devuelven **todas** las causales que disparen.

| # | Etapa | Módulo | Qué produce |
|---|-------|--------|-------------|
| 1 | Filtros duros | `reglas_filtros_duros.py` | R1, E1, R21, R22, R2–R12, E2 |
| 2 | Exclusión de score 0/4 | `motor_decision_service.py` | E7 o RC3 |
| 3 | Valor Ingreso e Ingreso Final | `valor_ingreso_service.py`, `reglas_ingreso.py` | E3 |
| 4 | Perfil de score y de ingreso | `reglas_perfil.py` | R14, R23, R15, R25 |
| 5 | Matriz de decisión | `reglas_perfil.py` | RC1, RC2, RC4, R16, R24, E4–E6 |
| 6 | Capacidad de pago (siempre) | `capacidad_pago_service.py` | R17–R19, E8, E9 |

**Decisión interna** = la de mayor prioridad entre las causales:
Rechazado > Requiere Codeudor > Estudio > Aprobado.
**Decisión pública** = binaria: *Aprobado* solo si no hay ninguna causal; en cualquier
otro caso *Rechazado*, con las causales ordenadas por prioridad. Si la matriz no puede
aprobar y ninguna etapa dejó causal (p. ej. no hay score del modelo contratado), se
reporta **R20**: el motor nunca aprueba por omisión.

## 2. Filtros duros

| Código | Política | Umbral / regla |
|--------|----------|----------------|
| R1 | Cliente reportado como fallecido | Score = 3 |
| E1 | Cliente diferente a persona natural | Tipo de documento NIT o PJE |
| — | Edad | Se conserva como dato informativo; no afecta la decisión ni los datos extraídos de HDC+ o Valor Ingreso. |
| R21 | Nacionalidad diferente a colombiana | Campo `nacionalidad` de la solicitud (BRD) |
| R22 | Multas en el RUNT | Campo `tiene_multas_runt` de la solicitud (BRD; sin integración) |
| R2 | Embargos | Cuenta de ahorros/corriente con estado 06/07 ≥ 1 |
| R3 | Cancelación por mal manejo | Evento 03 en los últimos 12 meses ≥ 1 (sin Telcos) |
| R4 | Cartera castigada | Estado 45 o “C” en vector 12 m ≥ 1 |
| R5 | Dudoso recaudo | Estado 47 o “D” en vector 12 m ≥ 1 |
| R6 | Mora 60+ vigente | Mora ≥ 60 días en vector 12 m, cuenta no bloqueada ni pagada (03) |
| R7 | Mora histórica 30 días | Moras ≥ 30 d en 12 m ≥ `umbral_mora_30_historica` (2); sin codeudor |
| R8 | Mora histórica 60 días | ≥ `umbral_mora_60_historica` (1) |
| R9 | Mora histórica 90+ días | ≥ `umbral_mora_90_historica` (1) |
| R10 | Calificación C, D, E o K | ≥ 1 (todos los sectores, sin codeudor); A, AA, B y BB no activan |
| R11 | Reestructuración | Reestructuradas/refinanciadas en 12 m ≥ `umbral_reestructuraciones` (2) |
| R12 | Documento no vigente | Estado ≠ 00 (25 = excepción cédula de extranjería) |
| E2 | Mora 30 días vigente | Mora ≥ 30 d en 12 m, propia, no bloqueada ni pagada |

**Telcos (sector 4):** solo cuentan en R4–R9 y E2 si el saldo en mora es mayor que
`saldo_mora_be` (300.000). R3, R10 y R11 excluyen Telcos siempre.

## 3. Exclusiones de score

| Score | Tratamiento |
|-------|-------------|
| 3 | R1 (fallecido) |
| 0 ó 4 | No se asigna perfil de score ni se aplica la matriz. Si el ingreso en SMMLV ≥ `ingreso_e_2` (independiente: `ingreso_i_2`) → **E7** Estudio; si no → **RC3** Requiere codeudor |

El score se toma del primer código de `codigos_score` presente en HDC+
(`67, Z0, BF, DF, 04`). Si no aparece ninguno, **no** se usa otro score del reporte.

### Exclusiones configurables para campañas

Estas banderas se cargan desde `parametros.json`, se pueden actualizar por `PUT /parametros`
y aparecen en la pantalla de parámetros:

| Parámetro | Valor `true` | Valor `false` |
|---|---|---|
| `activar_exclusion_persona_juridica` | NIT/PJE dispara E1 | Continúa la evaluación sin E1 |
| `activar_exclusion_score_0` | Score 0 dispara la exclusión | Score 0 continúa la evaluación |
| `activar_exclusion_score_3_fallecido` | Score 3 dispara R1 | Score 3 no dispara R1 |
| `activar_exclusion_score_4_codeudor` | Score 4 dispara la exclusión | Score 4 continúa la evaluación |

Al desactivar una bandera se ignora completamente esa exclusión y el caso sigue por
ingresos, perfil, capacidad de pago y demás políticas activas. Las dos descripciones
de score 0 de la PPT se controlan con una sola bandera porque el modelo normalizado
recibe únicamente el puntaje `0`; no contiene el dato necesario para diferenciarlas.
Desactivar score 3 no desactiva otras causales independientes, como documento no vigente
(`R12`) o moras.

## 4. Ingreso

**Valor Ingreso** = suma, hasta 5 aportantes, del promedio de los pagos válidos
(`realizo_pago` y > 0) de los 3 periodos más recientes de cada aportante.

**Ingreso Final** (PPT v4), para todas las ocupaciones:
Valor Ingreso > 0 → Valor Ingreso; si no, Quanto medio (HDC+ en miles × 1.000) > 0 →
Quanto; si no, ingresos declarados. Si los tres son 0 → ingreso 0 y **E3**.

## 5. Perfiles

**Score** (Empleado/Pensionado: `score_ep_*`; Independiente/FFMM: `score_if_*`)

| Perfil | Empleado / Pensionado | Independiente / FFMM |
|--------|----------------------|----------------------|
| A | ≥ 750 | ≥ 770 |
| B | ≥ 680 | ≥ 700 |
| C | ≥ 600 | ≥ 620 |
| D | ≥ 500 | ≥ 520 |
| R14 | 150 ≤ score < corte | 150 ≤ score < corte |
| R23 | < 150 (`score_piso_experiencia`, BRD) | < 150 |

**Ingreso** (en SMMLV)

| Perfil | Empleado* | Pensionado / FFMM | Independiente |
|--------|-----------|-------------------|---------------|
| ALTO | ≥ 1,6 | ≥ 1,6 | ≥ 2,5 |
| MEDIO | ≥ 1,4 | ≥ 1,4 | ≥ 2,0 |
| BAJO | ≥ 1,0 | ≥ 1,0 | ≥ 1,6 |
| GRIS | ≥ 1,0 sin continuidad | — | > 1,4 |
| R15 | < 1,0 | < 1,0 | ≤ 1,4 |

\* Empleado exige continuidad según **Valor Ingreso** (`meses_continuidad`):
indefinido ≥ 5 meses, fijo / obra o labor ≥ 10. La antigüedad declarada no se usa.

## 6. Matrices

**Empleado, Pensionado y Fuerzas Militares**

| Score \ Ingreso | ALTO | MEDIO | BAJO | GRIS |
|---|---|---|---|---|
| A | Aprobado | Aprobado | Estudio E4 | Rechazado RC1 |
| B | Aprobado | Aprobado | Estudio E5 | Rechazado RC1 |
| C | Aprobado | Aprobado | Estudio E6 | Rechazado RC1 |
| D | Rechazado R25 | Rechazado R25 | Rechazado R25 | Rechazado R25 |

**Independiente**: se exige Cámara de Comercio; si no se reporta → **R16**. Con Cámara,
los años mínimos son ALTO 1, MEDIO 2, BAJO 3, GRIS o score D 4; si no se cumplen →
**R24**. Luego: D → R25; ALTO/MEDIO → Aprobado;
BAJO → E4/E5/E6; GRIS → RC4.

## 7. Capacidad de pago

**Gastos personales:** si la fuente es Valor Ingreso, se aplica 50 % para menos de
1,6 SMMLV, 45 % para [1,6, 2,0) SMMLV y 40 % desde 2,0 SMMLV. Si la fuente es
Quanto 3 Medio, se aplica 50 % fijo sin importar el perfil de ingreso. Para gastos
rotativos sin cuota reportada se usan tasa mensual de 2 % y plazo de 36 meses.

| Variable | Fórmula |
|----------|---------|
| Base | Ingreso final + otros ingresos |
| Gasto financiero | Solo obligaciones abiertas/vigentes propias (se excluyen estados pagados, cancelados, cerrados e inactivos). Sin cuota reportada: anualidad al 2 % sobre el cupo (`cupo_total` en TDC, `valor_inicial` en cartera rotativa; `saldo_actual` como respaldo), a 36 meses rotativos; plazo apertura→vencimiento no rotativos |
| Gastos personales | Base × 50 % (< 1,6 SMMLV) / 45 % (1,6–2,0) / 40 % (≥ 2,0) |
| Endeudamiento | (gasto financiero + personales) / base × 100 |
| Disponible | Base − (gasto financiero + personales) |
| Capacidad de pago | Disponible × 70 % |
| Cupo sugerido | Valor presente de la capacidad con la tasa y el plazo de la solicitud |
| Cuota moto | Cuota del saldo a financiar con la tasa y el plazo de la solicitud |

Disponible ≤ 0 → R18; capacidad ≤ 0 → R19; endeudamiento > 90 % → R17. Si no hubo
rechazo: endeudamiento ≥ 75 % → E8; cuota moto > cuota sugerida → E9.

Todas las cuotas usan la anualidad francesa correcta (`finanzas.py`), no la fórmula
de la hoja “Ejemplo Calculo cuotas 1.xlsx”, que tiene un error de precedencia.
