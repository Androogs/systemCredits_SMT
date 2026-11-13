"""Formalización del crédito y confirmación de desembolso.

Cadena del esquema: producto_vehiculo -> credito_financiacion -> desembolso.

En Postgres el trigger `validar_cuentas_desembolso` exige que la cuenta
emisora sea del aliado propio activo y la receptora una cuenta de
ahorros activa del cliente; el servicio replica esas mismas
validaciones para que el contrato sea idéntico en cualquier motor
(p. ej. SQLite en pruebas).
"""

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from backend.config import get_settings

from backend.db_models.models import (
    AliadoFinanciero,
    Banco,
    CreditoFinanciacion,
    CuentaBancaria,
    Desembolso,
    OfertaCredito,
    ProductoVehiculo,
    SolicitudCredito,
)
from backend.models.solicitud_models import DesembolsoResponse, RegistrarDesembolsoRequest
from backend.services.finanzas import cuota_anualidad
from backend.services.motor_exceptions import SolicitudNoEncontradaError, ValidacionError


# Gastos administrativos del crédito: cargo fijo de originación que
# entra en el saldo a financiar (la UI lo suma al monto seleccionado y
# aquí queda descompuesto para el pagaré y la hoja de formalización).
GASTOS_ADMINISTRATIVOS = Decimal("200000")


def _fecha_fin(desde: date, plazo_meses: int) -> date:
    """Suma `plazo_meses` meses conservando el día cuando sea posible."""
    meses = desde.year * 12 + desde.month - 1 + plazo_meses
    anio, mes = divmod(meses, 12)
    dia = min(desde.day, calendar.monthrange(anio, mes + 1)[1])
    return date(anio, mes + 1, dia)


class DesembolsoService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def registrar(
        self,
        id_solicitud: uuid.UUID,
        req: RegistrarDesembolsoRequest,
        *,
        estado_desembolso: str = "confirmado",
    ) -> DesembolsoResponse:
        """Formaliza el crédito y registra el desembolso.

        `estado_desembolso="pendiente"` deja el giro en tránsito (el
        webhook del emisor anuncia que la transferencia salió pero aún
        no confirma): la solicitud no pasa a 'desembolsada' hasta que
        llegue la confirmación.
        """
        solicitud = (
            self.db.query(SolicitudCredito)
            .filter(SolicitudCredito.id_solicitud == id_solicitud)
            .one_or_none()
        )
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")

        credito = (
            self.db.query(CreditoFinanciacion)
            .filter(CreditoFinanciacion.id_solicitud == id_solicitud)
            .one_or_none()
        )

        if credito is not None:
            desembolso = (
                self.db.query(Desembolso)
                .filter(Desembolso.id_credito == credito.id_credito)
                .one_or_none()
            )
            if desembolso is not None:
                # Idempotente: un crédito ya formalizado devuelve su
                # desembolso; si quedó pendiente, se confirma aquí.
                if desembolso.estado == "pendiente" and estado_desembolso == "confirmado":
                    desembolso.estado = "confirmado"
                    desembolso.fecha_desembolso = datetime.now(timezone.utc)
                    if req.referencia_pago:
                        desembolso.referencia_pago = req.referencia_pago
                    self._marcar_desembolsada(solicitud)
                    self.db.flush()
                return self._response(desembolso)
            emisor = self._cuenta_emisora()
            receptor = self._cuenta_receptora(solicitud, req)
            desembolso = self._crear_desembolso(
                credito, emisor, receptor, req.referencia_pago, estado_desembolso
            )
            if estado_desembolso == "confirmado":
                self._marcar_desembolsada(solicitud)
            self.db.flush()
            return self._response(desembolso)

        # Formalización completa: la solicitud debe estar aprobada (o
        # facturada — el ciclo comercial sigue siendo "por girar") con
        # una oferta seleccionada por el cliente.
        if solicitud.estado not in ("aprobada", "facturada") or solicitud.decision != "aprobado":
            raise ValidacionError(
                f"La solicitud {id_solicitud} no es elegible para desembolso "
                f"(estado={solicitud.estado}, decisión={solicitud.decision})."
            )
        oferta = (
            self.db.query(OfertaCredito)
            .filter(OfertaCredito.id_solicitud == id_solicitud, OfertaCredito.seleccionada.is_(True))
            .one_or_none()
        )
        if oferta is None or oferta.monto_aprobado is None:
            raise ValidacionError(
                "La solicitud no tiene una oferta seleccionada; el cliente debe "
                "aceptar una oferta antes de confirmar el desembolso."
            )

        emisor = self._cuenta_emisora()
        receptor = self._cuenta_receptora(solicitud, req)
        vehiculo = self._crear_vehiculo(solicitud, req)
        credito = self._crear_credito(solicitud, oferta, vehiculo)
        desembolso = self._crear_desembolso(
            credito, emisor, receptor, req.referencia_pago, estado_desembolso
        )
        if estado_desembolso == "confirmado":
            self._marcar_desembolsada(solicitud)
        self.db.flush()
        return self._response(desembolso)

    def desembolsar_masivo(
        self, id_solicitudes: list[uuid.UUID]
    ) -> list[dict]:
        """Marca en bloque solicitudes 'facturada' como 'desembolsada'.

        Lo usa la bandeja de operaciones tras radicar el cargue de
        garantías en RUNT Pro. El registro del giro (cuenta del
        concesionario + referencia) NO se pide aquí: llega después por
        el webhook de tesorería o desde el detalle, y como aquí ya
        queda formalizado el crédito (`credito_financiacion`), ese
        registro solo tiene que crear la fila `desembolso`.

        Cada solicitud corre en su propio SAVEPOINT: una factura sin
        prenda o sin oferta falla sin revertir el resto del lote.
        """
        resultados: list[dict] = []
        for id_solicitud in id_solicitudes:
            try:
                with self.db.begin_nested():
                    self._desembolsar_una(id_solicitud)
                resultados.append({"id_solicitud": id_solicitud, "ok": True})
            except Exception as exc:  # noqa: BLE001 — el ítem falla, no el lote
                resultados.append(
                    {
                        "id_solicitud": id_solicitud,
                        "ok": False,
                        "error": getattr(exc, "detail", str(exc)),
                    }
                )
        return resultados

    def _desembolsar_una(self, id_solicitud: uuid.UUID) -> None:
        """Una facturada → desembolsada: exige oferta seleccionada y la
        prenda identificada (motor/chasis/VIN) — lo que se registró en
        el SGM. Garantiza la fila `credito_financiacion` para que el
        giro posterior solo inserte `desembolso`."""
        solicitud = (
            self.db.query(SolicitudCredito)
            .filter(SolicitudCredito.id_solicitud == id_solicitud)
            .one_or_none()
        )
        if solicitud is None:
            raise SolicitudNoEncontradaError(f"No existe la solicitud {id_solicitud}")
        if solicitud.estado != "facturada":
            raise ValidacionError(
                f"Solo se desembolsan solicitudes facturadas "
                f"(estado actual: {solicitud.estado})."
            )
        oferta = (
            self.db.query(OfertaCredito)
            .filter(
                OfertaCredito.id_solicitud == id_solicitud,
                OfertaCredito.seleccionada.is_(True),
            )
            .one_or_none()
        )
        if oferta is None or oferta.monto_aprobado is None:
            raise ValidacionError(
                "La solicitud no tiene una oferta seleccionada; no hay "
                "monto aprobado que desembolsar."
            )
        vehiculo = (
            self.db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == id_solicitud)
            .order_by(ProductoVehiculo.id_vehiculo.desc())
            .first()
        )
        if vehiculo is None or not (
            vehiculo.numero_motor or vehiculo.numero_chasis or vehiculo.vin
        ):
            raise ValidacionError(
                "La solicitud no tiene la prenda identificada "
                "(motor/chasis/VIN): la factura no la aportó y no hay "
                "garantía que registrar en el SGM."
            )
        credito = (
            self.db.query(CreditoFinanciacion)
            .filter(CreditoFinanciacion.id_solicitud == id_solicitud)
            .one_or_none()
        )
        if credito is None:
            self._crear_credito(solicitud, oferta, vehiculo)
        self._marcar_desembolsada(solicitud)
        self.db.flush()

    def _cuenta_emisora(self) -> CuentaBancaria:
        cuenta = (
            self.db.query(CuentaBancaria)
            .join(AliadoFinanciero, CuentaBancaria.id_aliado == AliadoFinanciero.id_aliado)
            .filter(
                AliadoFinanciero.es_propio.is_(True),
                AliadoFinanciero.activo.is_(True),
                CuentaBancaria.activa.is_(True),
            )
            .first()
        )
        if cuenta is None:
            raise ValidacionError(
                "No hay una cuenta bancaria activa del aliado financiero propio "
                "para emitir el desembolso."
            )
        return cuenta

    def _cuenta_receptora(self, solicitud: SolicitudCredito, req: RegistrarDesembolsoRequest) -> CuentaBancaria:
        banco = (
            self.db.query(Banco)
            .filter(Banco.codigo_ach == req.codigo_ach_banco)
            .one_or_none()
        )
        if banco is None or not banco.activo:
            raise ValidacionError(f"Banco no registrado o inactivo (código ACH {req.codigo_ach_banco}).")

        id_cliente = solicitud.id_cliente
        existente = (
            self.db.query(CuentaBancaria)
            .filter(
                CuentaBancaria.id_banco == banco.id_banco,
                CuentaBancaria.numero == req.numero_cuenta_cliente,
            )
            .one_or_none()
        )
        if existente is not None:
            if existente.id_cliente != id_cliente:
                raise ValidacionError("La cuenta receptora no pertenece al cliente de la solicitud.")
            if not existente.activa or existente.tipo != "ahorros":
                raise ValidacionError("La cuenta receptora no está activa o no es de ahorros.")
            return existente

        cliente = solicitud.cliente
        cuenta = CuentaBancaria(
            id_banco=banco.id_banco,
            tipo="ahorros",
            numero=req.numero_cuenta_cliente,
            titular=req.titular_cuenta or cliente.nombre_completo,
            nit_titular=cliente.num_cedula,
            id_cliente=id_cliente,
        )
        self.db.add(cuenta)
        self.db.flush()
        return cuenta

    def _crear_vehiculo(self, solicitud: SolicitudCredito, req: RegistrarDesembolsoRequest) -> ProductoVehiculo:
        datos = req.vehiculo
        # Si la formalización ya registró el vehículo (selección de
        # oferta), se reutiliza y solo se actualiza con lo que venga aquí.
        existente = (
            self.db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == solicitud.id_solicitud)
            .order_by(ProductoVehiculo.id_vehiculo.desc())
            .first()
        )
        if existente is not None:
            if datos is not None:
                for campo in ("producto_a_financiar", "marca", "referencia", "modelo", "color", "valor_moto_iva"):
                    valor = getattr(datos, campo, None)
                    if valor is not None:
                        setattr(existente, campo, valor)
            return existente
        vehiculo = ProductoVehiculo(
            id_solicitud=solicitud.id_solicitud,
            producto_a_financiar=(datos.producto_a_financiar if datos else solicitud.destino_credito or "Motocicleta"),
            marca=datos.marca if datos else None,
            referencia=datos.referencia if datos else None,
            modelo=datos.modelo if datos else None,
            color=datos.color if datos else None,
            valor_moto_iva=datos.valor_moto_iva if datos else None,
        )
        self.db.add(vehiculo)
        self.db.flush()
        return vehiculo

    def _crear_credito(
        self,
        solicitud: SolicitudCredito,
        oferta: OfertaCredito,
        vehiculo: ProductoVehiculo,
    ) -> CreditoFinanciacion:
        monto = oferta.monto_aprobado
        # oferta.cuota_mensual ya es la cuota TOTAL (anualidad + seguro
        # de vida) que el cliente vio al aceptar la oferta; aquí se
        # desglosa para persistir cada componente.
        cuota_total = oferta.cuota_mensual or 0
        plazo = oferta.plazo_ofrecido or solicitud.plazo_deseado_meses or 0
        if plazo <= 0:
            raise ValidacionError("La oferta seleccionada no define un plazo válido.")
        cuota_fin = Decimal(
            str(cuota_anualidad(Decimal(str(monto or 0)), Decimal(str(oferta.tasa_ofrecida or 0)), plazo))
        ).quantize(Decimal("0.01"))
        cuota_vida = max(Decimal(str(cuota_total)) - cuota_fin, Decimal(0))
        valor_vida = cuota_vida * plazo
        hoy = date.today()
        aliado = (
            self.db.query(AliadoFinanciero)
            .filter(AliadoFinanciero.es_propio.is_(True), AliadoFinanciero.activo.is_(True))
            .first()
        )
        credito = CreditoFinanciacion(
            id_solicitud=solicitud.id_solicitud,
            id_vehiculo=vehiculo.id_vehiculo,
            id_oferta=oferta.id_oferta,
            id_aliado_financiero=aliado.id_aliado if aliado else None,
            ganadora=True,
            aval_pct=vehiculo.aval_pct,
            tasa=oferta.tasa_ofrecida,
            plazo=plazo,
            valor_financiar=monto,
            gastos_administrativos=GASTOS_ADMINISTRATIVOS,
            saldo_financiar=monto,
            valor_financiacion=monto,
            seguro=valor_vida,
            valor_seguro_vida=valor_vida,
            total_a_pagar=cuota_total * plazo,
            cuota_financiacion=cuota_fin,
            cuota_seguro_vida=cuota_vida,
            cuota_total=cuota_total,
            moneda=solicitud.moneda or "COP",
            dia_pago=get_settings().documentos_dia_pago,
            fecha_inicio=hoy,
            fecha_fin=_fecha_fin(hoy, plazo),
        )
        self.db.add(credito)
        self.db.flush()
        return credito

    def _crear_desembolso(
        self,
        credito: CreditoFinanciacion,
        emisor: CuentaBancaria,
        receptor: CuentaBancaria,
        referencia_pago: str | None,
        estado: str = "confirmado",
    ) -> Desembolso:
        desembolso = Desembolso(
            id_credito=credito.id_credito,
            id_cuenta_emisor=emisor.id_cuenta,
            emisor=emisor.titular,
            id_cuenta_receptor=receptor.id_cuenta,
            nit_receptor=receptor.nit_titular,
            receptor=receptor.titular,
            referencia_pago=referencia_pago,
            fecha_desembolso=datetime.now(timezone.utc) if estado == "confirmado" else None,
            capital=credito.valor_financiacion,
            cuota=credito.cuota_total,
            plazo=credito.plazo,
            tasa=credito.tasa,
            valor_seguro=credito.valor_seguro_vida,
            moneda=credito.moneda,
            estado=estado,
        )
        self.db.add(desembolso)
        self.db.flush()
        if not desembolso.num_desembolso:
            desembolso.num_desembolso = f"DES-{desembolso.id_desembolso:06d}"
        return desembolso

    @staticmethod
    def _marcar_desembolsada(solicitud: SolicitudCredito) -> None:
        solicitud.estado = "desembolsada"

    @staticmethod
    def _response(desembolso: Desembolso) -> DesembolsoResponse:
        return DesembolsoResponse(
            id_desembolso=desembolso.id_desembolso,
            num_desembolso=desembolso.num_desembolso,
            id_credito=desembolso.id_credito,
            estado=desembolso.estado,
            capital=desembolso.capital,
            cuota=desembolso.cuota,
            plazo=desembolso.plazo,
            tasa=desembolso.tasa,
            emisor=desembolso.emisor,
            receptor=desembolso.receptor,
            referencia_pago=desembolso.referencia_pago,
            fecha_desembolso=desembolso.fecha_desembolso,
        )
