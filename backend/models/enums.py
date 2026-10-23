"""
Enumeraciones del dominio del motor de decisión.

Catálogo único de causales: combina la codificación de la PPT v4
(R*, RC*, E*) con las políticas del BRD que la PPT no enumeraba
(nacionalidad, RUNT, cliente sin experiencia crediticia).

Cada causal pertenece a un TIPO de decisión interna:
    R*  -> Rechazado
    RC* -> Rechazado (antes "Requiere Codeudor")
    E*  -> Rechazado (antes "Estudio")

La decisión del sistema es estrictamente binaria (Aprobado / Rechazado):
no hay comité ni estados intermedios — cualquier causal produce
"Rechazado". Los tipos históricos (Estudio, Requiere Codeudor) solo
aparecen en evaluaciones anteriores al cambio.
"""

from enum import StrEnum


class TipoIdentificacion(StrEnum):
    CC = "1"
    NIT = "2"
    PJE = "3"
    CE = "4"
    PAS = "5"
    PPT = "6"
    TI = "7"
    DNI = "8"
    PEP = "9"


# Tipos de documento que NO corresponden a persona natural (BRD:
# exclusión "Clientes diferentes a Persona Natural").
TIPOS_ID_PERSONA_JURIDICA = {TipoIdentificacion.NIT, TipoIdentificacion.PJE}


class Ocupacion(StrEnum):
    EMPLEADO = "Empleado"
    INDEPENDIENTE = "Independiente"
    PENSIONADO = "Pensionado"
    FUERZAS_MILITARES = "Fuerzas Militares"


class TipoContrato(StrEnum):
    INDEFINIDO = "Indefinido"
    FIJO = "Fijo"
    OBRA_LABOR = "Obra o Labor"
    NA = "NA"


class Decision(StrEnum):
    """Estados de trabajo internos. El sistema decide solo
    Aprobado/Rechazado: `ESTUDIO` y `REQUIERE_CODEUDOR` son valores
    históricos que ya no se emiten (D185) — solo aparecen en
    `decision_interna` de evaluaciones antiguas."""

    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"
    ESTUDIO = "Estudio"
    REQUIERE_CODEUDOR = "Requiere Codeudor"


PRIORIDAD_DECISION = {
    Decision.RECHAZADO: 3,
    Decision.REQUIERE_CODEUDOR: 2,
    Decision.ESTUDIO: 1,
    Decision.APROBADO: 0,
}


class DecisionFinal(StrEnum):
    """Únicos estados que se entregan al usuario o a las integraciones."""

    APROBADO = "Aprobado"
    RECHAZADO = "Rechazado"


class PerfilScore(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PerfilIngreso(StrEnum):
    ALTO = "ALTO"
    MEDIO = "MEDIO"
    BAJO = "BAJO"
    GRIS = "GRIS"


class Causal(StrEnum):
    """Catálogo de causales. El valor es la descripción visible."""

    # --- Rechazo (BRD 2.4.1 / PPT v4) ---
    R1 = "Clientes reportados como fallecidos"
    R2 = "Embargos vigentes"
    R3 = "Cancelaciones por mal hábito"
    R4 = "Cartera castigada"
    R5 = "Dudoso recaudo"
    R6 = "Mora 60 días o más vigentes"
    R7 = "Mora histórica 30 días"
    R8 = "Mora histórica 60 días"
    R9 = "Mora histórica 90 días o más"
    R10 = "Calificación diferente A y B"
    R11 = "Reestructuración"
    R12 = "Documento no vigente"
    R13 = "No cumple política de edad"
    R14 = "Score por debajo del punto de corte"
    R15 = "Ingresos por debajo del permitido"
    R16 = "No tiene Cámara de Comercio"
    R17 = "Endeudamiento mayor a 90 por ciento"
    R18 = "Sin disponible"
    R19 = "Sin capacidad de pago"
    R20 = "Información insuficiente para aprobar"
    R21 = "Nacionalidad diferente a colombiana"
    R22 = "Multas en el RUNT"
    R23 = "Cliente sin experiencia crediticia"
    R24 = "No cumple años mínimos de Cámara de Comercio"
    R25 = "Perfil Score D"
    RC1 = "No cumple continuidad"
    # RC2 y RC4 no se emiten hoy; el texto debe ser único (StrEnum
    # convierte valores repetidos en alias del primero).
    RC2 = "Perfil Score D (RC2)"
    RC3 = "Validación de exclusiones"
    RC4 = "Ingreso en zona gris para independiente"
    E1 = "Clientes diferentes a persona natural"
    E2 = "Mora 30 días vigentes"
    E3 = "Sin valor ingreso y quanto fin"
    E4 = "Perfil ingreso bajo"
    E5 = "Perfil ingreso bajo y score B"
    E6 = "Perfil ingreso bajo y score C"
    E7 = "Validación de exclusiones (estudio)"
    E8 = "Endeudamiento mayor a 75 y menor o igual a 90 por ciento"
    E9 = "Sin capacidad para moto solicitada"

    @property
    def codigo(self) -> str:
        return self.name

    @property
    def tipo(self) -> Decision:
        return _TIPO_CAUSAL[self.name]


def _tipo_por_codigo(codigo: str) -> Decision:
    # D185: decisión estrictamente binaria — cualquier causal (R*, RC*,
    # E*) es Rechazado; los tipos Estudio/Codeudor quedaron históricos.
    return Decision.RECHAZADO


_TIPO_CAUSAL = {c.name: _tipo_por_codigo(c.name) for c in Causal}


class EconomicSector(StrEnum):
    """Sectores económicos (Tabla 45 manual HDC+)."""

    FINANCIERO = "1"
    COOPERATIVO = "2"
    REAL = "3"
    TELCOS = "4"


class EstadoDocumento(StrEnum):
    """Estado del documento de identidad (Tabla 2 manual HDC+)."""

    VIGENTE = "00"
    CANCELADA_MUERTE = "21"
    EN_TRAMITE_88 = "88"
    EN_TRAMITE_99 = "99"


# Estados de documento aceptados como vigentes. "25" es la excepción
# del BRD para cédula de extranjería.
ESTADOS_DOCUMENTO_ACEPTADOS = {"00", "25"}


class TipoCuenta(StrEnum):
    """Tipos de cuenta (Tabla 3 manual HDC+)."""

    CCB = "CCB"  # Cuenta corriente bancaria
    TDC = "TDC"  # Tarjeta de crédito
    CBR = "CBR"  # Cartera bancaria rotativa
    CAB = "CAB"  # Cartera bancaria
    AHO = "AHO"  # Cuenta de ahorros
    MCR = "MCR"  # Microcrédito
    CTC = "CTC"  # Cartera telefonía celular
