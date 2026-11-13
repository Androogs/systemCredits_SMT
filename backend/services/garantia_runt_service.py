"""Cargue masivo de garantías mobiliarias al SGM (RUNT Pro).

Genera el Excel multi-hoja que operaciones sube a RUNT Pro con las
prendas de las solicitudes facturadas/desembolsadas. Cada garantía
incluida queda marcada (`garantia_runt_exportada_en` + lote): un
segundo clic no la repite — el SGM rechaza duplicados. Con
`incluir_exportadas` se regenera un archivo anterior (para consulta o
descarga, no para re-radicar).

La hoja "Advertencias" lista lo que revisar a mano antes de cargar
(prenda sin motor/chasis, sin valor, etc.); el conteo viaja también
en el header `X-Advertencias` de la respuesta.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.db_models.models import (
    AliadoFinanciero,
    ProductoVehiculo,
    SolicitudContactoVivienda,
    SolicitudCredito,
)
from backend.services.motor_exceptions import SolicitudNoEncontradaError


ENCABEZADOS_GARANTIAS = [
    "N° SOLICITUD",
    "TIPO ID DEUDOR",
    "ID DEUDOR",
    "NOMBRE DEUDOR",
    "TIPO ID ACREEDOR",
    "ID ACREEDOR",
    "NOMBRE ACREEDOR",
    "TIPO DE GARANTÍA",
    "BIEN",
    "MARCA",
    "REFERENCIA",
    "MODELO (AÑO)",
    "COLOR",
    "NÚMERO DE MOTOR",
    "NÚMERO DE CHASIS",
    "VIN",
    "PLACA",
    "VALOR DEL BIEN",
    "VALOR GARANTIZADO",
    "CIUDAD",
    "DEPARTAMENTO",
    "FECHA DE CONSTITUCIÓN",
    "CONCESIONARIO",
    "NIT CONCESIONARIO",
]

ENCABEZADOS_ADVERTENCIAS = ["N° SOLICITUD", "CLIENTE", "CÉDULA", "ADVERTENCIA"]

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _lote() -> str:
    return f"SGM-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"


def pendientes_garantias(
    db: Session, *, incluir_exportadas: bool
) -> list[SolicitudCredito]:
    """Solicitudes facturadas/desembolsadas candidatas al cargue RNGM.

    Las comparten el Excel de revisión y el archivo plano .txt.

    Las ventas de contado no generan prenda (no hay crédito que
    garantizar): quedan fuera del cargue aunque estén facturadas."""
    query = (
        db.query(SolicitudCredito)
        .filter(SolicitudCredito.estado.in_(("facturada", "desembolsada")))
        .filter(
            func.coalesce(func.lower(SolicitudCredito.linea_credito), "")
            != "contado"
        )
        .options(
            joinedload(SolicitudCredito.cliente),
            joinedload(SolicitudCredito.concesionario),
            # ciudad de la vivienda (municipio de la garantía)
            joinedload(SolicitudCredito.contacto_vivienda).joinedload(
                SolicitudContactoVivienda.ciudad
            ),
            selectinload(SolicitudCredito.ofertas),
        )
        .order_by(SolicitudCredito.num_solicitud)
    )
    if not incluir_exportadas:
        query = query.filter(
            SolicitudCredito.garantia_runt_exportada_en.is_(None)
        )
    return query.all()


def aliado_propio(db: Session) -> AliadoFinanciero | None:
    """Acreedor prendario que reporta el archivo (entidad propia)."""
    return (
        db.query(AliadoFinanciero)
        .filter(
            AliadoFinanciero.es_propio.is_(True),
            AliadoFinanciero.activo.is_(True),
        )
        .first()
    )


class GarantiaRuntService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _pendientes(
        self, *, incluir_exportadas: bool
    ) -> list[SolicitudCredito]:
        return pendientes_garantias(
            self.db, incluir_exportadas=incluir_exportadas
        )

    def generar(
        self, *, incluir_exportadas: bool, marcar: bool = True
    ) -> tuple[bytes, str, int, int]:
        """Devuelve (xlsx, nombre_archivo, n_garantias, n_advertencias).

        404 si no hay nada que exportar (o nada que regenerar). Con
        `marcar` (default) las garantías incluidas quedan exportadas:
        el caller hace commit. El Excel se usa hoy como hoja de
        revisión previa al .txt oficial — la ruta lo pide con
        `marcar=False` para no gastar las prendas."""
        solicitudes = self._pendientes(incluir_exportadas=incluir_exportadas)
        if not solicitudes:
            hay_exportadas = (
                self.db.query(SolicitudCredito)
                .filter(
                    SolicitudCredito.garantia_runt_exportada_en.isnot(None)
                )
                .count()
            )
            detalle = (
                "No hay garantías pendientes de exportación; marca "
                "'incluir ya exportadas' para regenerar un archivo anterior."
                if hay_exportadas
                else "No hay solicitudes facturadas o desembolsadas con "
                "garantía por exportar."
            )
            raise SolicitudNoEncontradaError(detalle)

        aliado = aliado_propio(self.db)
        lote = _lote()
        ahora = datetime.now(timezone.utc)

        wb = Workbook()
        hoja = wb.active
        hoja.title = "Garantias"
        hoja.append(ENCABEZADOS_GARANTIAS)
        hoja_adv = wb.create_sheet("Advertencias")
        hoja_adv.append(ENCABEZADOS_ADVERTENCIAS)
        for fila in hoja[1]:
            fila.font = Font(bold=True)
        for fila in hoja_adv[1]:
            fila.font = Font(bold=True)

        advertencias = 0
        for solicitud in solicitudes:
            fila_g, filas_adv = self._fila_garantia(solicitud, aliado)
            hoja.append(fila_g)
            for fila in filas_adv:
                hoja_adv.append(fila)
                advertencias += 1
            if marcar:
                solicitud.garantia_runt_exportada_en = ahora
                solicitud.garantia_runt_lote = lote
        self.db.flush()

        ancho = {"A": 12, "C": 16, "D": 32, "G": 28, "I": 14,
                 "J": 14, "K": 30, "N": 26, "O": 18, "P": 18, "Q": 22,
                 "W": 24}
        for col, w in ancho.items():
            hoja.column_dimensions[col].width = w
        for col, w in {"A": 12, "B": 32, "C": 16, "D": 80}.items():
            hoja_adv.column_dimensions[col].width = w

        buffer = BytesIO()
        wb.save(buffer)
        return (
            buffer.getvalue(),
            f"garantias_runt_{lote}.xlsx",
            len(solicitudes),
            advertencias,
        )

    def _fila_garantia(
        self, solicitud: SolicitudCredito, aliado: AliadoFinanciero | None
    ) -> tuple[list, list[list]]:
        cliente = solicitud.cliente
        vehiculo = (
            self.db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == solicitud.id_solicitud)
            .order_by(ProductoVehiculo.id_vehiculo.desc())
            .first()
        )
        oferta = next((o for o in solicitud.ofertas if o.seleccionada), None)
        vivienda = solicitud.contacto_vivienda
        ciudad = vivienda.ciudad if vivienda else None

        avisos: list[str] = []
        if vehiculo is None:
            avisos.append("Sin registro de vehículo: la factura no "
                          "aportó la identificación de la prenda.")
        else:
            if not vehiculo.numero_motor:
                avisos.append("Prenda sin número de motor.")
            if not (vehiculo.numero_chasis or vehiculo.vin):
                avisos.append("Prenda sin número de chasis/VIN.")
            if vehiculo.valor_moto_iva is None:
                avisos.append("Prenda sin valor del bien (valor moto + IVA).")
        if oferta is None or oferta.monto_aprobado is None:
            avisos.append("Sin oferta seleccionada: falta el valor "
                          "garantizado (monto aprobado).")
        if ciudad is None:
            avisos.append("Cliente sin ciudad de residencia: el SGM "
                          "pide el municipio de la garantía.")
        if vehiculo is not None and not vehiculo.modelo:
            avisos.append("Prenda sin año modelo.")

        es_motocarro = (
            "KING" in (vehiculo.referencia or "").upper()
            or "TUK TUK" in (vehiculo.referencia or "").upper()
            or "KARGUERO" in (vehiculo.referencia or "").upper()
        ) if vehiculo else False

        fila = [
            solicitud.num_solicitud,
            (cliente.tipo_documento if cliente else "CC") or "CC",
            cliente.num_cedula if cliente else "",
            cliente.nombre_completo if cliente else "",
            "NIT",
            aliado.nit if aliado else "",
            aliado.nombre if aliado else "",
            "PRENDA SIN TENENCIA",
            "MOTOCARRO" if es_motocarro else "MOTOCICLETA",
            vehiculo.marca if vehiculo else "",
            vehiculo.referencia if vehiculo else "",
            vehiculo.modelo if vehiculo else "",
            vehiculo.color if vehiculo else "",
            vehiculo.numero_motor if vehiculo else "",
            vehiculo.numero_chasis if vehiculo else "",
            vehiculo.vin if vehiculo else "",
            "",  # placa: la moto nueva aún no se matricula
            float(vehiculo.valor_moto_iva) if vehiculo and vehiculo.valor_moto_iva is not None else None,
            float(oferta.monto_aprobado) if oferta and oferta.monto_aprobado is not None else None,
            ciudad.nombre if ciudad else "",
            ciudad.departamento if ciudad else "",
            (
                solicitud.factura_cargada_en.date().isoformat()
                if solicitud.factura_cargada_en
                else solicitud.fecha_hora.date().isoformat()
            ),
            solicitud.concesionario.nombre if solicitud.concesionario else "",
            solicitud.concesionario.nit if solicitud.concesionario else "",
        ]
        filas_adv = [
            [
                solicitud.num_solicitud,
                cliente.nombre_completo if cliente else "",
                cliente.num_cedula if cliente else "",
                aviso,
            ]
            for aviso in avisos
        ]
        return fila, filas_adv
