# Benchmark del motor de decisión — D97

Fecha de medición: 2026-10-20 · Commit de trabajo actual · Equipo: estación
de desarrollo Windows (números de referencia, no SLA; en CI/servidor
varían por hardware).

## Qué se midió

| Nivel | Función | Incluye |
|---|---|---|
| Motor puro | `EvaluacionService.evaluar_con_reportes` | Validación de identidad + reglas de consistencia + `MotorDecision.evaluar` (filtros duros, score, capacidad de pago, cupo) |
| End-to-end | `POST /api/solicitudes/{id}/evaluar` | Pre-filtro SIMIT (mock), escenario de buró, motor, **persistencia completa**: evaluación versionada, capacidad de pago, causales, actualización de decisión/estado, generación de ofertas (solo aprobado), auditoría |

Fuera de alcance: consulta real a Experian/Placapi (red), Postgres en
producción (aquí SQLite en memoria), concurrencia. Esos son los
componentes que dominan la latencia real — el benchmark demuestra que
el código propio no es el cuello de botella.

## Resultados — motor puro (ms por evaluación, n=100 por escenario)

| Escenario | media | p50 | p95 | p99 | máx |
|---|---|---|---|---|---|
| aprobado | 0.50 | 0.47 | 0.66 | 0.79 | 0.79 |
| castigada | 0.62 | 0.51 | 1.08 | 2.46 | 2.47 |
| embargo | 0.50 | 0.46 | 0.66 | 1.08 | 1.09 |
| endeudamiento_alto | 0.64 | 0.55 | 1.06 | 1.42 | 1.42 |
| exclusion_score | 0.52 | 0.47 | 0.75 | 1.08 | 1.09 |
| fallecido | 0.65 | 0.52 | 1.32 | 1.77 | 1.77 |
| mora_30 | 0.53 | 0.50 | 0.73 | 0.92 | 0.92 |
| mora_90 | 0.56 | 0.53 | 0.80 | 1.80 | 1.81 |
| perfil_bajo | 0.55 | 0.50 | 0.84 | 1.05 | 1.05 |
| score_bajo | 0.54 | 0.51 | 0.77 | 1.61 | 1.62 |
| simit_multas* | 0.51 | 0.47 | 0.77 | 1.17 | 1.17 |
| sin_experiencia | 0.68 | 0.54 | 1.40 | 1.87 | 1.88 |
| sin_valor_ingreso | 0.59 | 0.49 | 1.25 | 1.44 | 1.44 |

\* `simit_multas` se evalúa como `aprobado` porque el benchmark mide el
motor, no el pre-filtro (ver `crear_escenario`).

## Resultados — endpoint POST /evaluar (ms por request, n=25)

| Camino | media | p50 | p95 | p99 | máx |
|---|---|---|---|---|---|
| aprobado (genera ofertas) | 33.3 | 33.0 | 42.9 | 44.5 | 43.4 |
| mora_90 (rechazo, sin ofertas) | 37.7 | 39.1 | 44.4 | 45.4 | 44.7 |

## Interpretación

- **La lógica de decisión cuesta ~0.5 ms.** El p99 global es 2.5 ms —
  con 70 créditos/día la capacidad del motor sobra por varios órdenes
  de magnitud (~1.700 evaluaciones/segundo teóricas).
- **El ~97% del tiempo por request es persistencia + HTTP**, no las
  reglas: ~33–38 ms end-to-end vs ~0.6 ms de motor. Las escrituras
  (evaluación + capacidad + causales + ofertas + auditoría) dominan.
- Si la latencia importa algún día, la palanca no es optimizar el
  motor sino la persistencia: índices, lotes de INSERT, o mover la
  auditoría a async. A esta escala no es necesario.
- El rechazo (`mora_90`) es marginalmente más lento pese a no generar
  ofertas — la diferencia está dentro del ruido de la medición.

## Reproducir

```bash
.venv/Scripts/python.exe -m pytest tests/perf/test_benchmark_motor.py -s
```

El archivo `tests/perf/test_benchmark_motor.py` corre dentro de la
suite normal: además de imprimir la tabla, falla si el p95 supera un
guard anti-regresión burdo (500 ms motor puro / 1500 ms endpoint) —
detecta una degradación de orden de magnitud, no un SLA.
