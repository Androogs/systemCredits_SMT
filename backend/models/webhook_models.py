"""Contratos del webhook de confirmación asíncrona de desembolso.

El emisor (aliado/tesorería) notifica el resultado de la transferencia
una vez girada — o fallida — sin intervención del operador en el panel.
"""

import uuid

from pydantic import BaseModel, Field, model_validator


class WebhookDesembolsoRequest(BaseModel):
    """Evento de desembolso notificado por el emisor.

    La solicitud se identifica por `id_solicitud` (uuid interno) o por
    `num_solicitud` (el número público #143); uno de los dos es
    obligatorio. `estado='en_transito'` formaliza el crédito dejando el
    giro pendiente; `estado='confirmado'` lo confirma (idempotente);
    `estado='rechazado'` marca el desembolso pendiente como rechazado.
    """

    id_solicitud: uuid.UUID | None = None
    num_solicitud: int | None = Field(default=None, ge=1)
    estado: str = Field(pattern="^(confirmado|rechazado|en_transito)$")

    # Cuenta receptora del cliente (obligatoria cuando se crea el
    # desembolso: 'en_transito' o 'confirmado').
    codigo_ach_banco: str | None = Field(default=None, max_length=10)
    numero_cuenta_cliente: str | None = Field(default=None, max_length=40)
    titular_cuenta: str | None = Field(default=None, max_length=180)
    referencia_pago: str | None = Field(default=None, max_length=80)

    # Trazabilidad del evento en el emisor y motivo del rechazo.
    id_evento: str | None = Field(default=None, max_length=80)
    motivo: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _validar(self):
        if self.id_solicitud is None and self.num_solicitud is None:
            raise ValueError("Se requiere id_solicitud o num_solicitud.")
        if self.estado in ("confirmado", "en_transito") and (
            not self.codigo_ach_banco or not self.numero_cuenta_cliente
        ):
            raise ValueError(
                f"estado={self.estado} exige codigo_ach_banco y numero_cuenta_cliente."
            )
        return self
