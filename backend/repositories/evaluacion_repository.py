import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.db_models.models import (
    CapacidadPago,
    CriterioEvaluacion,
    EvaluacionCredito,
    SolicitudCausal,
)
from backend.models.enums import Causal
from backend.models.motor_models import ResultadoMotor


class EvaluacionRepository:
    """
    Escritura de evaluacion_credito, capacidad_pago y solicitud_causal.

    En PostgreSQL el trigger trg_evaluacion_vigente (schema.sql) ya
    desmarca versiones previas; aquí se hace también de forma explícita
    para que el comportamiento sea idéntico en cualquier motor de base
    de datos (la operación es idempotente con el trigger).
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def _siguiente_version(self, modelo, id_solicitud: uuid.UUID) -> int:
        ultima = (
            self.db.query(modelo).filter(modelo.id_solicitud == id_solicitud).order_by(modelo.version.desc()).first()
        )
        return ultima.version + 1 if ultima else 1

    def _desmarcar_vigentes(self, modelo, id_solicitud: uuid.UUID) -> None:
        (
            self.db.query(modelo)
            .filter(modelo.id_solicitud == id_solicitud, modelo.vigente.is_(True))
            .update({modelo.vigente: False}, synchronize_session="fetch")
        )

    def crear_evaluacion(
        self,
        id_solicitud: uuid.UUID,
        score: float | Decimal | None,
        **campos_evaluacion,
    ) -> EvaluacionCredito:
        nueva_version = self._siguiente_version(EvaluacionCredito, id_solicitud)
        self._desmarcar_vigentes(EvaluacionCredito, id_solicitud)

        evaluacion = EvaluacionCredito(
            id_solicitud=id_solicitud,
            version=nueva_version,
            vigente=True,
            score=score,
            **campos_evaluacion,
        )
        self.db.add(evaluacion)
        self.db.flush()
        return evaluacion

    def crear_evaluacion_motor(self, id_solicitud: uuid.UUID, resultado: ResultadoMotor) -> EvaluacionCredito:
        """Persiste un ResultadoMotor en evaluacion_credito con los indicadores de buró."""
        ind = resultado.indicadores_buro
        codigo_excl = ind.get("score_codigo_exclusion")
        return self.crear_evaluacion(
            id_solicitud=id_solicitud,
            score=resultado.score_consultado,
            valor_ingreso=resultado.valor_ingreso,
            ingreso_final=resultado.ingreso_final,
            endeudamiento=resultado.endeudamiento,
            capacidad_pago=resultado.capacidad_pago,
            quanto3_medio=resultado.quanto_medio,
            mora_historica_90=ind.get("moras_90_historicas", 0),
            mora_historica_60=ind.get("moras_60_historicas", 0),
            mora_historica_30=ind.get("moras_30_historicas", 0),
            mora_60=ind.get("mora_60_vigente", 0),
            mora_30=ind.get("mora_30_vigente", 0),
            embargo=ind.get("embargos", 0),
            dudoso_recaudo=ind.get("dudoso_recaudo", 0),
            cartera_castigada=ind.get("cartera_castigada", 0),
            cancelaciones_negativas=ind.get("cancelaciones_mal_manejo", 0),
            obligaciones_reestructuradas=ind.get("reestructuraciones", 0),
            calificacion_diferente_ab=ind.get("calificaciones_negativas", 0),
            documento_vigente=ind.get("documento_vigente"),
            calificacion=ind.get("peor_calificacion"),
            reportado_fallecido=bool(ind.get("reportado_fallecido", False)),
            score_codigo_exclusion=str(codigo_excl) if codigo_excl is not None else None,
            perfil_score=resultado.perfil_score.value if resultado.perfil_score else None,
            perfil_ingreso=resultado.perfil_ingreso.value if resultado.perfil_ingreso else None,
            decision_interna=resultado.decision_interna.value,
        )

    def crear_capacidad_pago(self, id_solicitud: uuid.UUID, resultado: ResultadoMotor) -> CapacidadPago:
        version = self._siguiente_version(CapacidadPago, id_solicitud)
        self._desmarcar_vigentes(CapacidadPago, id_solicitud)
        capacidad = CapacidadPago(
            id_solicitud=id_solicitud,
            version=version,
            vigente=True,
            salario_minimo=resultado.smmlv,
            ingreso_final=resultado.ingreso_final,
            ingreso_final_smlmv=resultado.ingreso_final_smmlv,  # nombre de columna de schema.sql
            gastos_personales=resultado.gastos_personales,
            disponible_1=resultado.disponible,
            capacidad_pago_2=resultado.capacidad_pago,
            tasa_cupo=resultado.solicitud.tasa,
            plazo_cupo=resultado.solicitud.plazo,
            cupo_calculado=resultado.cupo_sugerido,
            cupo_aprobado=None,  # lo define el proceso comercial, no el motor
        )
        self.db.add(capacidad)
        self.db.flush()
        return capacidad

    def reemplazar_causales(self, id_solicitud: uuid.UUID, resultado: ResultadoMotor) -> list[SolicitudCausal]:
        return self.registrar_causales(id_solicitud, resultado.causales)

    def registrar_causales(self, id_solicitud: uuid.UUID, causales: list[Causal]) -> list[SolicitudCausal]:
        """Desactiva las causales vigentes y registra las nuevas."""
        (
            self.db.query(SolicitudCausal)
            .filter(SolicitudCausal.id_solicitud == id_solicitud, SolicitudCausal.activa.is_(True))
            .update({SolicitudCausal.activa: False}, synchronize_session="fetch")
        )
        criterios = {
            c.codigo: c.id_criterio
            for c in self.db.query(CriterioEvaluacion).filter(
                CriterioEvaluacion.codigo.in_([c.codigo for c in causales])
            )
        } if causales else {}
        nuevas = [
            SolicitudCausal(
                id_solicitud=id_solicitud,
                id_criterio=criterios.get(c.codigo),
                codigo=c.codigo,
                descripcion=c.value,
                activa=True,
            )
            for c in causales
        ]
        self.db.add_all(nuevas)
        self.db.flush()
        return nuevas
