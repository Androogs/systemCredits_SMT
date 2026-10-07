# Origen y cálculo de los indicadores del resultado del motor

Este documento explica los campos mostrados en el resultado de una evaluación y los relaciona con el código que los produce. La referencia es la configuración que está actualmente versionada en `parametros.json` y el `SMMLV=1.750.905` de `.env`.

> Importante: los parámetros pueden cambiarse desde `parametros.json` o mediante variables `MOTOR_<NOMBRE>`. Por ello, para explicar una evaluación histórica, se debe revisar `parametros_usados` que queda guardado en su resultado. El SMMLV empleado queda en el campo `smmlv` del mismo resultado.

## Recorrido de los datos

1. DataCrédito entrega HDC+ y Valor Ingreso.
2. `backend/integrations/datacredito/parsers/hdc_parser.py` normaliza el JSON HDC+ a `RespuestaHDC`.
3. `backend/services/motor_decision_service.py` escoge el score, calcula el ingreso final y llama a los perfiles y a capacidad de pago.
4. `backend/services/capacidad_pago_service.py` calcula los gastos, disponible, capacidad, cupo y cuotas.
5. `ResultadoMotor` expone los valores finales, redondeados para presentación a dos decimales (cuatro para SMMLV).

## Explicación campo a campo

| Campo mostrado | De dónde sale | Regla o fórmula aplicada |
| --- | --- | --- |
| **Score consultado** | HDC+ `ReportHDCplus.models[*]`: `modelCode` y `scoreValue`. El parser los deja como `Score.tipo` y `Score.puntaje`. | Se selecciona el primer score disponible cuyo código esté en `codigos_score`, en este orden: `67`, `Z0`, `BF`, `DF`, `04`. No se reemplaza por un score de otro modelo. Para el ejemplo, el modelo seleccionado devolvió **827**. |
| **Perfil Score** | Score seleccionado + ocupación informada en la solicitud. | Para empleado o pensionado: A si `score >= 750`, B si `>= 680`, C si `>= 600`, D si `>= 500`. Para independiente o fuerzas militares: 770 / 700 / 620 / 520. Con 827 el resultado es **A** para cualquiera de las dos escalas. |
| **Valor ingreso** (base de la fuente) | Servicio Valor Ingreso de DataCrédito, no HDC+. Se toman los aportantes y sus `resultado_pagos`. | Por cada uno de máximo 5 aportantes se promedian los 3 períodos más recientes, incluidos períodos con cero; se suman los promedios. `valor_ingreso = Σ(promedio de los últimos 3 pagos por aportante)`. |
| **Ingreso Final** | `valor_ingreso`, Quanto de HDC+ e ingreso declarado en la solicitud. | Para todas las ocupaciones se aplica la precedencia: Valor Ingreso positivo, luego Quanto 3 medio positivo y finalmente ingreso declarado positivo. Si las tres fuentes son cero se genera E3. En el caso mostrado, **$15.275.577** proviene de Valor Ingreso. |
| **Fuente ingreso** | Resultado de la regla de ingreso final. | `valor_ingreso` significa que se tomó el cálculo de aportantes descrito arriba. Las otras posibles fuentes son `quanto3_medio`, `ingresos_declarados` (fallback no esperado) y `ninguna`. |
| **Ingreso Final SMMLV** | Ingreso final y `SMMLV` de configuración. | `ingreso_final_smmlv = ingreso_final / smmlv`. En este caso: `15.275.577 / 1.750.905 = 8,724...`, presentado como **8,72 SMMLV**. |
| **Perfil Ingreso** | Ingreso final en SMMLV, ocupación, y para empleados continuidad/contrato. | Para empleado: ALTO `>= 1,6`, MEDIO `>= 1,4`, BAJO `>= 1,0`, siempre que cumpla continuidad: 5 meses indefinido o 10 meses fijo/obra-labor. Pensionado/FFMM usan 1,6 / 1,4 / 1,0; independiente usa 2,5 / 2,0 / 1,6. Con **8,72 SMMLV**, el resultado es **ALTO** (sujeto a que en empleado también cumpla continuidad). |
| **Gastos financieros no rotativos** | Obligaciones de cartera de HDC+ (`liabilities` / `CuentaCartera`). | Suma de las cuotas mensuales de obligaciones propias, vigentes y no bloqueadas que no sean rotativas: `Σ cuota_mensual`. La cuota viene de HDC+ `values[0].valueMonthlyPayment`; si no existe, se estima con la anualidad sobre el saldo y el plazo entre apertura y vencimiento. Las cuotas no mensuales se dividen por 2, 3, 6 o 12 según periodicidad. En el ejemplo la suma es **$725.000**. |
| **Gasto financiero rotativo** | Carteras tipo 2/3, TDC o CBR, y tarjetas de crédito de HDC+ (`CreditCardList`). | Suma de las cuotas mensuales de obligaciones propias, vigentes y no bloqueadas: `Σ cuota_mensual_rotativa`. Si no llega cuota, se calcula sobre `cupo_total`, luego `valor_inicial` y finalmente saldo, a 2% mensual y 36 meses. En el ejemplo la suma es **$512.734**. |
| **Gastos personales** | Base de ingresos y banda de SMMLV. | `base × porcentaje`. El porcentaje es 50% si `< 1,6 SMMLV`, 45% si `[1,6, 2,0)`, 40% si `>= 2,0`; con Quanto como fuente es 50% fijo. En el ejemplo: `15.275.577 × 40% = 6.110.230,80`, presentado como **$6.110.231**. |
| **Endeudamiento** | Gastos financieros, gastos personales y base. | `((no_rotativo + rotativo + personales) / base) × 100`. En el ejemplo: `(725.000 + 512.734 + 6.110.230,80) / 15.275.577 × 100 = 48,10%`. |
| **Disponible** | Base y gastos totales. | `base − (no_rotativo + rotativo + personales)`. En el ejemplo: `15.275.577 − 7.347.964,80 = 7.927.612,20`, presentado como **$7.927.612**. |
| **Capacidad de pago** | Disponible y parámetro `capacidad_pago_pct`. | `disponible × 70%`, solo si el disponible es positivo. Para el caso es aproximadamente `7.927.612,20 × 70% = 5.549.328,54`; el valor exacto presentado puede variar un peso por los decimales no visibles de las obligaciones y el redondeo final. |
| **Cupo sugerido** | Capacidad de pago. | Primero se halla el valor presente de una anualidad con cuota igual a la capacidad, tasa fija de 2% mensual y 24 meses: `cupo = capacidad × (1 − (1 + i)^(-n)) / i`. Luego se aplica un tope fijo de **$20.000.000**. El cupo teórico del ejemplo supera el tope, por eso se muestra exactamente **$20.000.000**. |
| **Cuota sugerida** | Cupo sugerido. | Anualidad francesa a 2% mensual y 24 meses: `cuota = cupo × i / (1 − (1 + i)^(-n))`. Para el cupo topado: `20.000.000 × 0,02 / (1 − 1,02^(-24)) = 1.057.422...`; resultado **$1.057.422**. |
| **Cuota moto** | `saldo_financiar`, `tasa` y `plazo` enviados en la solicitud. | Misma anualidad francesa: `saldo_financiar × i / (1 − (1 + i)^(-n))`, usando tasa mensual y plazo de la solicitud. El resultado mostrado es **$392.329**. No puede reconstruirse el capital exacto solo a partir de esa cuota: se necesitan los tres campos de la solicitud. |

### Base de los cálculos de capacidad

La `base` usada desde gastos personales hasta capacidad es:

```text
base = ingreso_final + otros_ingresos
```

En la muestra no se aprecia un componente de otros ingresos; por eso los cálculos reproducen los valores usando solo los $15.275.577 de ingreso final. Si la solicitud tuviera `otros_ingresos`, estos se sumarían a la base, aunque la banda de gasto personal seguiría determinada por el ingreso final en SMMLV.

### Cuándo una obligación cuenta en los gastos financieros

La obligación debe ser propia (no codeudor), no estar bloqueada y estar vigente. El motor descarta obligaciones pagadas, canceladas, cerradas, inactivas o terminadas, así como estado `03`. Para explicar los $725.000 y $512.734 de un caso específico, se deben consultar en el detalle HDC+ las cuentas incluidas y sus campos `valueMonthlyPayment`, periodicidad, tipo de cuenta y estado.

## Referencias de implementación

- Extracción de persona —incluido `genero` desde `nationalNatural.gender`—, scores, Quanto, cartera y tarjetas: `backend/integrations/datacredito/parsers/hdc_parser.py`.
- Cálculo de Valor Ingreso: `backend/services/valor_ingreso_service.py`.
- Selección de fuente e ingreso final: `backend/services/reglas_ingreso.py`.
- Perfiles de score e ingreso: `backend/services/reglas_perfil.py`.
- Parámetros vigentes por defecto y configurables: `backend/services/motor_parametros.py` y `parametros.json`.
- Gastos, endeudamiento, disponible, capacidad, cupo y cuotas: `backend/services/capacidad_pago_service.py`.
- Fórmulas de anualidad y valor presente: `backend/services/finanzas.py`.
- Orquestación, almacenamiento y redondeo de la salida: `backend/services/motor_decision_service.py`.

## Observación de implementación relevante

Aunque algunos comentarios históricos mencionan una alternativa de tasa/plazo de la solicitud o 48 meses, el código ejecutado para **cupo sugerido** y **cuota sugerida** usa actualmente valores fijos: **2% mensual y 24 meses**, además del tope de $20 millones. La cuota de la moto sí usa tasa y plazo de la solicitud.
