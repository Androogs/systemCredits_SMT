"""
Validaciones previas a la evaluación: que la solicitud y los reportes
del buró correspondan a la misma persona, y advertencias de
consistencia (edad declarada vs. rango de edad del HDC+).

Una solicitud mezclada con el reporte de otra persona DETIENE la
evaluación (IdentidadNoCoincideError): nunca se decide con datos cruzados.
"""

import re
from datetime import date
from typing import Any

from backend.models.buro_models import RespuestaHDC, RespuestaValorIngreso
from backend.models.motor_models import Solicitud
from backend.services.motor_exceptions import IdentidadNoCoincideError
from backend.utils.fechas import calcular_edad


def normalizar_identificacion(valor: Any) -> str:
    normalizado = re.sub(r"[^0-9a-zA-Z]", "", str(valor or "")).casefold()
    # HDC+ puede devolver el documento como número (sin ceros a la
    # izquierda) o como texto de ancho fijo (con ceros de relleno).
    if normalizado.isdigit():
        return normalizado.lstrip("0") or "0"
    return normalizado


def validar_identidad(
    solicitud: Solicitud,
    hdc: RespuestaHDC,
    valor_ingreso: RespuestaValorIngreso | None,
) -> None:
    persona = hdc.persona
    if not persona or not persona.numero_id:
        raise IdentidadNoCoincideError("El reporte HDC no incluye una identificación de persona para validar.")
    doc = normalizar_identificacion(solicitud.numero_id)
    tipo = normalizar_identificacion(solicitud.tipo_id.value)
    if doc != normalizar_identificacion(persona.numero_id):
        raise IdentidadNoCoincideError(
            "El número de identificación de la solicitud no coincide con el del HDC. No se generó decisión."
        )
    if persona.tipo_id and tipo != normalizar_identificacion(persona.tipo_id):
        raise IdentidadNoCoincideError("El tipo de identificación de la solicitud no coincide con el del HDC.")
    if valor_ingreso and valor_ingreso.numero_id:
        if doc != normalizar_identificacion(valor_ingreso.numero_id):
            raise IdentidadNoCoincideError("El reporte de Valor Ingreso corresponde a otra identificación.")
        if valor_ingreso.tipo_id and tipo != normalizar_identificacion(valor_ingreso.tipo_id):
            raise IdentidadNoCoincideError("El tipo de identificación de Valor Ingreso no coincide con la solicitud.")


def advertencias_consistencia(
    solicitud: Solicitud,
    hdc: RespuestaHDC,
    valor_ingreso: RespuestaValorIngreso | None,
    fecha: date | None = None,
) -> list[str]:
    advertencias: list[str] = []
    edad = calcular_edad(solicitud.fecha_nacimiento, fecha or date.today())
    advertencias.append(f"Edad calculada de la solicitud: {edad} años. Se evalúa en la política R13.")
    persona = hdc.persona
    if persona and (persona.edad_min is not None or persona.edad_max is not None):
        minimo = persona.edad_min if persona.edad_min is not None else 0
        maximo = persona.edad_max if persona.edad_max is not None else 200
        if not minimo <= edad <= maximo:
            advertencias.append(
                f"La fecha de nacimiento indica {edad} años, pero HDC+ reporta el rango "
                f"{persona.edad_min}-{persona.edad_max}. Se usa la fecha de la solicitud "
                "solo como referencia; verifica el dato fuente."
            )
    if valor_ingreso is not None and not valor_ingreso.aportantes:
        advertencias.append(
            "Valor Ingreso no contiene aportantes; el ingreso final usa Quanto o los "
            "ingresos declarados según la PPT v4."
        )
    return advertencias
