# Bitácora del ensamble (Motor Alejandro + Motor Juan)

Fecha: 30-sep-2026. Criterio acordado: **estructura y robustez del motor de Alejandro
(BRD), valores y matrices de la PPT v4 de Juan** donde las fuentes chocaban.

## 1. Qué se tomó de cada motor

| Componente | Origen | Cómo quedó |
|------------|--------|-----------|
| Estructura `backend/{services,repositories,models,db_models,utils}` | Alejandro | Se conserva; se agregan `routes/`, `middlewares/`, `integrations/` |
| Parámetros como clase con defaults + override por entorno `MOTOR_*` | Alejandro | Pydantic con validación de coherencia; valores de la PPT v4 |
| Parámetros editables en archivo JSON y API `/parametros` | Juan | Se valida el conjunto completo antes de guardar; escritura atómica |
| Fórmulas financieras correctas + nota del bug del Excel | Alejandro | `finanzas.py`, ahora en `Decimal` |
| Filtros duros como evaluación de un objeto de datos | Alejandro | `IndicadoresBuro` + `evaluar_politicas_buro` |
| Derivación de las políticas desde HDC+ (vector, estados, Telcos, codeudor) | Juan | `derivar_indicadores_buro` |
| Políticas de nacionalidad, RUNT y piso de score 150 | Alejandro (BRD) | R21, R22, R23 |
| Exclusiones de score 0/3/4, mora 30 vigente, estados Estudio/Codeudor internos | Juan (PPT v4) | Con salida pública binaria |
| Valor Ingreso desde Experian | Juan | `valor_ingreso_service.py` |
| Valor Ingreso desde cotizantes almacenados (`/motor/ingreso`) | Alejandro (modelo) | Implementado |
| Perfiles y matrices | Juan (PPT v4) | Documentados en `docs/reglas_de_negocio.md` |
| Capacidad de pago y gastos financieros desde HDC+ | Juan (PPT v4) | Parametrizado |
| Esquema SUMOTO (`db_models`, repositorios de solicitud/evaluación/ofertas) | Alejandro | Tipos portables (PostgreSQL y SQLite) |
| Motor de elegibilidad por producto de aliado | Alejandro | Se ejecuta tras una aprobación y genera ofertas |
| Auditoría de evaluaciones | Juan | Tabla `motor_evaluacion_auditoria` |
| Clientes Experian (OAuth Okta/SPLA, HDC+, Valor Ingreso) y parsers | Juan | Síncronos, caché de tokens segura entre hilos |
| CLI con reportes JSON/PDF y validación de identidad | Juan | `scripts/evaluar_local.py`; la validación ahora aplica también a la API |
| 146 pruebas | Juan | Portadas (145 pasaban; la que fallaba se corrigió) y ampliadas a 284 |

**Se dejó fuera:** la UI Streamlit (decisión del ensamble: solo API), `archive/`
(scripts históricos), `.git`, `venv`, `motor_rechazo.db`, `package-lock.json`,
`scripts/demo_motor.py` y `verificar_claves.py` (usaban parámetros obsoletos / eran de la UI),
configuración de Preselecta y SOAP (sin uso).

## 2. Diferencias de negocio resueltas (manda la PPT v4)

| Tema | BRD (Alejandro) | PPT v4 (Juan) — **vigente** |
|------|-----------------|------------------------------|
| Empleado con ingreso BAJO | Aprobado | Estudio E4/E5/E6 → Rechazado |
| Endeudamiento | ≥ 86 % rechaza | ≥ 75 % Estudio (E8), > 90 % Rechazo (R17) |
| Gastos personales | 40 / 45 / 50 % | 50 / 45 / 50 % |
| Base de gastos y endeudamiento | Solo ingreso final | Ingreso final + otros ingresos |
| Cupo sugerido | Tasa 2 % y plazo 24 fijos | Tasa y plazo de la solicitud |
| Ingreso final | Sin respaldo en ingreso declarado; Independiente solo Quanto | Valor Ingreso → Quanto → declarado, todas las ocupaciones |
| Mora 30 vigente, score D, exclusiones | Rechazo directo | Estudio / Codeudor internos (público: Rechazado) |

## 3. Errores encontrados y corregidos

**Motor de Alejandro**
1. `valor_ingreso_service.py` era una copia literal de `motor_decision_service.py`. Ahora calcula el Valor Ingreso.
2. `elegibilidad.service.py` no se podía importar (punto en el nombre del módulo). Renombrado a `elegibilidad_service.py`.
3. Métodos `async` sobre una `Session` síncrona. Todo el flujo quedó síncrono y consistente.
4. El motor leía `valor_ingreso` de evaluaciones anteriores (dato viejo) y guardaba `score=None` al rechazar por filtros duros.
5. `motor_exceptions.py` mencionaba un `error_middleware.py` que no existía; no había API, `main`, configuración ni pruebas. Creados.
6. `UUID`/`JSONB` exclusivos de PostgreSQL impedían probar sin servidor. Tipos portables.
7. `cuota_a_valor_mensual` fallaba con periodicidades en el formato que entrega HDC+; ahora usa mensual por defecto.

**Motor de Juan**
1. `parametros.json` (800/700/…) y los `DEFAULTS` del store (3,0/2,0/1,5; cámara 5/3/2/1 invertida) contradecían la PPT v4 que usaban sus propias pruebas: **la API evaluaba con cortes equivocados**.
2. Dos `parametros.json` distintos (edad máxima 65 y 75).
3. Con `edad_maxima_be = 65` y comparación `>=`, se rechazaba a los de 65 años (la PPT dice < 66).
4. Umbral Telcos inconsistente: 300.000 fijo en rechazo y 100.000 (`saldo_mora_be`) en estudio. Unificado en `saldo_mora_be = 300.000`.
5. El score se sustituía en silencio por el primero del reporte si no estaba el modelo contratado. Ahora no se sustituye (R20 + advertencia).
6. `rich` faltaba en dependencias: 2 archivos de pruebas no cargaban.
7. Prueba `test_demo_motor_cliente_aprobado` fallaba (no enviaba Valor Ingreso → GRIS).
8. Escenarios mock: el “aprobado” salía rechazado (sin Valor Ingreso), los vectores ponían la mora fuera de la ventana de 12 meses y el “endeudamiento_alto” tenía cuotas de 800 pesos. Reescritos y verificados por prueba.
9. La validación de identidad solo existía en el CLI; la API podía evaluar el reporte de otra persona. Ahora aplica en todos los flujos.
10. Datos personales reales en el repositorio (`resultado*.json`, `solicitud*.json` con cédulas, IP de servidor en `.env.example`, base SQLite). Excluidos; el fixture HDC se anonimizó.

## 4. Puntos que negocio debe confirmar

1. **Gastos personales 50 % para ≥ 2 SMMLV** (igual a la banda baja). Parece un error de transcripción de la PPT; el BRD decía 40 %. Parámetro `gastos_personales_pct_alto`.
2. **Cupo sugerido con tasa y plazo de la solicitud**: con la PPT v4 la cuota sugerida es igual a la capacidad de pago por construcción, así que E9 equivale a “cuota de la moto > capacidad de pago”.
3. **Orientación del vector de comportamiento**: se asume carácter 0 = mes más reciente. Confirmar con el manual HDC+ de la versión contratada.
4. **R6 “Mora 60 vigente”** se evalúa en la ventana de 12 meses, por lo que coincide casi siempre con R8. Confirmar si “vigente” debe ser solo el mes actual.
5. **Ingreso declarado como respaldo** (PPT v4): permite aprobar con un ingreso no verificado cuando no hay Valor Ingreso ni Quanto.
6. **Valores de `solicitud_credito.decision`**: se escribe `APROBADO` / `RECHAZADO` (constante `DECISION_DB`). Verificar contra el ENUM de `schema.sql`.
7. **`num_solicitud`** lo genera la base de datos; confirmar que `schema.sql` tenga la secuencia.
8. **SMMLV** en `.env` (1.750.905 tomado de la configuración de Juan): confirmar con el decreto vigente.
9. **Supuestos del ensamble**: persona jurídica se detecta por tipo de documento (NIT/PJE); RUNT y nacionalidad llegan en la solicitud (no hay integración); en elegibilidad se aplica también `aliado_producto.score_min` además de las reglas.

## 5. Verificación realizada

- 284 pruebas automáticas en verde (`pytest`) y lint sin observaciones (`ruff`).
- Prueba diferencial: 4.000 solicitudes aleatorias (ocupaciones, scores, vectores,
  estados, Telcos, codeudores, Valor Ingreso, Quanto) evaluadas con el motor original de
  Juan (con los valores de la PPT v4) y con este motor: **0 diferencias en la decisión
  pública** (114 aprobadas). Las listas de causales difieren a propósito: este motor
  reporta todas las causales ordenadas por prioridad y agrega R21–R23 del BRD.
- Arranque real con `uvicorn` y evaluación por HTTP de la solicitud de ejemplo.
