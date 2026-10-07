"""
Perfil de score, perfil de ingreso y matriz de decisión
(PPT v4 + BRD).

PERFIL SCORE
    Empleado / Pensionado            -> escalera Score_EP_1..4
    Independiente / Fuerzas Militares -> escalera Score_IF_1..4
        score >= S1 -> A ; >= S2 -> B ; >= S3 -> C ; >= S4 -> D
        piso <= score < S4 -> Rechazo R14 "Score por debajo del punto de corte"
        score < piso (150)  -> Rechazo R23 "Cliente sin experiencia crediticia"

PERFIL INGRESO (INGRESO_FINAL en SMMLV)
    Empleado: ALTO >= E1, MEDIO >= E2, BAJO >= E3, todos exigiendo
        continuidad (Valor Ingreso: indefinido >= Meses_Cont_1, fijo /
        obra-labor >= Meses_Cont_2). Con ingreso >= E3 sin continuidad
        -> GRIS. Ingreso < E3 -> Rechazo R15.
    Pensionado / FFMM: ALTO >= PF1, MEDIO >= PF2, BAJO >= PF3, < PF3 -> R15.
    Independiente: ALTO >= I1, MEDIO >= I2, BAJO >= I3, GRIS > I4, <= I4 -> R15.

MATRIZ POR OCUPACIÓN (PPT v4)
    Empleado:
        D           -> RECHAZO (R25 "Perfil Score D")
        ALTO/MEDIO  -> Aprobado
        BAJO        -> Aprobado (E4 score A, E5 score B, E6 score C)
        GRIS        -> RECHAZO (RC1 "No cumple continuidad")

    Pensionado:
        D           -> RECHAZO (R25 "Perfil Score D")
        ALTO/MEDIO  -> Aprobado
        BAJO        -> RECHAZO (E4 score A, E5 score B, E6 score C)
        GRIS        -> RECHAZO (RC1 "No cumple continuidad")

    Fuerzas Militares:
        D           -> RECHAZO (R25 "Perfil Score D")
        ALTO/MEDIO  -> Aprobado
        BAJO        -> RECHAZO (E4 score A, E5 score B, E6 score C)
        GRIS        -> RECHAZO (R15 "Ingreso por debajo del permitido")

    Independiente (además exige años de Cámara de Comercio):
        mínimo de años: ALTO Anios_Cam_1, MEDIO Anios_Cam_2, BAJO Anios_Cam_3,
        GRIS o score D Anios_Cam_4. Sin Cámara -> Rechazo R16; con Cámara
        pero sin la antigüedad exigida -> Rechazo R24.
        Luego: D -> RECHAZO ; ALTO/MEDIO -> Aprobado ; BAJO -> RECHAZO ;
        GRIS -> RECHAZO (R15 "Ingreso por debajo del permitido").
"""

from dataclasses import dataclass
from decimal import Decimal

from backend.models.enums import Causal, Decision, Ocupacion, PerfilIngreso, PerfilScore, TipoContrato
from backend.models.motor_models import Solicitud
from backend.services.motor_parametros import MotorParametros

_OCUPACIONES_ESCALERA_EP = (Ocupacion.EMPLEADO, Ocupacion.PENSIONADO)
_OCUPACIONES_ESCALERA_IF = (Ocupacion.INDEPENDIENTE, Ocupacion.FUERZAS_MILITARES)


@dataclass
class ResultadoPerfilScore:
    perfil: PerfilScore | None = None
    decision_forzada: Decision | None = None
    causal_forzada: Causal | None = None
    razon: str = ""


@dataclass
class ResultadoPerfilIngreso:
    perfil: PerfilIngreso | None = None
    decision_forzada: Decision | None = None
    causal_forzada: Causal | None = None
    razon: str = ""


@dataclass
class ResultadoDecision:
    decision: Decision
    causal: Causal | None = None
    razon: str = ""


# ---------------------------------------------------------------------------
# Perfil de score
# ---------------------------------------------------------------------------
def asignar_perfil_score(
    score: Decimal | float | None,
    solicitud: Solicitud,
    params: MotorParametros,
) -> ResultadoPerfilScore:
    if score is None:
        return ResultadoPerfilScore(razon="Sin score disponible")

    score_d = Decimal(str(score))
    if solicitud.ocupacion in _OCUPACIONES_ESCALERA_EP:
        s1, s2, s3, s4 = params.score_ep_1, params.score_ep_2, params.score_ep_3, params.score_ep_4
    else:
        s1, s2, s3, s4 = params.score_if_1, params.score_if_2, params.score_if_3, params.score_if_4

    if score_d >= s1:
        return ResultadoPerfilScore(PerfilScore.A, razon=f"Score {score_d} >= {s1}")
    if score_d >= s2:
        return ResultadoPerfilScore(PerfilScore.B, razon=f"Score {score_d} en [{s2}, {s1})")
    if score_d >= s3:
        return ResultadoPerfilScore(PerfilScore.C, razon=f"Score {score_d} en [{s3}, {s2})")
    if score_d >= s4:
        return ResultadoPerfilScore(PerfilScore.D, razon=f"Score {score_d} en [{s4}, {s3})")
    if score_d < params.score_piso_experiencia:
        return ResultadoPerfilScore(
            None,
            Decision.RECHAZADO,
            Causal.R23,
            f"Score {score_d} < {params.score_piso_experiencia} (sin experiencia crediticia)",
        )
    return ResultadoPerfilScore(None, Decision.RECHAZADO, Causal.R14, f"Score {score_d} < {s4} (punto de corte)")


# ---------------------------------------------------------------------------
# Perfil de ingreso
# ---------------------------------------------------------------------------
def cumple_continuidad(
    tipo_contrato: TipoContrato | None,
    params: MotorParametros,
    meses_continuidad: int | None,
) -> bool:
    """Continuidad según Valor Ingreso; contrato NA o vacío no cumple."""
    meses = meses_continuidad or 0
    if tipo_contrato == TipoContrato.INDEFINIDO:
        return meses >= params.meses_cont_1
    if tipo_contrato in (TipoContrato.FIJO, TipoContrato.OBRA_LABOR):
        return meses >= params.meses_cont_2
    return False


def _rechazo_ingreso(razon: str) -> ResultadoPerfilIngreso:
    return ResultadoPerfilIngreso(None, Decision.RECHAZADO, Causal.R15, razon)


def asignar_perfil_ingreso(
    ingreso_final_smmlv: Decimal,
    solicitud: Solicitud,
    params: MotorParametros,
    meses_continuidad: int | None = None,
) -> ResultadoPerfilIngreso:
    x = ingreso_final_smmlv

    if solicitud.ocupacion == Ocupacion.EMPLEADO:
        if x < params.ingreso_e_3:
            return _rechazo_ingreso(f"Ingreso {x:.4f} SMMLV < {params.ingreso_e_3}")
        if not cumple_continuidad(solicitud.tipo_contrato, params, meses_continuidad):
            return ResultadoPerfilIngreso(
                PerfilIngreso.GRIS,
                razon=f"Ingreso suficiente pero sin continuidad ({meses_continuidad or 0} meses, "
                f"contrato {solicitud.tipo_contrato or 'sin dato'})",
            )
        if x >= params.ingreso_e_1:
            return ResultadoPerfilIngreso(
                PerfilIngreso.ALTO, razon=f"Ingreso {x:.4f} >= {params.ingreso_e_1} y cumple continuidad"
            )
        if x >= params.ingreso_e_2:
            return ResultadoPerfilIngreso(
                PerfilIngreso.MEDIO, razon=f"Ingreso {x:.4f} >= {params.ingreso_e_2} y cumple continuidad"
            )
        return ResultadoPerfilIngreso(
            PerfilIngreso.BAJO, razon=f"Ingreso {x:.4f} >= {params.ingreso_e_3} y cumple continuidad"
        )

    if solicitud.ocupacion in (Ocupacion.PENSIONADO, Ocupacion.FUERZAS_MILITARES):
        if x >= params.ingreso_pf_1:
            return ResultadoPerfilIngreso(PerfilIngreso.ALTO, razon=f"PF: {x:.4f} >= {params.ingreso_pf_1}")
        if x >= params.ingreso_pf_2:
            return ResultadoPerfilIngreso(PerfilIngreso.MEDIO, razon=f"PF: {x:.4f} >= {params.ingreso_pf_2}")
        if x >= params.ingreso_pf_3:
            return ResultadoPerfilIngreso(PerfilIngreso.BAJO, razon=f"PF: {x:.4f} >= {params.ingreso_pf_3}")
        return _rechazo_ingreso(f"PF: ingreso {x:.4f} SMMLV < {params.ingreso_pf_3}")

    # Independiente
    if x >= params.ingreso_i_1:
        return ResultadoPerfilIngreso(PerfilIngreso.ALTO, razon=f"Ind: {x:.4f} >= {params.ingreso_i_1}")
    if x >= params.ingreso_i_2:
        return ResultadoPerfilIngreso(PerfilIngreso.MEDIO, razon=f"Ind: {x:.4f} >= {params.ingreso_i_2}")
    if x >= params.ingreso_i_3:
        return ResultadoPerfilIngreso(PerfilIngreso.BAJO, razon=f"Ind: {x:.4f} >= {params.ingreso_i_3}")
    if x > params.ingreso_i_4:
        return ResultadoPerfilIngreso(PerfilIngreso.GRIS, razon=f"Ind: {x:.4f} > {params.ingreso_i_4}")
    return _rechazo_ingreso(f"Ind: ingreso {x:.4f} SMMLV <= {params.ingreso_i_4}")


# ---------------------------------------------------------------------------
# Matriz de decisión
# ---------------------------------------------------------------------------
_CAUSAL_BAJO = {PerfilScore.A: Causal.E4, PerfilScore.B: Causal.E5, PerfilScore.C: Causal.E6}


def cruzar_perfiles_empleado(
    perfil_score: PerfilScore | None,
    perfil_ingreso: PerfilIngreso | None,
) -> ResultadoDecision:
    """Matriz para Empleado."""
    if perfil_score == PerfilScore.D:
        return ResultadoDecision(Decision.RECHAZADO, Causal.R25, "Perfil Score D")
    if perfil_score is None or perfil_ingreso is None:
        return ResultadoDecision(Decision.ESTUDIO, None, "Perfil incompleto")
    if perfil_ingreso in (PerfilIngreso.ALTO, PerfilIngreso.MEDIO):
        return ResultadoDecision(Decision.APROBADO, None, f"Score {perfil_score} con ingreso {perfil_ingreso}")
    if perfil_ingreso == PerfilIngreso.BAJO:
        # Empleado + BAJO -> Aprobado
        return ResultadoDecision(
            Decision.APROBADO, _CAUSAL_BAJO[perfil_score], f"Ingreso bajo con score {perfil_score}"
        )
    return ResultadoDecision(Decision.RECHAZADO, Causal.RC1, "No cumple continuidad")


def cruzar_perfiles_pensionado(
    perfil_score: PerfilScore | None,
    perfil_ingreso: PerfilIngreso | None,
) -> ResultadoDecision:
    """Matriz para Pensionado."""
    if perfil_score == PerfilScore.D:
        return ResultadoDecision(Decision.RECHAZADO, Causal.R25, "Perfil Score D")
    if perfil_score is None or perfil_ingreso is None:
        return ResultadoDecision(Decision.ESTUDIO, None, "Perfil incompleto")
    if perfil_ingreso in (PerfilIngreso.ALTO, PerfilIngreso.MEDIO):
        return ResultadoDecision(Decision.APROBADO, None, f"Score {perfil_score} con ingreso {perfil_ingreso}")
    if perfil_ingreso == PerfilIngreso.BAJO:
        # Pensionado + BAJO -> Rechazado
        return ResultadoDecision(
            Decision.RECHAZADO, _CAUSAL_BAJO[perfil_score], f"Ingreso bajo con score {perfil_score}"
        )
    return ResultadoDecision(Decision.RECHAZADO, Causal.RC1, "No cumple continuidad")


def cruzar_perfiles_ffmm(
    perfil_score: PerfilScore | None,
    perfil_ingreso: PerfilIngreso | None,
) -> ResultadoDecision:
    """Matriz para Fuerzas Militares."""
    if perfil_score == PerfilScore.D:
        return ResultadoDecision(Decision.RECHAZADO, Causal.R25, "Perfil Score D")
    if perfil_score is None or perfil_ingreso is None:
        return ResultadoDecision(Decision.ESTUDIO, None, "Perfil incompleto")
    if perfil_ingreso in (PerfilIngreso.ALTO, PerfilIngreso.MEDIO):
        return ResultadoDecision(Decision.APROBADO, None, f"Score {perfil_score} con ingreso {perfil_ingreso}")
    if perfil_ingreso == PerfilIngreso.BAJO:
        # FFMM + BAJO -> Rechazado
        return ResultadoDecision(
            Decision.RECHAZADO, _CAUSAL_BAJO[perfil_score], f"Ingreso bajo con score {perfil_score}"
        )
    return ResultadoDecision(Decision.RECHAZADO, Causal.R15, "Ingreso por debajo del permitido")


def cruzar_perfiles_independiente(
    perfil_score: PerfilScore | None,
    perfil_ingreso: PerfilIngreso | None,
    anios_camara: Decimal | int | None,
    params: MotorParametros,
) -> ResultadoDecision:
    """Matriz para Independiente."""
    if perfil_score is None or perfil_ingreso is None:
        return ResultadoDecision(Decision.ESTUDIO, None, "Perfil incompleto")

    if perfil_score == PerfilScore.D:
        minimo = params.anios_cam_4
    else:
        minimo = {
            PerfilIngreso.ALTO: params.anios_cam_1,
            PerfilIngreso.MEDIO: params.anios_cam_2,
            PerfilIngreso.BAJO: params.anios_cam_3,
            PerfilIngreso.GRIS: params.anios_cam_4,
        }[perfil_ingreso]

    if anios_camara is None:
        return ResultadoDecision(
            Decision.RECHAZADO,
            Causal.R16,
            "Independiente sin Cámara de Comercio registrada",
        )

    anios = Decimal(str(anios_camara))
    if anios < minimo:
        return ResultadoDecision(
            Decision.RECHAZADO, Causal.R24, f"Antigüedad en Cámara de Comercio {anios} < {minimo} años"
        )

    if perfil_score == PerfilScore.D:
        return ResultadoDecision(Decision.RECHAZADO, Causal.R25, "Perfil Score D")
    if perfil_ingreso in (PerfilIngreso.ALTO, PerfilIngreso.MEDIO):
        return ResultadoDecision(Decision.APROBADO, None, f"Independiente con ingreso {perfil_ingreso}")
    if perfil_ingreso == PerfilIngreso.BAJO:
        # Independiente + BAJO -> Rechazado
        return ResultadoDecision(Decision.RECHAZADO, _CAUSAL_BAJO[perfil_score], "Ingreso bajo para independiente")
    return ResultadoDecision(Decision.RECHAZADO, Causal.R15, "Ingreso por debajo del permitido")


def decidir_por_ocupacion(
    solicitud: Solicitud,
    perfil_score: PerfilScore | None,
    perfil_ingreso: PerfilIngreso | None,
    params: MotorParametros,
) -> ResultadoDecision:
    if solicitud.ocupacion == Ocupacion.EMPLEADO:
        return cruzar_perfiles_empleado(perfil_score, perfil_ingreso)
    if solicitud.ocupacion == Ocupacion.PENSIONADO:
        return cruzar_perfiles_pensionado(perfil_score, perfil_ingreso)
    if solicitud.ocupacion == Ocupacion.FUERZAS_MILITARES:
        return cruzar_perfiles_ffmm(perfil_score, perfil_ingreso)
    if solicitud.ocupacion == Ocupacion.INDEPENDIENTE:
        return cruzar_perfiles_independiente(perfil_score, perfil_ingreso, solicitud.anios_camara_comercio, params)
    return ResultadoDecision(Decision.ESTUDIO, None, "Ocupación no reconocida")
