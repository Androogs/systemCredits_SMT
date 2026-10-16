"""
Normalización entre los enums del dominio y los valores que aceptan
los tipos ENUM de PostgreSQL (schema.sql).

El dominio usa etiquetas legibles ("Empleado", "Obra o Labor",
"Aprobado") mientras el esquema SUMOTO define los ENUM en snake_case
('empleado', 'obra_labor', 'aprobado'). Estos mapas son la única
frontera de traducción: los services escriben *_A_DB y leen con
*_DESDE_DB, tolerando también valores legados escritos a mano.
"""

from backend.models.enums import DecisionFinal, Ocupacion, TipoContrato


def _normalizar(valor: str) -> str:
    return valor.strip().lower().replace(" ", "_")


OCUPACION_A_DB = {
    Ocupacion.EMPLEADO: "empleado",
    Ocupacion.INDEPENDIENTE: "independiente",
    Ocupacion.PENSIONADO: "pensionado",
    Ocupacion.FUERZAS_MILITARES: "fuerzas_militares",
}
OCUPACION_DESDE_DB = {_normalizar(v): k for k, v in OCUPACION_A_DB.items()} | {
    _normalizar(o.value): o for o in Ocupacion
}


TIPO_CONTRATO_A_DB = {
    TipoContrato.INDEFINIDO: "indefinido",
    TipoContrato.FIJO: "fijo",
    TipoContrato.OBRA_LABOR: "obra_labor",
    TipoContrato.NA: "no_aplica",
}
TIPO_CONTRATO_DESDE_DB = {_normalizar(v): k for k, v in TIPO_CONTRATO_A_DB.items()} | {
    _normalizar(t.value): t for t in TipoContrato
}


# solicitud_credito.decision es ENUM ('aprobado', 'rechazado',
# 'perfil_gris'); la decisión pública del motor es binaria.
DECISION_A_DB = {
    DecisionFinal.APROBADO: "aprobado",
    DecisionFinal.RECHAZADO: "rechazado",
}


def estado_solicitud(resultado) -> str:
    """Estado de solicitud_credito tras una evaluación.

    Sin comité: las causales internas Estudio / Requiere Codeudor ya no
    dejan la solicitud 'en_revision'; siguen la decisión pública.
    """
    return "aprobada" if resultado.decision == DecisionFinal.APROBADO else "rechazada"
