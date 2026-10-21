"""
Motor de reglas de elegibilidad por producto de aliado.

A diferencia del motor de decisión, aquí la mecánica SÍ es genérica:
cada fila de aliado_regla_elegibilidad trae {campo, operador,
valor_json} y los operadores soportados están fijados por el CHECK de
schema.sql (>=, <=, =, !=, IN, NOT IN).

Solo se ejecuta sobre solicitudes APROBADAS por el motor de decisión
(ver evaluacion_service). Los campos disponibles para las reglas son
los de CAMPOS_ELEGIBILIDAD; un campo fuera del catálogo se registra y
la regla se considera NO cumplida (no se aprueba por un dato ausente).
"""

import uuid
from decimal import Decimal
from typing import Any

from backend.db_models.models import AliadoProducto, OfertaCredito
from backend.services.finanzas import cuota_anualidad
from backend.services.seguro_service import cuota_seguro
from backend.utils.loggers import get_logger

logger = get_logger("motor_decision.elegibilidad")

# Catálogo de campos que el motor entrega a las reglas de elegibilidad.
CAMPOS_ELEGIBILIDAD = {
    "score",
    "perfil_score",
    "perfil_ingreso",
    "ingreso_final",
    "ingreso_final_smmlv",
    "endeudamiento",
    "capacidad_pago",
    "cupo_sugerido",
    "edad",
    "ocupacion",
    "monto_solicitado",
    "plazo",
}


def _num(valor: Any) -> Any:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return Decimal(str(valor))
    return valor


def _cmp(fn):
    def _aplicar(valor, esperado):
        if valor is None:
            return False
        try:
            return fn(_num(valor), _num(esperado))
        except TypeError:
            return False

    return _aplicar


_OPERADORES = {
    ">=": _cmp(lambda v, e: v >= e),
    "<=": _cmp(lambda v, e: v <= e),
    "=": _cmp(lambda v, e: v == e),
    "!=": _cmp(lambda v, e: v != e),
    "IN": lambda v, e: v is not None and _num(v) in [_num(x) for x in (e or [])],
    "NOT IN": lambda v, e: v is not None and _num(v) not in [_num(x) for x in (e or [])],
}


def _acotar(valor, minimo, maximo):
    if valor is None:
        return None
    if minimo is not None and valor < minimo:
        return minimo
    if maximo is not None and valor > maximo:
        return maximo
    return valor


class EligibilidadService:
    def evaluar_producto(
        self,
        id_solicitud: uuid.UUID,
        producto: AliadoProducto,
        datos_solicitud: dict[str, Any],
    ) -> OfertaCredito:
        motivos: list[str] = []

        for regla in producto.reglas:
            operador_fn = _OPERADORES.get(regla.operador.strip().upper())
            if operador_fn is None:
                raise ValueError(f"Operador no soportado: {regla.operador}")
            if regla.campo not in CAMPOS_ELEGIBILIDAD:
                logger.warning("Campo de elegibilidad fuera del catálogo: %s", regla.campo)
            valor_actual = datos_solicitud.get(regla.campo)
            if not operador_fn(valor_actual, regla.valor_json):
                motivos.append(f"{regla.campo} {regla.operador} {regla.valor_json} (valor actual: {valor_actual})")

        if producto.score_min is not None:
            score = datos_solicitud.get("score")
            if score is None or Decimal(str(score)) < producto.score_min:
                motivos.append(f"score >= {producto.score_min} (valor actual: {score})")

        oferta = OfertaCredito(
            id_solicitud=id_solicitud,
            id_aliado_producto=producto.id_aliado_producto,
            elegible=not motivos,
            motivo_no_elegible="; ".join(motivos) if motivos else None,
        )
        if oferta.elegible:
            cupo = datos_solicitud.get("cupo_sugerido")
            monto_min = getattr(producto, "monto_min", None)
            if (
                cupo is not None
                and monto_min is not None
                and Decimal(str(cupo)) < Decimal(str(monto_min))
            ):
                # La capacidad real no alcanza ni el mínimo comercial:
                # la oferta no se infla sobre la capacidad del cliente.
                oferta.elegible = False
                oferta.motivo_no_elegible = (
                    f"cupo_sugerido {cupo} por debajo del "
                    f"monto_min {monto_min} del producto"
                )
            else:
                self._poblar_terminos(oferta, producto, datos_solicitud)
        return oferta

    @staticmethod
    def _poblar_terminos(oferta: OfertaCredito, producto: AliadoProducto, datos: dict[str, Any]) -> None:
        """
        Términos de la oferta: ck_oferta_elegible exige tasa, monto y
        cuota no nulos en ofertas elegibles. El monto ofrecido es lo que
        el cliente pidió topado por el cupo del motor (si pidió más de
        lo que su capacidad aprueba, se ofrece el cupo), acotado al
        rango comercial del producto.
        """
        # La tasa ofrecida es la que evaluó el motor (tasa_referencia del
        # request): el cupo y la cuota que vio el asesor responden a esa
        # tasa; el rango del catálogo queda como respaldo.
        tasa = datos.get("tasa_referencia") or getattr(producto, "tasa_min", None)
        plazo = _acotar(
            datos.get("plazo"),
            getattr(producto, "plazo_min_meses", None),
            getattr(producto, "plazo_max_meses", None),
        )
        if plazo is None:
            plazo = getattr(producto, "plazo_min_meses", None) or getattr(producto, "plazo_max_meses", None)
        cupo = datos.get("cupo_sugerido")
        solicitado = datos.get("monto_solicitado")
        if cupo is not None and solicitado is not None:
            monto_base = min(Decimal(str(solicitado)), Decimal(str(cupo)))
        else:
            monto_base = cupo if cupo is not None else solicitado
        monto = _acotar(monto_base, getattr(producto, "monto_min", None), getattr(producto, "monto_max", None))
        oferta.tasa_ofrecida = tasa
        oferta.plazo_ofrecido = int(plazo) if plazo is not None else None
        oferta.monto_aprobado = monto
        if tasa is not None and plazo and monto is not None:
            # cuota_mensual es la cuota TOTAL que paga el cliente:
            # anualidad + seguro de vida deudores (como la carta real).
            cuota = cuota_anualidad(Decimal(str(monto)), Decimal(str(tasa)), int(plazo))
            prima_pct = datos.get("prima_seguro_pct")
            if prima_pct:
                cuota += cuota_seguro(Decimal(str(monto)), Decimal(str(prima_pct)))
            oferta.cuota_mensual = cuota
