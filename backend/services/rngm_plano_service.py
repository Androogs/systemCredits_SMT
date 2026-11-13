"""Archivo plano RNGM para el cargue masivo de prendas en RUNTPRO.

Implementa la estructura de la guía "Proceso ingreso, cargue a
RUNTPRO_GM Fase II" (Ministerio de Transporte) y del Excel "Ejemplo
construcción archivo plano RNGM": un .txt ASCII con campos separados
por ``|`` y registros por salto de línea.

Layout de un archivo de Registro de prenda (novedad R)::

    <total_registros>|<DDMMAAAA>          registro de control
    PRN|R|N|<nit_acreedor>                por cada prenda…
    GRV|<fecha_ini DD/MM/AAAA>|<fecha_fin>|<monto>|COP|<tipo_garantía>
    DEU|<tipo_id>|<num>|<p_nombre>|<s_nombre>|<p_apellido>|<s_apellido>|
        <M|F>|<país>|<dpto DANE>|<mpio DANE>|<dirección>|<correo>|
        <tel_fijo>|<celular>|<NUEVO|RECURRENTE>|<tipo_deudor>|
        <sector>|<insolvencia>|<tipo_adm_insolv>|<razón_insolv>
    VEH|<tipo_reg>|<placa o id única>|<VIN>

Nombre del archivo: ``<NIT>RGM<consecutivo 3d><AAAAMMDD>.txt`` — el
consecutivo reinicia cada fecha y sale de la tabla ``rngm_archivo_lote``
(que también audita cada generación).

Novedades M (modificación) y C (cancelación) existen en la guía pero
requieren el número de prenda registrada en el RNGM, que el flujo de
originación aún no captura: por ahora solo se generan archivos de
registro (R).

Cada prenda incluida queda marcada en ``garantia_runt_lote`` con el
nombre del archivo; lo que falte (VIN, género, DANE sin mapear, etc.)
sale en ``advertencias`` para revisión previa — el RUNTPRO rechaza la
fila si un campo obligatorio va vacío.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from backend.db_models.auditoria_models import ConsultaBuro
from backend.db_models.models import (
    CreditoFinanciacion,
    ProductoVehiculo,
    RngmArchivoLote,
    SolicitudCredito,
)
from backend.models.buro_models import PersonaBasica
from backend.services.garantia_runt_service import (
    aliado_propio,
    pendientes_garantias,
)
from backend.services.motor_exceptions import SolicitudNoEncontradaError

DIVIPOLA_PATH = Path(__file__).resolve().parent.parent / "data" / "divipola_dane.json"

# Valores fijos de la guía RUNTPRO GM Fase II.
NOVEDAD_REGISTRO = "R"   # Pre-registro (también M=modificación, C=cancelación)
TIPO_ID_NIT = "N"        # tipo de identificación del acreedor
MONEDA_COP = "COP"
TIPO_GARANTIA_MOBILIARIA = "1"
PAIS_COLOMBIA = "CO"
# Sector económico del catálogo RUNTPRO: todos los ejemplos de la guía
# usan 19 para deudores persona natural.
SECTOR_ECONOMICO_DEFAULT = "19"
# Tipo de registro vehicular usado en los ejemplos de la guía.
VEH_TIPO_REGISTRO = "RNA"
TIPO_DEUDOR = "Deudor"

MIME_TXT = "text/plain; charset=utf-8"

# Documento del deudor → código RUNTPRO (D, C, E, P, U, T, N).
# La app guarda los códigos HDC ("1"…"9") y el log histórico trajo
# etiquetas largas ("Cedula De Ciudadania").
_TIPO_DOC_RUNT = {
    "1": "C", "C": "C", "CC": "C",
    "CEDULA DE CIUDADANIA": "C", "CEDULA CIUDADANIA": "C",
    "2": "N", "N": "N", "NIT": "N",
    "4": "E", "E": "E", "CE": "E", "CEDULA DE EXTRANJERIA": "E",
    "5": "P", "P": "P", "PAS": "P", "PASAPORTE": "P",
    "7": "T", "T": "T", "TI": "T", "TARJETA DE IDENTIDAD": "T",
    "D": "D", "CARNET DIPLOMATICO": "D",
    "U": "U", "RC": "U", "REGISTRO CIVIL": "U",
}
# Tipos de la app sin equivalente en el layout persona natural del
# RNGM: PJE ("3"), PPT ("6"), DNI ("8"), PEP ("9").
_TIPOS_JURIDICOS = {"2", "N", "NIT", "3", "PJE"}

_TILDES = str.maketrans(
    "ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun"
)


def _ascii(valor: object) -> str:
    """Campo del plano: mayúsculas, sin tildes ni ``|`` ni saltos."""
    s = str(valor if valor is not None else "").translate(_TILDES)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.replace("|", " ").replace("\r", " ").replace("\n", " ")
    return " ".join(s.upper().split())


def _fecha_grv(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def _nit_sin_dv(nit: str | None) -> str:
    """NIT sin dígito de verificación ni separadores ('814005081-3' → '814005081')."""
    base = (nit or "").split("-")[0].split(" ")[0]
    return re.sub(r"\D", "", base)


def _hoy_operacion() -> date:
    """Fecha de corte del archivo en la zona del RUNT (Colombia)."""
    try:
        return datetime.now(ZoneInfo("America/Bogota")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _nombre_archivo(nit: str, consecutivo: int, fecha: date) -> str:
    return f"{nit}RGM{consecutivo:03d}{fecha:%Y%m%d}.txt"


@lru_cache(maxsize=1)
def _divipola() -> dict:
    """Catálogo DANE/DIVIPOLA oficial (datos.gov.co gdxc-w37w)."""
    try:
        return json.loads(DIVIPOLA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"departamentos": {}, "municipios": {}, "municipios_unicos": {}}


def _norm_divipola(nombre: str | None) -> str:
    s = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    return " ".join(s.upper().split())


def _dane_ciudad(nombre: str | None, departamento: str | None) -> tuple[str, str]:
    """(cod_dpto 2d, cod_mpio 5d) de la ciudad; ("", "") si no mapea."""
    cat = _divipola()
    nom, dep = _norm_divipola(nombre), _norm_divipola(departamento)
    cod_mpio = cat["municipios"].get(f"{nom}|{dep}") or cat["municipios_unicos"].get(nom, "")
    if not cod_mpio:
        return "", ""
    return cod_mpio[:2], cod_mpio


def _tipo_doc_runt(tipo_documento: str | None) -> str:
    clave = _ascii(tipo_documento)
    return _TIPO_DOC_RUNT.get(clave, "")


def _es_doc_juridico(tipo_documento: str | None) -> bool:
    return _ascii(tipo_documento) in _TIPOS_JURIDICOS


def _genero(codigo: str | None) -> str:
    letra = _ascii(codigo)[:1]
    return letra if letra in ("M", "F") else ""


def _telefonos(raw: str | None) -> tuple[str, str]:
    """(fijo, celular). En la app solo se captura un número: móvil
    colombiano = 10 dígitos empezando en 3 (o '57' + 10); fijo = 7
    dígitos o 10 empezando en 60 (formato nacional con indicativo)."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 12 and d.startswith("57"):
        d = d[2:]
    if len(d) == 7 or (len(d) == 10 and d.startswith("60")):
        return d, ""
    return "", d if len(d) >= 10 else ""


def _partir_nombre(
    nombre_completo: str | None,
    primer_apellido: str | None,
    origen: str | None,
) -> tuple[str, str, str, str]:
    """(p_nombre, s_nombre, p_apellido, s_apellido).

    - Si el buró trajo el primer apellido (`flujo` lo pide en el
      formulario), su posición dentro del nombre completo fija el orden.
    - El log histórico radicó 'APELLIDOS NOMBRES' (su `primer_apellido`
      quedó con el último token — no es confiable).
    - Resto: convención 'NOMBRES APELLIDOS' (los 2 últimos tokens son
      los apellidos).
    """
    tokens = _ascii(nombre_completo).split()
    if not tokens:
        return "", "", "", ""
    if len(tokens) == 1:
        return tokens[0], "", "", ""
    pa = _ascii(primer_apellido)
    i = tokens.index(pa) if pa and pa in tokens and origen != "cargue_historico" else -1
    if i > 0:  # NOMBRES… APELLIDOS
        nombres, apellidos = tokens[:i], tokens[i:]
    elif i == 0:  # APELLIDOS NOMBRES
        apellidos, nombres = tokens[:2], tokens[2:]
    elif origen == "cargue_historico":
        apellidos, nombres = tokens[:2], tokens[2:]
    elif len(tokens) == 2:
        return tokens[0], "", tokens[1], ""
    else:
        nombres, apellidos = tokens[:-2], tokens[-2:]
    p_nom = nombres[0] if nombres else ""
    s_nom = " ".join(nombres[1:])
    p_ape = apellidos[0] if apellidos else ""
    s_ape = " ".join(apellidos[1:])
    return p_nom, s_nom, p_ape, s_ape


def _nombres_buro(persona: PersonaBasica | None) -> tuple[str, str, str, str] | None:
    """El buró reporta nombres/apellidos ya separados — la fuente más
    confiable cuando existe."""
    if persona is None or not (persona.nombres or persona.primer_apellido):
        return None
    nombres = _ascii(persona.nombres).split()
    return (
        nombres[0] if nombres else "",
        " ".join(nombres[1:]),
        _ascii(persona.primer_apellido),
        _ascii(persona.segundo_apellido),
    )


class ArchivoPlanoRngmService:
    """Genera el .txt de registro de prendas y marca las garantías."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Generación
    # ------------------------------------------------------------------
    def generar(
        self, *, incluir_exportadas: bool, generado_por: str | None = None
    ) -> tuple[bytes, str, int, list[list]]:
        """Devuelve (txt, nombre_archivo, n_garantias, advertencias).

        Las advertencias son filas [n° solicitud, cliente, cédula,
        mensaje] iguales a las de la hoja "Advertencias" del Excel.
        Marca cada garantía con el nombre del archivo: el caller hace
        commit. 404 si no hay prendas que exportar."""
        solicitudes = pendientes_garantias(
            self.db, incluir_exportadas=incluir_exportadas
        )
        if not solicitudes:
            hay_exportadas = (
                self.db.query(SolicitudCredito)
                .filter(SolicitudCredito.garantia_runt_exportada_en.isnot(None))
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
        nit = _nit_sin_dv(aliado.nit) if aliado else ""

        lineas: list[str] = []
        advertencias: list[list] = []
        for solicitud in solicitudes:
            avisos = []
            if not nit:
                avisos.append(
                    "Aliado propio sin NIT: el acreedor del PRN va vacío."
                )
            lineas.extend(self._registros_prenda(solicitud, nit, avisos))
            advertencias.extend(
                [
                    solicitud.num_solicitud,
                    _ascii(solicitud.cliente.nombre_completo if solicitud.cliente else ""),
                    _ascii(solicitud.cliente.num_cedula if solicitud.cliente else ""),
                    aviso,
                ]
                for aviso in avisos
            )

        hoy = _hoy_operacion()
        control = f"{len(lineas)}|{hoy:%d%m%Y}"
        cuerpo = "\n".join([control, *lineas]) + "\n"

        self._asegurar_tabla_lote()
        _consecutivo, nombre, _lote = self._reservar_lote(
            nit=nit,
            fecha=hoy,
            n_garantias=len(solicitudes),
            n_registros=len(lineas),
            n_advertencias=len(advertencias),
            generado_por=generado_por,
        )

        ahora = datetime.now(timezone.utc)
        for solicitud in solicitudes:
            solicitud.garantia_runt_exportada_en = ahora
            solicitud.garantia_runt_lote = nombre
        self.db.flush()

        return cuerpo.encode("ascii"), nombre, len(solicitudes), advertencias

    def advertencias_pendientes(
        self, *, incluir_exportadas: bool
    ) -> tuple[int, list[list]]:
        """Revisión previa sin marcar: (n_pendientes, advertencias)."""
        solicitudes = pendientes_garantias(
            self.db, incluir_exportadas=incluir_exportadas
        )
        aliado = aliado_propio(self.db)
        nit = _nit_sin_dv(aliado.nit) if aliado else ""
        advertencias: list[list] = []
        for solicitud in solicitudes:
            avisos = []
            if not nit:
                avisos.append(
                    "Aliado propio sin NIT: el acreedor del PRN va vacío."
                )
            self._registros_prenda(solicitud, nit, avisos)
            advertencias.extend(
                [
                    solicitud.num_solicitud,
                    _ascii(solicitud.cliente.nombre_completo if solicitud.cliente else ""),
                    _ascii(solicitud.cliente.num_cedula if solicitud.cliente else ""),
                    aviso,
                ]
                for aviso in avisos
            )
        return len(solicitudes), advertencias

    # ------------------------------------------------------------------
    # Registros de una prenda
    # ------------------------------------------------------------------
    def _registros_prenda(
        self, solicitud: SolicitudCredito, nit: str, avisos: list[str]
    ) -> list[str]:
        cliente = solicitud.cliente
        vehiculo = (
            self.db.query(ProductoVehiculo)
            .filter(ProductoVehiculo.id_solicitud == solicitud.id_solicitud)
            .order_by(ProductoVehiculo.id_vehiculo.desc())
            .first()
        )
        credito = (
            self.db.query(CreditoFinanciacion)
            .filter(CreditoFinanciacion.id_solicitud == solicitud.id_solicitud)
            .order_by(
                CreditoFinanciacion.ganadora.desc(),
                CreditoFinanciacion.id_credito.desc(),
            )
            .first()
        )
        oferta = next((o for o in solicitud.ofertas if o.seleccionada), None)
        persona = self._persona_buro(solicitud)

        return [
            self._registro_prn(nit),
            self._registro_grv(solicitud, credito, oferta, avisos),
            self._registro_deu(solicitud, cliente, persona, avisos),
            self._registro_veh(vehiculo, avisos),
        ]

    @staticmethod
    def _registro_prn(nit: str) -> str:
        # PRENDA: novedad R (pre-registro), acreedor con NIT.
        return "|".join(["PRN", NOVEDAD_REGISTRO, TIPO_ID_NIT, _ascii(nit)])

    @staticmethod
    def _registro_grv(solicitud, credito, oferta, avisos: list[str]) -> str:
        # Fecha de constitución: la del crédito si ya existe; si no, la
        # carga de la factura (prenda nace al facturar el vehículo).
        fecha_ini = (
            (credito.fecha_inicio if credito else None)
            or (solicitud.factura_cargada_en.date() if solicitud.factura_cargada_en else None)
            or (solicitud.fecha_hora.date() if solicitud.fecha_hora else None)
        )
        fecha_fin = credito.fecha_fin if credito else None
        plazo = (
            (credito.plazo if credito else None)
            or (oferta.plazo_ofrecido if oferta else None)
            or solicitud.plazo_deseado_meses
        )
        if fecha_fin is None and fecha_ini and plazo:
            fecha_fin = fecha_ini + relativedelta(months=int(plazo))
        if fecha_fin is None:
            avisos.append("Prenda sin fecha de finalización (crédito sin "
                          "fecha_fin ni plazo para estimarla).")
        monto = (
            (oferta.monto_aprobado if oferta else None)
            or (credito.valor_financiacion if credito else None)
        )
        if monto is None:
            avisos.append("Prenda sin monto máximo: no hay oferta "
                          "seleccionada ni financiación.")
            monto_txt = ""
        else:
            monto_txt = str(int(round(float(monto))))
        return "|".join([
            "GRV",
            _fecha_grv(fecha_ini),
            _fecha_grv(fecha_fin),
            monto_txt,
            MONEDA_COP,
            TIPO_GARANTIA_MOBILIARIA,
        ])

    def _registro_deu(self, solicitud, cliente, persona, avisos: list[str]) -> str:
        tipo_doc = _tipo_doc_runt(cliente.tipo_documento if cliente else None)
        if not tipo_doc:
            avisos.append(
                f"Tipo de documento '{cliente.tipo_documento}' sin código "
                "RUNT en el layout persona natural."
            )
        elif _es_doc_juridico(cliente.tipo_documento):
            avisos.append("Deudor persona jurídica: el layout del archivo "
                          "plano es de persona natural; revisar a mano.")
        num_doc = _ascii(cliente.num_cedula if cliente else "")

        partes = _nombres_buro(persona) or _partir_nombre(
            cliente.nombre_completo if cliente else "",
            cliente.primer_apellido if cliente else "",
            solicitud.origen,
        )
        p_nom, s_nom, p_ape, s_ape = partes
        if not p_ape:
            avisos.append("Deudor sin primer apellido identificable.")

        genero = _genero(persona.genero if persona else None)
        if not genero:
            avisos.append("Deudor sin género: el buró no lo reportó y la "
                          "solicitud no lo captura; RUNTPRO lo exige.")

        vivienda = solicitud.contacto_vivienda
        ciudad = vivienda.ciudad if vivienda else None
        cod_dpto, cod_mpio = _dane_ciudad(
            ciudad.nombre if ciudad else None,
            ciudad.departamento if ciudad else None,
        )
        if ciudad is None:
            avisos.append("Cliente sin ciudad de residencia: el RNGM "
                          "pide depto y municipio DANE.")
        elif not cod_mpio:
            avisos.append(f"Ciudad '{ciudad.nombre}' sin código DANE en "
                          "el catálogo DIVIPOLA del servicio.")

        fijo, celular = _telefonos(vivienda.telefono if vivienda else None)
        if not celular and not fijo:
            avisos.append("Deudor sin teléfono de contacto.")

        return "|".join([
            "DEU",
            tipo_doc,
            num_doc,
            p_nom,
            s_nom,
            p_ape,
            s_ape,
            genero,
            PAIS_COLOMBIA,
            cod_dpto,
            cod_mpio,
            _ascii(vivienda.direccion if vivienda else ""),
            _ascii(vivienda.correo if vivienda else ""),
            fijo,
            celular,
            self._tipo_cliente(solicitud),
            TIPO_DEUDOR,
            SECTOR_ECONOMICO_DEFAULT,
            "N",   # sin proceso de insolvencia
            "",    # tipo de administrador de insolvencia
            "",    # razón social / nombre de insolvencia
        ])

    def _tipo_cliente(self, solicitud: SolicitudCredito) -> str:
        """NUEVO si el cliente no tiene otros créditos en curso o
        cerrados en la app; RECURRENTE en caso contrario."""
        otros = (
            self.db.query(SolicitudCredito)
            .filter(
                SolicitudCredito.id_cliente == solicitud.id_cliente,
                SolicitudCredito.id_solicitud != solicitud.id_solicitud,
                SolicitudCredito.estado.in_(("aprobada", "facturada", "desembolsada")),
            )
            .count()
        )
        return "RECURRENTE" if otros else "NUEVO"

    @staticmethod
    def _registro_veh(vehiculo, avisos: list[str]) -> str:
        # Moto nueva: aún no hay placa — la identificación única es el
        # VIN, chasis o motor que aportó la factura del concesionario.
        id_unica = ""
        if vehiculo:
            id_unica = _ascii(
                vehiculo.vin or vehiculo.numero_chasis or vehiculo.numero_motor or ""
            )
        if not id_unica:
            avisos.append("Vehículo sin identificación única: la factura "
                          "no aportó VIN, chasis ni motor.")
        return "|".join([
            "VEH",
            VEH_TIPO_REGISTRO,
            id_unica,
            _ascii(vehiculo.vin if vehiculo else ""),
        ])

    # ------------------------------------------------------------------
    # Datos auxiliares
    # ------------------------------------------------------------------
    def _persona_buro(self, solicitud: SolicitudCredito) -> PersonaBasica | None:
        """Nombres, apellidos y género del último reporte HDC de la
        solicitud (reusa la consulta paga ya guardada en consulta_buro)."""
        consulta = (
            self.db.query(ConsultaBuro)
            .filter(ConsultaBuro.id_solicitud == solicitud.id_solicitud)
            .order_by(ConsultaBuro.fecha_consulta.desc())
            .first()
        )
        if consulta is None:
            return None
        try:
            hdc, _ = consulta.a_reportes()
        except (ValueError, TypeError):
            return None
        return hdc.persona if hdc else None

    def _asegurar_tabla_lote(self) -> None:
        """La tabla la crea la migración 0035 en Postgres; en la SQLite
        de desarrollo (que no corre alembic) la crea aquí on-demand."""
        RngmArchivoLote.__table__.create(bind=self.db.get_bind(), checkfirst=True)

    def _reservar_lote(
        self,
        *,
        nit: str,
        fecha: date,
        n_garantias: int,
        n_registros: int,
        n_advertencias: int,
        generado_por: str | None,
    ) -> tuple[int, str, RngmArchivoLote]:
        """Inserta el lote con el siguiente consecutivo del día.

        El UNIQUE(fecha_corte, consecutivo) resuelve en savepoint el
        choque de dos generaciones concurrentes: reintenta con el
        siguiente número."""
        for _ in range(3):
            ultimo = (
                self.db.query(func.max(RngmArchivoLote.consecutivo))
                .filter(RngmArchivoLote.fecha_corte == fecha)
                .scalar()
            )
            consecutivo = (ultimo or 0) + 1
            if consecutivo > 999:
                raise SolicitudNoEncontradaError(
                    "Se agotó el consecutivo diario de archivos RNGM (999)."
                )
            nombre = _nombre_archivo(nit, consecutivo, fecha)
            lote = RngmArchivoLote(
                fecha_corte=fecha,
                consecutivo=consecutivo,
                nombre_archivo=nombre,
                tipo_novedad=NOVEDAD_REGISTRO,
                n_garantias=n_garantias,
                n_registros=n_registros,
                n_advertencias=n_advertencias,
                generado_por=generado_por,
            )
            try:
                with self.db.begin_nested():
                    self.db.add(lote)
                    self.db.flush()
                return consecutivo, nombre, lote
            except IntegrityError:
                # El savepoint deshizo el INSERT pero el objeto sigue
                # pending: sacarlo para que el próximo flush no lo repita.
                self.db.expunge(lote)
                continue
        raise SolicitudNoEncontradaError(
            "No fue posible reservar el consecutivo del archivo RNGM."
        )
