"""Cargue del log histórico de transacciones (Excel) a la base de datos.

El archivo "Log Transacciones Credito Digital" es el registro de
producción previo a esta aplicación: cada fila de la hoja ``base`` es
una solicitud con su cliente, evaluación del motor anterior, producto,
financiación y firma. Este script la importa a las tablas normalizadas
marcando cada solicitud con ``origen='cargue_historico'`` para que la
analítica (y el embudo) la distingan del flujo nuevo.

Decisiones de mapeo (el log tiene su propio ciclo de estados):

- estado 99 "Aprobado"      -> desembolsada + credito_financiacion
- estado 12 "Rechazado"     -> rechazada
- estado 30 "Anulado"       -> rechazada (en el log se contabiliza con
                              los rechazos del panel de efectividad)
- estado 40 "Finalizado"    -> cancelada (proceso terminado sin crédito:
                              0 firmas en el log)
- estado 35 "Cancelado"     -> cancelada
- otros códigos menores     -> creada (quedaron a mitad de flujo)
- ``decision`` refleja el desenlace, no la columna cruda del motor:
  aprobado solo para los créditos cerrados (estado 99), rechazado para
  12/30, vacío para canceladas/en curso.
- Columnas ``Evaluacion - X`` del log: valor numérico distinto de 0 =
  criterio fallido -> se registran como solicitud_causal (R13, R15,
  RC1, R14, R11, R10, R9, R8, R6, R7, R17, R2, R5, R12, R18, R4, R19,
  R3). Las evaluaciones quedan con origen_evaluacion='cargue_historico'.
- perfil_score se deriva del score con la escalera del motor
  (770/700/620/520); perfil_ingreso del ingreso en SMMLV con las bandas
  de reglas_perfil.py.

Idempotente: el id_solicitud es un UUID5 determinista del número de
solicitud + cédula + fecha; las filas ya cargadas se saltan. En
SQLite crea la columna ``origen`` si aún no existe (en Postgres la crea
la migración 0032).

Uso:

    python -m backend.database.cargue_log_historico --excel ruta.xlsx
    python -m backend.database.cargue_log_historico --excel ruta.xlsx --sqlite motor_decision.db
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import openpyxl
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db_models.auth_models import Concesionario
from backend.db_models.models import (
    AliadoFinanciero,
    CapacidadPago,
    Ciudad,
    Cliente,
    CreditoFinanciacion,
    CriterioEvaluacion,
    DatosLaborales,
    EvaluacionCredito,
    ProductoVehiculo,
    SolicitudCausal,
    SolicitudContactoVivienda,
    SolicitudCredito,
)

NS_LOG = uuid.UUID("9f0f4b3a-3c2a-4f6d-9b2f-4b7a0d1c2e55")

ORIGEN = "cargue_historico"
HOJA = "base"

# Columna (índice 0) de cada flag "Evaluacion - X" -> código de causal.
EVAL_COLUMNA_CAUSAL = {
    44: "R13",  # Edad
    45: "R15",  # Ingresos
    46: "RC1",  # Meses continuidad
    47: "RC1",  # Meses antigüedad (mismo criterio de continuidad)
    48: "R14",  # Score
    49: "R11",  # Obligaciones reestructuradas
    50: "R10",  # Calificación diferente A/B
    51: "R9",   # Mora histórica 90 días
    52: "R8",   # Mora histórica 60 días
    53: "R6",   # Mora 60 días vigente
    54: "R7",   # Mora histórica 30 días
    55: "R17",  # Endeudamiento
    56: "R2",   # Embargo
    57: "R5",   # Dudoso recaudo
    58: "R12",  # Documento vigente
    59: "R18",  # Disponible
    60: "R4",   # Cartera castigada
    61: "R19",  # Capacidad de pago
    62: "R3",   # Cancelaciones negativas
}

ESTADO_MAP = {
    99: "desembolsada",
    12: "rechazada",
    30: "rechazada",
    35: "cancelada",
    40: "cancelada",
}
DECISION_MAP = {
    99: "aprobado",
    12: "rechazado",
    30: "rechazado",
}

OCUPACION_MAP = {
    "empleado": "empleado",
    "independiente": "independiente",
    "pensionado": "pensionado",
    "fuerzas militares": "fuerzas_militares",
}
CONTRATO_MAP = {
    "indefinido": "indefinido",
    "fijo": "fijo",
    "obra o labor": "obra_labor",
    "no aplica": "no_aplica",
    "n/a": "no_aplica",
}

# Escaleras del motor (motor_parametros.py): score EP e IF comparten
# cortes; ingreso en SMMLV según ocupación.
CORTES_SCORE = (Decimal("770"), Decimal("700"), Decimal("620"), Decimal("520"))
BANDAS_INGRESO = {
    # ocupacion: (ALTO, MEDIO, BAJO, piso_gris)
    "empleado": (Decimal("1.6"), Decimal("1.4"), Decimal("1.0"), None),
    "pensionado": (Decimal("1.6"), Decimal("1.4"), Decimal("1.0"), None),
    "fuerzas_militares": (Decimal("1.6"), Decimal("1.4"), Decimal("1.0"), None),
    "independiente": (Decimal("2.5"), Decimal("2.0"), Decimal("1.6"), Decimal("1.4")),
}


# ---------------------------------------------------------------------------
# Normalización de celdas
# ---------------------------------------------------------------------------
def _txt(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        s = str(v).replace(",", "").replace("$", "").strip()
        try:
            return float(s)
        except ValueError:
            return None


def _int(v: Any) -> int | None:
    n = _num(v)
    return int(round(n)) if n is not None else None


def _bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("si", "sí", "s", "true", "1", "x"):
        return True
    if s in ("no", "false", "0"):
        return False
    n = _num(v)
    return n > 0 if n is not None else None


def _fecha(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if v is None or v == "":
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _fecha_hora(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v
    f = _fecha(v)
    return datetime(f.year, f.month, f.day) if f else None


def _fallo_eval(v: Any) -> bool:
    """Un flag 'Evaluacion - X' del log: numérico != 0 = criterio fallido."""
    n = _num(v)
    return n is not None and n != 0


def _perfil_score(score: float | None) -> str | None:
    if score is None:
        return None
    s = Decimal(str(score))
    a, b, c, d = CORTES_SCORE
    if s >= a:
        return "A"
    if s >= b:
        return "B"
    if s >= c:
        return "C"
    if s >= d:
        return "D"
    return None


def _perfil_ingreso(
    ingreso_smmlv: float | None,
    ocupacion: str | None,
    tipo_contrato: str | None,
    meses_continuidad: int | None,
) -> str | None:
    if ingreso_smmlv is None or ocupacion not in BANDAS_INGRESO:
        return None
    x = Decimal(str(ingreso_smmlv))
    alto, medio, bajo, piso_gris = BANDAS_INGRESO[ocupacion]
    if ocupacion == "empleado":
        if x < bajo:
            return None
        meses = meses_continuidad or 0
        exige = 6 if tipo_contrato == "indefinido" else 12
        cumple = tipo_contrato in ("indefinido", "fijo", "obra_labor") and meses >= exige
        if not cumple:
            return "GRIS"
    elif piso_gris is not None and x <= piso_gris:
        return None
    if x >= alto:
        return "ALTO"
    if x >= medio:
        return "MEDIO"
    if x >= bajo:
        return "BAJO"
    if piso_gris is not None:
        return "GRIS"
    return None


# Ciudades del log que faltan en el catálogo se crean con su
# departamento conocido; el resto opera en el Valle/Tolima.
DEPTOS_CIUDAD = {
    "IBAGUE": "Tolima",
    "MIRANDA": "Cauca",
    "ARMENIA": "Quindío",
    "PEREIRA": "Risaralda",
    "BOGOTA": "Cundinamarca",
    "MEDELLIN": "Antioquia",
}
# Sede del concesionario -> su ciudad (único punto de venta).
CIUDAD_SEDE = {
    "SUMOTO S.A": "PALMIRA",
}
_TILDES = str.maketrans("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun")


def _norm_ciudad(nombre: str | None) -> str:
    """Clave de ciudad: mayúsculas, sin tildes ni '(VALLE)' ni signos.

    El log mezcla 'TULUÁ' (con mojibake), 'Tulua' y 'TULUA (VALLE)'."""
    if not nombre:
        return ""
    s = str(nombre).strip().upper()
    s = s.split("(")[0].strip()
    s = s.translate(_TILDES)
    return "".join(ch for ch in s if ch.isalnum() or ch == " ")


def _etiqueta_ciudad(nombre_norm: str) -> str:
    return nombre_norm.title() if nombre_norm else nombre_norm


# ---------------------------------------------------------------------------
# Importación
# ---------------------------------------------------------------------------
# Tablas que escribe el cargue y cuyas columnas recientes puede no tener
# una BD SQLite de desarrollo vieja (create_all no migra en caliente).
_TABLAS_ESCRITAS = [
    Cliente,
    SolicitudCredito,
    DatosLaborales,
    SolicitudContactoVivienda,
    ProductoVehiculo,
    EvaluacionCredito,
    CapacidadPago,
    SolicitudCausal,
    CreditoFinanciacion,
]


def _asegurar_columnas(engine) -> None:
    """SQLite dev: agrega las columnas que el modelo declara y la tabla
    todavía no tiene (numero_motor/chasis/vin, factura_*, garantia_*,
    origen...). En Postgres cada columna la crea su migración de
    alembic."""
    if engine.dialect.name != "sqlite":
        return
    with engine.connect() as conn:
        for modelo in _TABLAS_ESCRITAS:
            tabla = modelo.__table__
            cols = {
                r[1]
                for r in conn.execute(
                    text(f"PRAGMA table_info({tabla.name})")
                )
            }
            for col in tabla.columns:
                if col.name in cols:
                    continue
                ddl = str(col.type.compile(dialect=engine.dialect))
                extra = (
                    " NOT NULL DEFAULT 'flujo'"
                    if col.name == "origen" and tabla.name == "solicitud_credito"
                    else ""
                )
                conn.execute(
                    text(
                        f"ALTER TABLE {tabla.name} "
                        f"ADD COLUMN {col.name} {ddl}{extra}"
                    )
                )
                print(f"  columna agregada: {tabla.name}.{col.name} ({ddl})")
        conn.commit()


def _uuid_log(num: Any, cedula: Any, fecha: datetime | None) -> uuid.UUID:
    return uuid.uuid5(NS_LOG, f"{num}|{cedula}|{fecha or ''}")


def _uuid_texto(v: Any) -> uuid.UUID | None:
    s = _txt(v)
    if not s:
        return None
    try:
        return uuid.UUID(s)
    except ValueError:
        return None


def _id_ciudad(db: Session, ciudades: dict[str, int], nombre_log: Any) -> int | None:
    """Resuelve la ciudad del log contra el catálogo (nombre
    normalizado; 'TULUÁ' y 'TULUA (VALLE)' → 'TULUA'); si no existe la
    crea — son ciudades reales del área de operación."""
    norm = _norm_ciudad(_txt(nombre_log))
    if not norm:
        return None
    if norm in ciudades:
        return ciudades[norm]
    # Nombre recortado por mojibake ('TULU' por 'TULUÁ'): prefijo en
    # cualquier dirección contra el catálogo.
    for clave, cid in ciudades.items():
        if clave and (clave.startswith(norm) or norm.startswith(clave)):
            return cid
    ciudad = Ciudad(
        nombre=_etiqueta_ciudad(norm),
        departamento=DEPTOS_CIUDAD.get(norm, "Valle del Cauca"),
    )
    db.add(ciudad)
    db.flush()
    ciudades[norm] = ciudad.id_ciudad
    return ciudad.id_ciudad


def _cargar(
    db: Session,
    filas: list[tuple[int, Any]],
    ciudades: dict[str, int],
    conservar_num: bool,
) -> dict[str, int]:
    criterios = {c.codigo: c for c in db.scalars(select(CriterioEvaluacion))}
    concesionarios = {
        c.nombre.strip().upper(): c
        for c in db.scalars(select(Concesionario))
    }
    # Sede -> su ciudad de operación si aún no la tiene asignada.
    for nombre, conc in concesionarios.items():
        clave = CIUDAD_SEDE.get(nombre)
        if conc.id_ciudad is None and clave:
            conc.id_ciudad = _id_ciudad(db, ciudades, clave)
    concesionarios_ids = {
        nombre: conc.id_concesionario for nombre, conc in concesionarios.items()
    }
    aliado = db.scalar(select(AliadoFinanciero).limit(1))

    existentes = set(
        db.scalars(
            select(SolicitudCredito.id_solicitud).where(SolicitudCredito.origen == ORIGEN)
        )
    )
    numeros_usados = set(
        n for n in db.scalars(
            select(SolicitudCredito.num_solicitud).where(
                SolicitudCredito.num_solicitud.isnot(None)
            )
        )
        if n is not None
    )
    clientes = {
        c.num_cedula: c
        for c in db.scalars(select(Cliente).where(Cliente.num_cedula.isnot(None)))
    }

    nuevas = saltadas = errores = 0
    lote = 0
    for _, r in filas:
        fecha = _fecha_hora(r[1])
        num = _int(r[9])
        cedula = _txt(r[15])
        sid = _uuid_log(num, cedula, fecha)
        if sid in existentes:
            saltadas += 1
            continue

        cliente_nuevo: Cliente | None = None
        try:
            ocupacion = OCUPACION_MAP.get((_txt(r[23]) or "").lower())
            nacimiento = _fecha(r[19])
            if nacimiento is None:
                edad = _int(r[26])
                if edad and fecha:
                    nacimiento = date(fecha.year - edad, 6, 1)
                else:
                    nacimiento = date(1900, 1, 1)

            cliente = clientes.get(cedula) if cedula else None
            if cliente is None:
                cedula = cedula or f"LOG-SIN-CC-{num or 'X'}-{len(clientes)}"
                cliente = clientes.get(cedula)
            if cliente is None:
                nombre = _txt(r[16]) or "Sin nombre"
                partes = nombre.split()
                cliente = Cliente(
                    tipo_documento=_txt(r[14]) or "CC",
                    num_cedula=cedula,
                    nombre_completo=nombre,
                    primer_apellido=partes[-1] if partes else None,
                    fecha_nacimiento=nacimiento,
                    fecha_expedicion=_fecha(r[17]),
                    ocupacion=ocupacion,
                    nacionalidad=_txt(r[21]) or "Colombiana",
                )
                db.add(cliente)
                db.flush()
                clientes[cedula] = cliente
                cliente_nuevo = cliente

            codigo_estado = _int(r[65])
            estado = ESTADO_MAP.get(codigo_estado, "creada")
            decision = DECISION_MAP.get(codigo_estado)
            desc = _txt(r[66]) or "Cargue histórico"
            num_guardado = (
                num
                if conservar_num and num is not None and num not in numeros_usados
                else None
            )
            if num_guardado is not None:
                numeros_usados.add(num_guardado)

            solicitud = SolicitudCredito(
                id_solicitud=sid,
                num_solicitud=num_guardado,
                id_cliente=cliente.id_cliente,
                asesor_nombre=_txt(r[3]),
                id_concesionario=concesionarios_ids.get((_txt(r[4]) or "").upper()),
                fecha_hora=fecha or datetime(2020, 1, 1),
                moneda="COP",
                decision=decision,
                estado=estado,
                descripcion_estado=f"Log #{num}: {desc}" if num else desc,
                fecha_hora_firma=_fecha_hora(r[137]),
                uuid_firma=_uuid_texto(r[138]),
                autenticacion=_txt(r[134]),
                origen=ORIGEN,
            )
            db.add(solicitud)
            db.flush()

            db.add(
                DatosLaborales(
                    id_solicitud=sid,
                    tipo_contrato=CONTRATO_MAP.get((_txt(r[24]) or "").lower()),
                    meses_continuidad=_int(r[27]),
                    ingreso_mensual=_num(r[70]),
                    nombre_empresa=_txt(r[125]),
                    fecha_ingreso=_fecha(r[127]),
                    nivel_educativo=_txt(r[128]),
                    profesion=_txt(r[129]),
                    cargo=_txt(r[130]),
                    actividad_comercial=_txt(r[131]),
                    anios_camara_comercio=_num(r[25]),
                )
            )
            db.add(
                SolicitudContactoVivienda(
                    id_solicitud=sid,
                    estrato=_int(r[112]),
                    personas_a_cargo=_int(r[116]),
                    tipo_vivienda=_txt(r[113]),
                    correo=_txt(r[10]),
                    telefono=_txt(r[11]),
                    direccion=_txt(r[109]),
                    barrio=_txt(r[110]),
                    id_ciudad=_id_ciudad(db, ciudades, r[111]),
                    zona_rural=_bool(r[114]),
                    estado_civil=_txt(r[115]),
                    num_hijos=_int(r[117]),
                    es_cabeza_familia=_bool(r[118]),
                    cuenta_bienes_raices=_bool(r[119]),
                    cuenta_vehiculo=_bool(r[120]),
                    tiene_moto=((_int(r[121]) or 0) > 0) if r[121] not in (None, "") else None,
                    tiene_carro=_bool(r[122]),
                    primera_moto=_bool(r[123]),
                    estoy_financiando=_bool(r[124]),
                )
            )
            vehiculo = ProductoVehiculo(
                id_solicitud=sid,
                producto_a_financiar=_txt(r[80]) or "Motocicleta",
                marca=_txt(r[81]),
                referencia=_txt(r[82]),
                modelo=_txt(r[83]),
                color=_txt(r[84]),
                valor_moto_iva=_num(r[85]),
                descuento_pesos=_num(r[86]) or 0,
                descuento_pct=_num(r[87]) or 0,
                accesorios=_num(r[88]) or 0,
                matricula=_num(r[89]) or 0,
                soat=_num(r[90]) or 0,
                impuestos=_num(r[91]) or 0,
                aval_pct=_num(r[92]),
            )
            db.add(vehiculo)
            db.flush()

            score = _num(r[29])
            # 'Ingresos' del log ya viene en SMMLV (mediana ~1.25);
            # 'ingreso mensual' es el valor declarado en pesos.
            salario = _num(r[67])
            ingreso_smmlv = _num(r[68])
            ingreso_final = (
                ingreso_smmlv * salario if ingreso_smmlv and salario else _num(r[70])
            )
            tiene_eval = score is not None or _txt(r[63]) is not None
            if tiene_eval:
                db.add(
                    EvaluacionCredito(
                        id_solicitud=sid,
                        version=1,
                        vigente=True,
                        origen_evaluacion=ORIGEN,
                        score=score,
                        valor_ingreso=_num(r[70]),
                        ingreso_final=ingreso_final,
                        endeudamiento=_num(r[36]),
                        capacidad_pago=_num(r[42]),
                        mora_historica_90=_int(r[32]) or 0,
                        mora_historica_60=_int(r[33]) or 0,
                        mora_historica_30=_int(r[35]) or 0,
                        mora_60=_int(r[34]) or 0,
                        embargo=_int(r[37]) or 0,
                        dudoso_recaudo=_int(r[38]) or 0,
                        cartera_castigada=_int(r[41]) or 0,
                        cancelaciones_negativas=_int(r[43]) or 0,
                        obligaciones_reestructuradas=_int(r[30]) or 0,
                        calificacion_diferente_ab=_int(r[31]) or 0,
                        documento_vigente=_bool(r[39]),
                        quanto3_medio=_num(r[69]),
                        score_codigo_exclusion=(
                            str(_int(r[48])) if _fallo_eval(r[48]) else None
                        ),
                        perfil_score=_perfil_score(score),
                        perfil_ingreso=_perfil_ingreso(
                            ingreso_smmlv,
                            ocupacion,
                            CONTRATO_MAP.get((_txt(r[24]) or "").lower()),
                            _int(r[27]),
                        ),
                        decision_interna=_txt(r[63]),
                    )
                )
                db.add(
                    CapacidadPago(
                        id_solicitud=sid,
                        version=1,
                        vigente=True,
                        salario_minimo=salario,
                        ingreso_final=ingreso_final,
                        ingreso_final_smlmv=ingreso_smmlv,
                        gastos_personales=_num(r[71]),
                        disponible_1=_num(r[74]),
                        capacidad_pago_2=_num(r[75]),
                        cupo_aprobado=_num(r[76]),
                        cupo_calculado=_num(r[77]),
                        tasa_cupo=_num(r[78]),
                        plazo_cupo=_int(r[79]),
                    )
                )

            if decision == "rechazado":
                codigos_vistos: set[str] = set()
                for idx, codigo in EVAL_COLUMNA_CAUSAL.items():
                    if not _fallo_eval(r[idx]) or codigo in codigos_vistos:
                        continue
                    codigos_vistos.add(codigo)
                    criterio = criterios.get(codigo)
                    descripcion = criterio.descripcion if criterio else codigo
                    db.add(
                        SolicitudCausal(
                            id_solicitud=sid,
                            id_criterio=criterio.id_criterio if criterio else None,
                            codigo=codigo,
                            descripcion=descripcion,
                            activa=True,
                        )
                    )

            if estado == "desembolsada":
                db.add(
                    CreditoFinanciacion(
                        id_solicitud=sid,
                        id_vehiculo=vehiculo.id_vehiculo,
                        id_aliado_financiero=aliado.id_aliado if aliado else None,
                        ganadora=True,
                        aval_pct=_num(r[92]),
                        tasa=_num(r[93]) or 0,
                        plazo=_int(r[94]) or 0,
                        seguro=_num(r[95]) or 0,
                        cuota_inicial=_num(r[96]) or 0,
                        valor_financiar=_num(r[97]) or 0,
                        gastos_administrativos=_num(r[98]) or 0,
                        saldo_financiar=_num(r[99]) or 0,
                        valor_financiacion=_num(r[100]) or 0,
                        valor_seguro_vida=_num(r[101]) or 0,
                        total_a_pagar=_num(r[102]) or 0,
                        cuota_financiacion=_num(r[103]) or 0,
                        cuota_seguro_vida=_num(r[104]) or 0,
                        cuota_total=_num(r[105]) or 0,
                        dia_pago=_int(r[106]),
                        fecha_inicio=_fecha(r[107]),
                        fecha_fin=_fecha(r[108]),
                    )
                )

            nuevas += 1
            lote += 1
            if lote >= 400:
                db.commit()
                lote = 0
        except Exception as exc:  # noqa: BLE001 - cargue masivo: reporta y sigue
            errores += 1
            db.rollback()
            if cliente_nuevo is not None:
                clientes.pop(cliente_nuevo.num_cedula, None)
            print(f"  fila num={num} cedula={cedula}: {exc}", file=sys.stderr)

    db.commit()
    return {"nuevas": nuevas, "saltadas": saltadas, "errores": errores}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--excel", required=True, metavar="RUTA.xlsx",
                        help="Log de transacciones (hoja 'base')")
    parser.add_argument("--hoja", default=HOJA, help="Hoja a leer (defecto 'base')")
    parser.add_argument("--sqlite", metavar="RUTA.db",
                        help="Usar un archivo SQLite en vez del DATABASE_URL")
    parser.add_argument("--reprocesar", action="store_true",
                        help="Borra el cargue histórico existente y vuelve a importarlo")
    args = parser.parse_args()

    ruta = Path(args.excel)
    if not ruta.exists():
        sys.exit(f"No existe el archivo: {ruta}")

    url = (
        f"sqlite:///{args.sqlite}"
        if args.sqlite
        else get_settings().sqlalchemy_database_url()
    )
    engine = create_engine(url, pool_pre_ping=True)
    _asegurar_columnas(engine)
    # En Postgres num_solicitud es GENERATED ALWAYS AS IDENTITY: no
    # admite valores explícitos; en SQLite sí se conserva el número del
    # log cuando no choca con una radicación del flujo nuevo.
    conservar_num = engine.dialect.name == "sqlite"

    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    ws = wb[args.hoja]
    filas = [
        (i, r)
        for i, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2)
        if r[15] is not None or r[9] is not None
    ]
    wb.close()
    print(f"{len(filas)} filas con datos en '{args.hoja}'")

    with Session(engine) as db:
        if args.reprocesar:
            ids = list(
                db.scalars(
                    select(SolicitudCredito.id_solicitud).where(
                        SolicitudCredito.origen == ORIGEN
                    )
                )
            )
            if ids:
                # Hijos primero: SQLite dev no fuerza ON DELETE CASCADE.
                for modelo in (
                    SolicitudCausal,
                    CreditoFinanciacion,
                    EvaluacionCredito,
                    CapacidadPago,
                    ProductoVehiculo,
                    DatosLaborales,
                    SolicitudContactoVivienda,
                ):
                    db.execute(
                        modelo.__table__.delete().where(
                            modelo.__table__.c.id_solicitud.in_(ids)
                        )
                    )
                db.execute(
                    SolicitudCredito.__table__.delete().where(
                        SolicitudCredito.id_solicitud.in_(ids)
                    )
                )
                db.commit()
            print(f"Reprocesar: {len(ids)} filas del cargue eliminadas")
        ciudades = {
            _norm_ciudad(c.nombre): c.id_ciudad
            for c in db.scalars(select(Ciudad))
        }
        resumen = _cargar(db, filas, ciudades, conservar_num)
        total = db.scalar(
            select(func.count()).select_from(SolicitudCredito).where(
                SolicitudCredito.origen == ORIGEN
            )
        )

    print(
        f"Cargue: {resumen['nuevas']} nuevas, {resumen['saltadas']} ya estaban, "
        f"{resumen['errores']} con error. Total cargue_histórico en BD: {total}."
    )


if __name__ == "__main__":
    main()
    sys.exit(0)
