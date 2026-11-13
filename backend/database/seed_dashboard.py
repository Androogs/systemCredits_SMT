"""Siembra de solicitudes demo para el dashboard (Resumen + embudo).

La BD real quedó con pocas radicaciones recientes y casi ninguna con
sede/asesor, así que los paneles se ven vacíos. Este script completa
`--total` solicitudes (por defecto 75) repartidas en los últimos 6
meses y cubriendo TODAS las dimensiones que grafica el Resumen:

- estados: creada / en_evaluacion / aprobada / rechazada /
  en_revision / desembolsada / cancelada (con decision coherente);
- embudo: evaluadas (decision), aprobadas (decision=aprobado),
  formalizadas (fecha_hora_firma), desembolsadas (estado);
- causales: TODOS los códigos del catálogo criterio_evaluacion
  (R1..R25, RC1..RC4, E1..E9) repartidos entre las rechazadas;
- perfiles: perfil_score A/B/C/D y perfil_ingreso ALTO/MEDIO/BAJO/GRIS;
- dimensiones: ocupacion (4), destino_credito (6), plazos 12/24/36/48,
  tipo_contrato (4), meses_continuidad, las 3 sedes y varios asesores;
- cuota/cupo: oferta seleccionada + capacidad_pago en las aprobadas.

También crea asesores demo (usuario + rol asesor + ficha, clave
Asesor123!) en las sedes que no tienen, para que el ranking y el
filtro por asesor tengan más de un titular.

Idempotente: solo agrega las solicitudes que falten para llegar a
--total (las cédulas demo son 88XXXXXXX) y los asesores se buscan por
correo antes de crearse. Uso:

    python -m backend.database.seed_dashboard            # hasta 75
    python -m backend.database.seed_dashboard --total 120
    python -m backend.database.seed_dashboard --sqlite ruta.db
"""

import argparse
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select

from backend.config import get_settings
from backend.db_models.auth_models import Asesor, Concesionario, Rol, Usuario, UsuarioRol
from backend.db_models.models import (
    AliadoProducto,
    CapacidadPago,
    Cliente,
    CriterioEvaluacion,
    DatosLaborales,
    EvaluacionCredito,
    OfertaCredito,
    ProductoVehiculo,
    SolicitudCausal,
    SolicitudContactoVivienda,
    SolicitudCredito,
)
from sqlalchemy.orm import Session

RNG = random.Random(20261029)

# Mismo hash bcrypt que insert.sql (asesor@sumoto.com.co / Asesor123!):
# las cuentas demo nuevas comparten clave con el usuario de prueba.
HASH_ASESOR_DEMO = "$2b$12$kgMN4JFNA8mB9ak/aftAueZ2djG5QcixL5cchV5iolgYo9dkt8fQa"

TASA_PRODUCTO = 2.1175  # % m.v. operativa (usura menos un punto base)
SMMLV = 1_750_905

OCUPACIONES = ["empleado", "independiente", "pensionado", "fuerzas_militares"]
DESTINOS = [
    "El sueño de tener motocicleta",
    "Una solución de movilidad",
    "Un medio para generar ingresos adicionales",
    "Un medio para sustento económico",
    "La oportunidad de construir historial crediticio",
    "Un medio de transporte amigable con el medio ambiente",
]
LINEAS = ["Crédito Directo", "Sumoto Preferencial", "Credicontado", "Motocicleta"]
PLAZOS = [12, 24, 36, 48]
TIPOS_CONTRATO_EMPLEADO = ["indefinido", "fijo", "obra_labor"]

# Asesores demo de SUMOTO S.A (correo, nombre, cédula). Conviven con
# el asesor de prueba ya sembrado.
ASESORES_DEMO = [
    ("diana.rios@sumoto.com.co", "Diana Marcela Ríos", "32333444"),
    ("laura.cifuentes@sumoto.com.co", "Laura Cifuentes", "30111222"),
    ("carlos.mena@sumoto.com.co", "Carlos Andrés Mena", "31222333"),
]

# Único punto de venta: todos los asesores demo radican por SUMOTO S.A
# (se resuelve por nombre, no por id serial).
CONCESIONARIO_DEMO = "SUMOTO S.A"

NOMBRES = [
    "Juan Camilo", "Andrés Felipe", "Luisa Fernanda", "Camila Andrea",
    "Jhon Alexander", "Yurany", "Óscar David", "Paola Andrea",
    "Santiago", "Valentina", "Wilson Javier", "Leidy Johana",
    "Fabián Andrés", "Natalia", "Cristian Camilo", "Diana Carolina",
    "Jeison Steven", "Ángela María", "Brayan Stiven", "Tatiana",
    "Edgar Andrés", "Milena", "Harol Stiven", "Karen Dayana",
]
APELLIDOS = [
    "Rodríguez", "García", "Martínez", "López", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Gómez", "Díaz",
    "Vargas", "Castro", "Ruiz", "Álvarez", "Romero", "Suárez",
    "Rojas", "Moreno", "Muñoz", "Valencia", "Cortés", "Guerrero",
]
EMPRESAS = [
    "Almacenes Éxito S.A.", "Transportes del Valle", "Panadería La Central",
    "Comercializadora Andina", "Talleres El Progreso", "Cárnicos del Sur",
    "Textiles Palmira", "Distribuciones La 14", "Ferretería El Tornillo",
    "Restaurante Fogón Caleño", "Agropecuaria Santa Rosa", "Muebles Valencia",
]
CARGOS = [
    "Vendedor", "Auxiliar contable", "Operario", "Conductor", "Cajera",
    "Supervisor", "Técnico", "Mecánico", "Administrativo", "Mensajero",
]
PROFESIONES = [
    "Bachiller", "Técnico en sistemas", "Tecnólogo en ventas",
    "Contador público", "Ingeniero industrial", "Administrador",
    "Enfermera auxiliar", "Electricista",
]
MOTOS = {
    "Bajaj": ["Boxer CT 100", "Pulsar NS 125", "Pulsar NS 200", "Discover 125", "Platino 110"],
    "Hero": ["Eco 100", "Hunk 150", "Xpulse 200", "Dash 110"],
    "AKT": ["NKD 125", "CR4 125", "Dynamic Pro 150"],
    "Suzuki": ["GN 125", "GIXXER 150", "NKD 125"],
    "Honda": ["CB 125F", "CB 190R", "XR 150L", "Navi 110"],
    "TVS": ["Apache RTR 160", "Ntorq 125", "Sport 110"],
}
BARRIOS = [
    "La Flora", "El Ingenio", "Pradera", "Zamorano", "Chapultepec",
    "Santa Emilia", "Villa Colombia", "Centro", "La Esmeralda",
    "Versalles", "San Fernando", "El Recreo",
]
ESTADOS_CIVILES = ["Soltero(a)", "Casado(a)", "Unión libre", "Divorciado(a)"]
TIPOS_VIVIENDA = ["Propia", "Familiar", "Arrendada"]

# Causal → contadores de buró coherentes con su descripción (realismo
# del expediente del motor; no afecta las métricas del panel).
CONTADORES_BURO = {
    "R1": {"reportado_fallecido": True},
    "R2": {"embargo": 1},
    "R3": {"cancelaciones_negativas": 1},
    "R4": {"cartera_castigada": 1},
    "R5": {"dudoso_recaudo": 1},
    "R6": {"mora_60": 1},
    "R7": {"mora_historica_30": 1},
    "R8": {"mora_historica_60": 1},
    "R9": {"mora_historica_90": 1},
    "R10": {"calificacion_diferente_ab": 1},
    "R11": {"obligaciones_reestructuradas": 1},
    "R12": {"documento_vigente": False},
    "E2": {"mora_30": 1},
}

# Reparto de estados de las solicitudes nuevas (sobre 46 ≈ 75 - 29).
# Cada tupla: (estado, decision, firma, con_evaluacion).
PLAN_ESTADOS = (
    [("rechazada", "rechazado", False, True)] * 20
    + [("aprobada", "aprobado", True, True)] * 7
    + [("aprobada", "aprobado", False, True)] * 6
    + [("desembolsada", "aprobado", True, True)] * 4
    + [("creada", None, False, False)] * 4
    + [("en_evaluacion", None, False, False)] * 3
    # en_revision es legado del comité; conserva evaluación 'Estudio'.
    + [("en_revision", None, False, True)]
    + [("cancelada", None, False, False)]
)

# Solicitudes por mes (0 = el actual … 5 = hace 5 meses): más del 40 %
# en el mes en curso para que los KPIs "del mes" no queden en cero.
PESOS_MES = [0.40, 0.22, 0.14, 0.10, 0.08, 0.06]


def _cuota_anualidad(monto: float, tasa_mv: float, plazo: int) -> float:
    i = tasa_mv / 100
    return monto * i / (1 - (1 + i) ** -plazo)


def _fecha_en_mes(meses_atras: int, ahora: datetime) -> datetime:
    """Día/hora aleatorios dentro del mes `meses_atras` (sin pasar hoy)."""
    inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(meses_atras):
        inicio = (inicio - timedelta(days=1)).replace(day=1)
    fin = (
        ahora
        if meses_atras == 0
        else (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        - timedelta(seconds=1)
    )
    fecha = inicio + timedelta(
        seconds=RNG.uniform(0, (fin - inicio).total_seconds())
    )
    fecha = fecha.replace(
        hour=RNG.randint(8, 18),
        minute=RNG.randint(0, 59),
        second=0,
        microsecond=0,
    )
    return min(fecha, ahora)


def _asegurar_asesores(db: Session) -> dict[int, list[Asesor]]:
    """Crea (si faltan) los asesores demo y devuelve sede → asesores.

    Incluye los asesores ya existentes en cada concesionario para que
    las radicaciones nuevas también repartan sobre los de prueba.
    """
    rol_asesor = db.scalar(select(Rol).where(Rol.nombre == "asesor"))
    concesionario = db.scalar(
        select(Concesionario).where(Concesionario.nombre == CONCESIONARIO_DEMO)
    )
    id_concesionario = concesionario.id_concesionario if concesionario else None
    for correo, nombre, cedula in ASESORES_DEMO:
        usuario = db.scalar(select(Usuario).where(Usuario.correo == correo))
        if usuario is None:
            usuario = Usuario(
                id_usuario=uuid.uuid4(),
                correo=correo,
                hash_contrasena=HASH_ASESOR_DEMO,
                estado="activo",
                nombre_completo=nombre,
                fecha_verificacion=datetime.now(timezone.utc),
            )
            db.add(usuario)
            db.flush()
            if rol_asesor is not None:
                db.add(UsuarioRol(id_usuario=usuario.id_usuario, id_rol=rol_asesor.id_rol))
        asesor = db.scalar(select(Asesor).where(Asesor.id_usuario == usuario.id_usuario))
        if asesor is None:
            db.add(
                Asesor(
                    id_usuario=usuario.id_usuario,
                    nombre=nombre,
                    num_cedula=cedula,
                    id_concesionario=id_concesionario,
                )
            )
    db.flush()
    # Radicadores del demo: solo fichas con cédula (los asesores de
    # prueba sin cédula quedan fuera — dos cuentas con el mismo nombre
    # generarían filas duplicadas en el ranking).
    por_sede: dict[int, list[Asesor]] = {}
    for a in db.scalars(
        select(Asesor).where(
            Asesor.id_concesionario.isnot(None),
            Asesor.num_cedula.isnot(None),
        )
    ):
        por_sede.setdefault(a.id_concesionario, []).append(a)
    return por_sede


def _cedulas_libres(db: Session, cuantas: int) -> list[str]:
    """Siguiente bloque de cédulas demo 88XXXXXXX sin colisionar."""
    ultima = db.scalar(
        select(func.max(Cliente.num_cedula)).where(Cliente.num_cedula.like("88%"))
    )
    base = int(ultima) + 1 if ultima else 880_000_001
    return [str(base + i) for i in range(cuantas)]


def _plan_estados(n: int) -> list[tuple[str, str | None, bool, bool]]:
    """Reparte `n` solicitudes con la mezcla de PLAN_ESTADOS.

    Con n=46 reproduce exactamente la mezcla fija; con otro n escala
    las proporciones manteniendo al menos una de cada estado.
    """
    if n == len(PLAN_ESTADOS):
        plan = list(PLAN_ESTADOS)
    else:
        pesos = [
            ("rechazada", "rechazado", False, True, 0.44),
            ("aprobada", "aprobado", True, True, 0.15),
            ("aprobada", "aprobado", False, True, 0.13),
            ("desembolsada", "aprobado", True, True, 0.09),
            ("creada", None, False, False, 0.09),
            ("en_evaluacion", None, False, False, 0.07),
            ("en_revision", None, False, True, 0.02),
            ("cancelada", None, False, False, 0.01),
        ]
        plan = [
            (estado, decision, firma, ev)
            for estado, decision, firma, ev, peso in pesos
            for _ in range(max(1, round(n * peso)))
        ]
        plan = plan[:n] + [("aprobada", "aprobado", True, True)] * max(0, n - len(plan))
    RNG.shuffle(plan)
    return plan


def _solicitud_demo(
    db: Session,
    cedula: str,
    plan: tuple[str, str | None, bool, bool],
    ahora: datetime,
    asesores_por_sede: dict[int, list[Asesor]],
    catalogo_causales: list[CriterioEvaluacion],
    codigos_causales: list[str],
    producto: AliadoProducto | None,
    hoy: bool = False,
) -> None:
    estado, decision, firmada, con_evaluacion = plan
    ocupacion = RNG.choices(OCUPACIONES, weights=[45, 30, 15, 10])[0]
    nombres = RNG.choice(NOMBRES).split()
    apellidos = RNG.sample(APELLIDOS, 2)
    fecha_nacimiento = date(
        ahora.year - RNG.randint(19, 62), RNG.randint(1, 12), RNG.randint(1, 28)
    )
    cliente = Cliente(
        tipo_documento="CC",
        num_cedula=cedula,
        nombre_completo=" ".join(nombres + apellidos),
        primer_apellido=apellidos[0],
        fecha_nacimiento=fecha_nacimiento,
        fecha_expedicion=fecha_nacimiento.replace(year=fecha_nacimiento.year + 18),
        id_ciudad_expedicion=RNG.randint(1, 8),
        id_ciudad_nacimiento=RNG.randint(1, 8),
        ocupacion=ocupacion,
        nacionalidad="Colombiana",
    )
    db.add(cliente)
    db.flush()

    sede = RNG.choices(
        sorted(asesores_por_sede), weights=[40, 35, 25][: len(asesores_por_sede)]
    )[0]
    asesor = RNG.choice(asesores_por_sede[sede])
    fecha = ahora if hoy else _fecha_en_mes(
        RNG.choices(range(len(PESOS_MES)), weights=PESOS_MES)[0], ahora
    )
    plazo = RNG.choice(PLAZOS)
    solicitud = SolicitudCredito(
        id_solicitud=uuid.uuid4(),
        id_cliente=cliente.id_cliente,
        id_asesor=asesor.id_asesor,
        asesor_nombre=asesor.nombre,
        asesor_cedula=asesor.num_cedula,
        id_concesionario=sede,
        fecha_hora=fecha,
        moneda="COP",
        decision=decision,
        estado=estado,
        linea_credito=RNG.choice(LINEAS),
        destino_credito=RNG.choice(DESTINOS),
        plazo_deseado_meses=plazo,
        fecha_hora_firma=(
            fecha + timedelta(days=RNG.randint(2, 10), hours=RNG.randint(1, 8))
            if firmada
            else None
        ),
        uuid_firma=uuid.uuid4() if firmada else None,
        autenticacion="OTP SMS" if firmada else None,
    )
    db.add(solicitud)
    db.flush()

    # Datos laborales: tipo_contrato aplica a empleados; el resto queda
    # no_aplica o sin dato para poblar ambos segmentos del panel.
    if ocupacion == "empleado":
        tipo_contrato = RNG.choice(TIPOS_CONTRATO_EMPLEADO)
    else:
        tipo_contrato = RNG.choice(["no_aplica", None])
    ingreso = RNG.randrange(1_400_000, 8_200_000, 50_000)
    db.add(
        DatosLaborales(
            id_solicitud=solicitud.id_solicitud,
            tipo_contrato=tipo_contrato,
            meses_continuidad=RNG.randint(0, 48),
            anios_camara_comercio=(
                RNG.choice([0.5, 1, 1.5, 2, 3, 4, 5, 6, 8])
                if ocupacion == "independiente"
                else None
            ),
            ingreso_mensual=ingreso,
            otros_ingresos=RNG.choice([0, 0, 0, RNG.randrange(200_000, 1_500_000, 50_000)]),
            nombre_empresa=RNG.choice(EMPRESAS) if ocupacion == "empleado" else None,
            cargo=RNG.choice(CARGOS),
            profesion=RNG.choice(PROFESIONES),
            nivel_educativo=RNG.choice(
                ["Bachiller", "Técnico", "Tecnólogo", "Profesional", "Posgrado"]
            ),
            actividad_comercial=(
                RNG.choice(["Comercio", "Servicios", "Transporte", "Alimentos"])
                if ocupacion == "independiente"
                else None
            ),
        )
    )
    db.add(
        SolicitudContactoVivienda(
            id_solicitud=solicitud.id_solicitud,
            estrato=RNG.randint(1, 4),
            personas_a_cargo=RNG.randint(0, 5),
            tipo_vivienda=RNG.choice(TIPOS_VIVIENDA),
            correo=f"{nombres[0].lower()}.{apellidos[0].lower()}{RNG.randint(1, 99)}@correo.co",
            telefono=f"3{RNG.choice(['00', '01', '05', '10', '15', '20'])}{RNG.randint(1000000, 9999999)}",
            direccion=f"Calle {RNG.randint(1, 80)} #{RNG.randint(1, 50)}-{RNG.randint(1, 99)}",
            barrio=RNG.choice(BARRIOS),
            id_ciudad=RNG.randint(1, 8),
            estado_civil=RNG.choice(ESTADOS_CIVILES),
            num_hijos=RNG.randint(0, 4),
            es_cabeza_familia=RNG.choice([True, False]),
            cuenta_bienes_raices=RNG.choice([True, False]),
            cuenta_vehiculo=RNG.choice([True, False]),
            tiene_moto=RNG.choice([True, False, False]),
            tiene_carro=RNG.choice([True, False, False, False]),
            primera_moto=RNG.choice([True, False]),
            estoy_financiando=RNG.choice([True, False]),
        )
    )
    marca = RNG.choice(list(MOTOS))
    valor_moto = RNG.randrange(4_000_000, 14_000_000, 100_000)
    db.add(
        ProductoVehiculo(
            id_solicitud=solicitud.id_solicitud,
            producto_a_financiar="Motocicleta",
            marca=marca,
            referencia=RNG.choice(MOTOS[marca]),
            modelo=str(RNG.randint(2023, 2026)),
            color=RNG.choice(["Negro", "Blanco", "Rojo", "Azul", "Gris"]),
            valor_moto_iva=valor_moto,
            matricula=RNG.choice([350_000, 400_000, 450_000]),
            soat=RNG.choice([550_000, 620_000, 700_000]),
            impuestos=RNG.choice([0, 80_000, 120_000]),
        )
    )

    if not con_evaluacion:
        if estado == "cancelada":
            solicitud.descripcion_estado = "Cancelada: desistimiento del cliente"
        return

    # --- Evaluación + capacidad (hitos del embudo: decision) ---
    es_rechazo = decision == "rechazado"
    codigos = codigos_causales if es_rechazo else []
    if es_rechazo and "R25" in codigos:
        perfil_score = "D"
        score = RNG.randint(500, 590)
    elif es_rechazo:
        perfil_score = RNG.choices(["A", "B", "C", "D"], weights=[15, 30, 40, 15])[0]
        score = RNG.randint(540, 780)
    elif estado == "en_revision":
        perfil_score = RNG.choice(["B", "C"])
        score = RNG.randint(600, 720)
    else:
        perfil_score = RNG.choices(["A", "B", "C"], weights=[40, 35, 25])[0]
        score = {
            "A": RNG.randint(760, 860),
            "B": RNG.randint(685, 750),
            "C": RNG.randint(605, 680),
        }[perfil_score]
    perfil_ingreso = (
        RNG.choices(["ALTO", "MEDIO", "BAJO", "GRIS"], weights=[30, 30, 25, 15])[0]
        if es_rechazo or estado == "en_revision"
        else RNG.choices(["ALTO", "MEDIO", "BAJO"], weights=[40, 35, 25])[0]
    )
    endeudamiento = (
        RNG.uniform(55, 95)
        if es_rechazo
        else RNG.uniform(15, 55)
    )
    ingreso_final = ingreso + RNG.randrange(0, 500_000, 50_000)
    buro: dict = {}
    for codigo in codigos:
        buro.update(CONTADORES_BURO.get(codigo, {}))
    monto_aprobado = max(
        500_000,
        valor_moto
        + RNG.randrange(800_000, 1_600_000, 50_000)
        + 200_000
        - RNG.randrange(0, 2_500_000, 100_000),
    )
    capacidad = RNG.randrange(800_000, 3_200_000, 50_000) if not es_rechazo else None

    evaluacion = EvaluacionCredito(
        id_solicitud=solicitud.id_solicitud,
        version=1,
        vigente=True,
        origen_evaluacion="motor_sumoto",
        score=score,
        valor_ingreso=ingreso,
        ingreso_final=ingreso_final,
        endeudamiento=round(endeudamiento, 2),
        capacidad_pago=capacidad,
        calificacion=(
            "D"
            if perfil_score == "D" or "R10" in codigos
            else RNG.choice(["A", "B"])
        ),
        perfil_score=perfil_score,
        perfil_ingreso=perfil_ingreso,
        decision_interna=(
            "Rechazado" if es_rechazo else ("Estudio" if estado == "en_revision" else "Aprobado")
        ),
        **buro,
    )
    db.add(evaluacion)
    db.flush()

    db.add(
        CapacidadPago(
            id_solicitud=solicitud.id_solicitud,
            version=1,
            vigente=True,
            salario_minimo=SMMLV,
            ingreso_final=ingreso_final,
            ingreso_final_smlmv=round(ingreso_final / SMMLV, 4),
            gastos_personales=round(ingreso_final * RNG.uniform(0.35, 0.6), 2),
            disponible_1=capacidad,
            capacidad_pago_2=capacidad,
            tasa_cupo=TASA_PRODUCTO,
            plazo_cupo=plazo,
            cupo_calculado=monto_aprobado if not es_rechazo else None,
            cupo_aprobado=monto_aprobado if not es_rechazo else None,
        )
    )

    if decision == "aprobado" and producto is not None:
        cuota = _cuota_anualidad(monto_aprobado, TASA_PRODUCTO, plazo)
        db.add(
            OfertaCredito(
                id_solicitud=solicitud.id_solicitud,
                id_aliado_producto=producto.id_aliado_producto,
                elegible=True,
                tasa_ofrecida=TASA_PRODUCTO,
                plazo_ofrecido=plazo,
                cuota_mensual=round(cuota, 2),
                monto_aprobado=monto_aprobado,
                seleccionada=True,
                fecha_vigencia=fecha + timedelta(days=15),
            )
        )

    if es_rechazo:
        descripciones = []
        for codigo in codigos:
            criterio = next((c for c in catalogo_causales if c.codigo == codigo), None)
            descripcion = criterio.descripcion if criterio else codigo
            descripciones.append(descripcion)
            db.add(
                SolicitudCausal(
                    id_solicitud=solicitud.id_solicitud,
                    id_criterio=criterio.id_criterio if criterio else None,
                    codigo=codigo,
                    descripcion=descripcion,
                    activa=True,
                )
            )
        solicitud.descripcion_estado = "; ".join(descripciones)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--total",
        type=int,
        default=75,
        help="Total de solicitudes objetivo en la tabla (defecto 75)",
    )
    parser.add_argument(
        "--sqlite",
        metavar="RUTA.db",
        help="Usar un archivo SQLite en vez del DATABASE_URL del entorno",
    )
    args = parser.parse_args()

    url = (
        f"sqlite:///{args.sqlite}"
        if args.sqlite
        else get_settings().sqlalchemy_database_url()
    )
    engine = create_engine(url, pool_pre_ping=True)
    ahora = datetime.now(timezone.utc)

    with Session(engine) as db:
        asesores_por_sede = _asegurar_asesores(db)
        catalogo_causales = list(db.scalars(select(CriterioEvaluacion)))
        producto = db.scalar(select(AliadoProducto).limit(1))

        actuales = db.scalar(select(func.count()).select_from(SolicitudCredito)) or 0
        faltan = max(0, args.total - actuales)
        if faltan == 0:
            print(f"Ya hay {actuales} solicitudes (>= {args.total}); nada que sembrar.")
            return
        cedulas = _cedulas_libres(db, faltan)
        plan = _plan_estados(faltan)

        # Reparto de causales: todos los códigos del catálogo aparecen
        # al menos una vez entre las rechazadas; cada rechazada lleva 1+
        # causales (round-robin sobre la lista barajada).
        rechazadas = [i for i, p in enumerate(plan) if p[1] == "rechazado"]
        codigos = [c.codigo for c in catalogo_causales]
        RNG.shuffle(codigos)
        base, extra = divmod(len(codigos), max(1, len(rechazadas)))
        causales_por_idx: dict[int, list[str]] = {}
        cursor = 0
        for pos, idx in enumerate(rechazadas):
            k = base + (1 if pos < extra else 0)
            causales_por_idx[idx] = codigos[cursor : cursor + k] or codigos[:1]
            cursor += k

        # Algunas radicadas hoy: primeras 3 del plan, para el KPI del día.
        hoy_idx = set(range(min(3, faltan)))

        for i, (cedula, fila) in enumerate(zip(cedulas, plan)):
            _solicitud_demo(
                db,
                cedula,
                fila,
                ahora - timedelta(minutes=RNG.randint(10, 600)),
                asesores_por_sede,
                catalogo_causales,
                causales_por_idx.get(i, []),
                producto,
                hoy=i in hoy_idx,
            )
        db.commit()

        total = db.scalar(select(func.count()).select_from(SolicitudCredito))
        print(
            f"Sembradas {faltan} solicitudes -> total {total}. "
            f"Asesores por sede: "
            + ", ".join(
                f"{sede}: {len(lista)}" for sede, lista in sorted(asesores_por_sede.items())
            )
        )


if __name__ == "__main__":
    main()
    sys.exit(0)
