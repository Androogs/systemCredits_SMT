"""Cargue masivo RNGM desde el Excel externo de registro de garantías.

La plantilla operativa ("<año> Sumoto <sede> - Registro Garantia.xlsx")
lista una garantía por fila; las de ``ESTADO DE PAGO = PENDIENTE`` son
las que faltan por radicar en RUNTPRO. Este servicio las convierte en
el archivo plano oficial de la guía RUNTPRO GM Fase II (control +
PRN/GRV/DEU/VEH por prenda), igual que ``ArchivoPlanoRngmService`` lo
hace con las solicitudes de la plataforma.

Lo usa el endpoint ``POST /cargas/garantias-runtpro/excel`` y el script
``scripts/cargue_runt_excel.py`` (cargues manuales por consola).

Particularidades de la plantilla (verificadas en el registro 2026):

- Las columnas 5-8 se digitan 'PRIMER/SEGUNDO APELLIDO | PRIMER/SEGUNDO
  NOMBRE' — orden inverso al encabezado ("LOPEZ PABON DUVAN ALBERTO"
  es Duvan Alberto Lopez Pabon).
- ``FECHA FIN GARANTIA`` puede venir anterior a la de inicio: se
  recalcula como inicio + plazo y sale en las advertencias.
- El tipo de documento no se digita: toda cédula va como 'C'.
"""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

import openpyxl
from dateutil.relativedelta import relativedelta
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from backend.services.garantia_runt_service import (
    ENCABEZADOS_ADVERTENCIAS,
    ENCABEZADOS_GARANTIAS,
    aliado_propio,
)
from backend.services.motor_exceptions import SolicitudNoEncontradaError
from backend.services.rngm_plano_service import (
    MONEDA_COP,
    NOVEDAD_REGISTRO,
    PAIS_COLOMBIA,
    SECTOR_ECONOMICO_DEFAULT,
    TIPO_DEUDOR,
    TIPO_GARANTIA_MOBILIARIA,
    TIPO_ID_NIT,
    VEH_TIPO_REGISTRO,
    ArchivoPlanoRngmService,
    _ascii,
    _dane_ciudad,
    _fecha_grv,
    _nit_sin_dv,
    _telefonos,
)

# Columnas de la hoja de registro (1-based), tal como se digitan.
C_ESTADO, C_CEDULA = 3, 4
C_APE1, C_APE2, C_NOM1, C_NOM2 = 5, 6, 7, 8
C_GENERO, C_DEPTO, C_MPIO = 9, 11, 12
C_DIR, C_CORREO, C_CEL, C_TIPO_CLI = 13, 14, 15, 16
C_PLACA, C_CHASIS, C_FAB, C_MODELO = 18, 19, 20, 21
C_SALDO, C_PLAZO, C_F_INI, C_F_FIN = 23, 24, 25, 26


def _cel(ws, fila: int, col: int):
    v = ws.cell(fila, col).value
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def _genero(valor) -> str:
    letra = _ascii(valor)[:1]
    return letra if letra in ("M", "F") else ""


def _fecha_fin(f_ini, plazo, f_fin_hoja):
    """Fin de la prenda: el de la hoja si es coherente; si no,
    inicio + plazo (la columna llega mal calculada en la plantilla)."""
    ini = f_ini.date() if isinstance(f_ini, datetime) else f_ini
    fin_h = f_fin_hoja.date() if isinstance(f_fin_hoja, datetime) else f_fin_hoja
    if isinstance(fin_h, date) and ini and fin_h >= ini:
        return fin_h, ""
    if ini and plazo:
        fin = ini + relativedelta(months=int(plazo))
        if fin_h and fin_h < ini:
            return fin, (
                "Fecha fin de la hoja anterior a la de inicio: se "
                "recalculó como inicio + plazo."
            )
        return fin, ""
    return fin_h, ""


def leer_prendas(ws, desde: int) -> tuple[list[dict], list[list]]:
    """Filas PENDIENTE de la hoja desde ``desde`` → (prendas, advertencias)."""
    prendas: list[dict] = []
    advertencias: list[list] = []
    for fila in range(desde, ws.max_row + 1):
        cedula = _cel(ws, fila, C_CEDULA)
        if cedula in (None, ""):
            continue
        if _ascii(_cel(ws, fila, C_ESTADO)) != "PENDIENTE":
            continue
        ape1, ape2 = _cel(ws, fila, C_APE1), _cel(ws, fila, C_APE2)
        nom1, nom2 = _cel(ws, fila, C_NOM1), _cel(ws, fila, C_NOM2)
        cliente = " ".join(str(x) for x in (nom1, nom2, ape1, ape2) if x)
        prenda = {
            "fila": fila,
            "cedula": str(cedula).strip(),
            "cliente": _ascii(cliente),
            "ape1": _ascii(ape1), "ape2": _ascii(ape2),
            "nom1": _ascii(nom1), "nom2": _ascii(nom2),
            "genero": _genero(_cel(ws, fila, C_GENERO)),
            "depto": _cel(ws, fila, C_DEPTO),
            "mpio": _cel(ws, fila, C_MPIO),
            "direccion": _cel(ws, fila, C_DIR),
            "correo": _cel(ws, fila, C_CORREO),
            "celular": _cel(ws, fila, C_CEL),
            "tipo_cliente": _ascii(_cel(ws, fila, C_TIPO_CLI)) or "NUEVO",
            "placa": _ascii(_cel(ws, fila, C_PLACA)),
            "chasis": _ascii(_cel(ws, fila, C_CHASIS)),
            "fabricante": _ascii(_cel(ws, fila, C_FAB)),
            "modelo": _cel(ws, fila, C_MODELO),
            "saldo": _cel(ws, fila, C_SALDO),
            "plazo": _cel(ws, fila, C_PLAZO),
            "f_ini": _cel(ws, fila, C_F_INI),
            "f_fin": _cel(ws, fila, C_F_FIN),
        }
        _validar(prenda, advertencias)
        prendas.append(prenda)
    return prendas, advertencias


def _validar(p: dict, advertencias: list[list]) -> None:
    def aviso(msg: str) -> None:
        advertencias.append([p["fila"], p["cliente"], p["cedula"], msg])

    if not p["ape1"]:
        aviso("Deudor sin primer apellido identificable.")
    if not p["genero"]:
        aviso("Deudor sin género: RUNTPRO lo exige (M/F).")
    if not p["chasis"]:
        aviso("Vehículo sin chasis/VIN: la garantía queda sin "
              "identificación única del bien.")
    if not p["placa"]:
        aviso("Vehículo sin placa ni identificación: revisar registro "
              "vehicular en RUNTPRO.")
    if not p["saldo"]:
        aviso("Prenda sin monto máximo (saldo deuda vacío).")
    if not p["f_ini"]:
        aviso("Prenda sin fecha de constitución.")
    p["f_fin_calc"], nota_fin = _fecha_fin(p["f_ini"], p["plazo"], p["f_fin"])
    if nota_fin:
        aviso(nota_fin)
    p["cod_dpto"], p["cod_mpio"] = _dane_ciudad(p["mpio"], p["depto"])
    if not p["cod_mpio"]:
        aviso(f"Municipio '{p['mpio']}' sin código DANE en el catálogo "
              "DIVIPOLA.")
    p["fijo"], p["cel"] = _telefonos(str(p["celular"] or ""))
    if not p["cel"] and not p["fijo"]:
        aviso("Deudor sin teléfono de contacto.")


def lineas_rngm(p: dict, nit: str) -> list[str]:
    """Los 4 registros de la prenda: PRN/GRV/DEU/VEH (guía GM Fase II)."""
    f_ini = p["f_ini"].date() if isinstance(p["f_ini"], datetime) else p["f_ini"]
    monto = str(int(round(float(p["saldo"])))) if p["saldo"] else ""
    return [
        "|".join(["PRN", NOVEDAD_REGISTRO, TIPO_ID_NIT, _ascii(nit)]),
        "|".join([
            "GRV",
            _fecha_grv(f_ini),
            _fecha_grv(p["f_fin_calc"]),
            monto,
            MONEDA_COP,
            TIPO_GARANTIA_MOBILIARIA,
        ]),
        "|".join([
            "DEU",
            "C",                       # cédula de ciudadanía
            _ascii(p["cedula"]),
            p["nom1"], p["nom2"], p["ape1"], p["ape2"],
            p["genero"],
            PAIS_COLOMBIA,
            p["cod_dpto"], p["cod_mpio"],
            _ascii(p["direccion"]),
            _ascii(p["correo"]),
            p["fijo"], p["cel"],
            p["tipo_cliente"],
            TIPO_DEUDOR,
            SECTOR_ECONOMICO_DEFAULT,
            "N", "", "",
        ]),
        "|".join(["VEH", VEH_TIPO_REGISTRO, p["placa"], p["chasis"]]),
    ]


def excel_revision(prendas, advertencias, nit, acreedor) -> bytes:
    """Hoja de revisión (Garantías + Advertencias) para depurar antes
    de radicar — mismo formato que el export de solicitudes."""
    wb = Workbook()
    hoja = wb.active
    hoja.title = "Garantias"
    hoja.append(ENCABEZADOS_GARANTIAS)
    hoja_adv = wb.create_sheet("Advertencias")
    hoja_adv.append(ENCABEZADOS_ADVERTENCIAS)
    for c in hoja[1]:
        c.font = Font(bold=True)
    for c in hoja_adv[1]:
        c.font = Font(bold=True)
    for p in prendas:
        f_ini = p["f_ini"].date() if isinstance(p["f_ini"], datetime) else p["f_ini"]
        hoja.append([
            p["fila"],                    # "N° SOLICITUD" → fila de la hoja
            "CC",
            p["cedula"],
            p["cliente"],
            "NIT",
            nit,
            acreedor,
            "PRENDA SIN TENENCIA",
            "MOTOCICLETA",
            p["fabricante"],
            "",
            p["modelo"] or "",
            "",
            "",
            p["chasis"],
            p["chasis"],
            p["placa"],
            float(p["saldo"]) if p["saldo"] else None,
            float(p["saldo"]) if p["saldo"] else None,
            _ascii(p["mpio"]),
            _ascii(p["depto"]),
            f_ini.isoformat() if f_ini else "",
            "SUMOTO",
            "",
        ])
    for fila in advertencias:
        hoja_adv.append(fila)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def generar_desde_excel(
    db: Session,
    *,
    contenido: bytes,
    hoja: str,
    desde: int,
    nit: str | None = None,
    generado_por: str | None = None,
) -> tuple[bytes, str, int, list[list]]:
    """(txt, nombre_archivo, n_prendas, advertencias).

    Reserva el consecutivo del día en ``rngm_archivo_lote`` (la misma
    auditoría del cargue por solicitudes); el caller hace commit.
    404 si no hay filas PENDIENTE o la hoja no existe."""
    try:
        ws = openpyxl.load_workbook(BytesIO(contenido), data_only=True)[hoja]
    except KeyError:
        raise SolicitudNoEncontradaError(
            f"El archivo no tiene una hoja '{hoja}'."
        )
    except Exception as exc:
        raise SolicitudNoEncontradaError(
            f"No fue posible leer el Excel de registro: {exc}"
        )

    prendas, advertencias = leer_prendas(ws, desde)
    if not prendas:
        raise SolicitudNoEncontradaError(
            f"No hay garantías con estado PENDIENTE desde la fila {desde} "
            f"de la hoja '{hoja}'."
        )

    aliado = aliado_propio(db)
    nit_plano = _nit_sin_dv(nit or (aliado.nit if aliado else ""))
    if not nit_plano:
        advertencias.insert(
            0, ["", "", "", "Acreedor sin NIT: el PRN va vacío."]
        )
    acreedor = aliado.nombre if aliado else ""

    hoy = date.today()
    lineas = [l for p in prendas for l in lineas_rngm(p, nit_plano)]
    cuerpo = "\n".join([f"{len(lineas)}|{hoy:%d%m%Y}", *lineas]) + "\n"

    servicio = ArchivoPlanoRngmService(db)
    servicio._asegurar_tabla_lote()
    _, nombre, _ = servicio._reservar_lote(
        nit=nit_plano,
        fecha=hoy,
        n_garantias=len(prendas),
        n_registros=len(lineas),
        n_advertencias=len(advertencias),
        generado_por=generado_por,
    )
    return (
        cuerpo.encode("ascii"),
        nombre,
        len(prendas),
        advertencias,
        excel_revision(prendas, advertencias, nit_plano, acreedor),
        nit_plano,
        acreedor,
    )
