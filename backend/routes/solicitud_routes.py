"""Solicitudes del esquema SUMOTO: alta, evaluación y ofertas."""

import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.auth.dependencies import UsuarioActual, requiere_roles, usuario_actual
from backend.config import get_settings
from backend.db_models.session import get_db
from backend.models.analitica_models import AnaliticaResponse
from backend.models.motor_models import EvaluarSolicitudRequest, ResultadoBinarioResponse, ResultadoMotorResponse
from backend.models.solicitud_models import (
    CancelarSolicitudRequest,
    ConteoSolicitudesResponse,
    CrearSolicitudRequest,
    CrearSolicitudResponse,
    DatosFormalizacionRequest,
    DesembolsoMasivoRequest,
    DesembolsoMasivoResponse,
    DesembolsoResponse,
    FacturaRegistradaResponse,
    FacturaResponse,
    GenerarOtpRequest,
    GenerarOtpResponse,
    MetricasEmbudoResponse,
    OfertaResponse,
    PrendaVehiculoRequest,
    RechazoPoliticasRequest,
    RegistrarDesembolsoRequest,
    SeleccionarOfertaRequest,
    SimitConsultaRequest,
    SimitConsultaResponse,
    SolicitudDetalleResponse,
    SolicitudResumenResponse,
    VehiculoPrendaResponse,
    VentaContadoRequest,
    VerificarOtpRequest,
    VerificarOtpResponse,
)
from backend.repositories.solicitud_repository import SolicitudRepository
from backend.routes.dependencies import (
    auditar_acceso,
    get_evaluacion_service,
    get_tasa_mercado_service,
)
from backend.services.analitica_service import AnaliticaService
from backend.services.desembolso_service import DesembolsoService
from backend.services.documento_service import DocumentoService
from backend.services.evaluacion_service import EvaluacionService
from backend.services.factura_service import FacturaService
from backend.services.motor_exceptions import (
    DataCreditoError,
    SolicitudNoEncontradaError,
    ValidacionError,
)
from backend.services.notificacion_service import NotificacionService
from backend.services.otp_service import OtpError, OtpService
from backend.services.analitica_service import AnaliticaService
from backend.services.solicitud_service import SolicitudService
from backend.services.tasa_mercado_service import TasaMercadoService

router = APIRouter(prefix="/solicitudes", tags=["solicitudes"])


def _rechazar_tasa_sobre_usura(
    payload: EvaluarSolicitudRequest, servicio: TasaMercadoService
) -> None:
    """Guarda de cumplimiento: la tasa cobrada nunca puede igualar ni
    superar la usura vigente de la modalidad (bajo monto ≤ 6 SMMLV,
    ordinario por encima). Si la fuente SFC está caída no bloquea —
    la referencia es informativa, como en el simulador."""
    try:
        tasas = servicio.tasas()
    except DataCreditoError:
        return
    modalidad = (
        tasas.bajo_monto
        if float(payload.saldo_financiar) <= tasas.umbral_bajo_monto
        else tasas.ordinario
    )
    if float(payload.tasa) >= modalidad.usura_mv:
        raise ValidacionError(
            f"La tasa {payload.tasa}% m.v. llega o supera la usura vigente "
            f"de {modalidad.modalidad.lower()} ({modalidad.usura_mv}% m.v., "
            f"{modalidad.usura_ea}% EA). Debe quedar por debajo."
        )


def _paquete_legalizacion(db: Session, id_solicitud: uuid.UUID) -> str | None:
    """Genera el paquete de documentos tras la firma OTP.

    Ya no se envía al correo aquí: la prenda aún no tiene motor/chasis
    (llegan con la factura del concesionario). El envío del paquete
    definitivo —convertido a PDF— ocurre al registrar la factura
    (`enviar_documentos_finales`).

    Best-effort: la firma quedó registrada aunque la generación falle;
    el paquete se regenera al cargar la factura. Devuelve None si el
    paquete quedó completo; el motivo del fallo si no — la respuesta del
    endpoint lo expone al asesor en lugar de dejar el paquete parcial en
    silencio.
    """
    try:
        generadas = DocumentoService(db).generar_paquete(id_solicitud)
    except Exception as exc:  # noqa: BLE001
        import logging

        # La sesión quedó con la transacción en error: rollback para que
        # el commit final de get_db (firma/OTP ya commitados, pero la
        # sesión sigue abierta) no falle.
        db.rollback()
        logging.getLogger(__name__).exception(
            "No se pudo generar el paquete de legalización de %s", id_solicitud
        )
        return (
            "La firma quedó registrada, pero el paquete de legalización "
            f"no se generó ({exc}). Se reintenta al cargar la factura."
        )
    if not generadas:
        return (
            "La firma quedó registrada, pero no se generó ningún "
            "documento de legalización. Revisa las plantillas del "
            "paquete o vuelve a intentarlo al cargar la factura."
        )
    return None


def _notificar(db: Session, id_solicitud: uuid.UUID, evento: str, datos: dict | None = None) -> None:
    """Notificación best-effort: nunca bloquea la operación principal."""
    try:
        solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
        if solicitud is not None:
            NotificacionService().notificar(evento, solicitud, datos=datos)
    except Exception:  # noqa: BLE001
        pass


@router.get("", response_model=list[SolicitudResumenResponse])
def listar(
    estado: str | None = None,
    decision: str | None = None,
    busqueda: str | None = None,
    limite: int = 50,
    offset: int = 0,
    id_concesionario: int | None = None,
    id_asesor: int | None = None,
    orden: Literal["reciente", "prioridad"] = "reciente",
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> list[SolicitudResumenResponse]:
    """`id_concesionario`/`id_asesor` son filtros del panel (admin):
    se intersectan con el alcance de la sesión — nunca lo amplían.
    `orden=prioridad` pone las pendientes de evaluación primero."""
    return SolicitudService(db).listar(
        limite=min(limite, 200),
        offset=offset,
        estado=estado,
        decision=decision,
        busqueda=busqueda,
        concesionario_ids=usuario.concesionario_ids(),
        asesor_ids=usuario.asesor_ids(),
        asesor_cedula=usuario.cedula_asesor,
        persona_desde=usuario.persona_desde_asesor,
        filtro_id_concesionario=id_concesionario,
        filtro_id_asesor=id_asesor,
        orden=orden,
        ver_detalle_interno=usuario.es_admin(),
    )


@router.get("/conteo", response_model=ConteoSolicitudesResponse)
def conteo(
    estado: str | None = None,
    decision: str | None = None,
    busqueda: str | None = None,
    id_concesionario: int | None = None,
    id_asesor: int | None = None,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> ConteoSolicitudesResponse:
    """Total bajo los mismos filtros de `listar`, sin paginación:
    alimenta la paginación server-side de las bandejas."""
    return ConteoSolicitudesResponse(
        total=SolicitudService(db).contar(
            estado=estado,
            decision=decision,
            busqueda=busqueda,
            concesionario_ids=usuario.concesionario_ids(),
            asesor_ids=usuario.asesor_ids(),
            asesor_cedula=usuario.cedula_asesor,
            persona_desde=usuario.persona_desde_asesor,
            filtro_id_concesionario=id_concesionario,
            filtro_id_asesor=id_asesor,
        )
    )


@router.post("/desembolso-masivo", response_model=DesembolsoMasivoResponse)
def desembolso_masivo(
    payload: DesembolsoMasivoRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "contabilidad")),
    db: Session = Depends(get_db),
) -> DesembolsoMasivoResponse:
    """Bandeja de operaciones: marca en bloque facturadas como
    desembolsadas una vez radicado el cargue de garantías en RUNT Pro.
    Cada ítem corre en su propio SAVEPOINT — una factura sin prenda u
    oferta falla sin revertir el lote; el giro (cuenta + referencia)
    llega después por webhook de tesorería o desde el detalle."""
    resultados = DesembolsoService(db).desembolsar_masivo(
        payload.id_solicitudes
    )
    procesadas = sum(1 for r in resultados if r["ok"])
    for r in resultados:
        auditar_acceso(
            db,
            usuario,
            "desembolso_masivo",
            f"solicitud {r['id_solicitud']}: "
            + ("desembolsada" if r["ok"] else f"falló — {r['error']}"),
            request,
        )
    db.commit()
    return DesembolsoMasivoResponse(
        procesadas=procesadas,
        fallidas=len(resultados) - procesadas,
        resultados=resultados,
    )


@router.get("/metricas/embudo", response_model=MetricasEmbudoResponse)
def metricas_embudo(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    id_concesionario: int | None = None,
    id_asesor: int | None = None,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> MetricasEmbudoResponse:
    """Conversión del embudo originación → desembolso: conteos por etapa,
    distribución por estado y desglose por aliado financiero. `desde`/
    `hasta` acotan el rango por fecha de radicación (ej: mes del filtro
    del panel); `id_concesionario`/`id_asesor` son los filtros
    dimensionales del panel (intersectados con el alcance)."""
    return SolicitudService(db).metricas_embudo(
        desde=desde,
        hasta=hasta,
        concesionario_ids=usuario.concesionario_ids(),
        asesor_ids=usuario.asesor_ids(),
        asesor_cedula=usuario.cedula_asesor,
        persona_desde=usuario.persona_desde_asesor,
        # El desglose por aliado nunca expone competidores: el usuario
        # aliado solo ve el suyo; admin y asesor ven el completo.
        aliado_ids=usuario.aliado_ids() if "aliado" in usuario.roles else None,
        filtro_id_concesionario=id_concesionario,
        filtro_id_asesor=id_asesor,
        # Las causales de rechazo son dato sensible: solo el admin
        # las ve; el resto de roles recibe la lista vacía.
        ver_causales=usuario.es_admin(),
    )


@router.get("/metricas/analitica", response_model=AnaliticaResponse)
def metricas_analitica(
    desde: date | None = None,
    hasta: date | None = None,
    usuario: UsuarioActual = Depends(requiere_roles("admin")),
    db: Session = Depends(get_db),
) -> AnaliticaResponse:
    """Efectividad y perfil por sector — insumo para campañas.

    Cruza todo el portafolio (cargue histórico + flujo normal) sin
    alcance de sede/asesor: efectividad por sede/marca/asesor,
    distribución de score e ingreso, causales de rechazo y
    segmentación por dimensiones de campaña. `desde`/`hasta` acotan
    por fecha de radicación (hasta inclusivo); sin ambos, devuelve el
    histórico completo."""
    return AnaliticaService(db).obtener(desde=desde, hasta=hasta)


@router.get("/{id_solicitud}", response_model=SolicitudDetalleResponse)
def detalle(
    id_solicitud: uuid.UUID,
    request: Request,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> SolicitudDetalleResponse:
    try:
        resultado = SolicitudService(db).detalle(
            id_solicitud,
            concesionario_ids=usuario.concesionario_ids(),
            asesor_ids=usuario.asesor_ids(),
            asesor_cedula=usuario.cedula_asesor,
            persona_desde=usuario.persona_desde_asesor,
            ver_detalle_interno=usuario.es_admin(),
        )
    except (HTTPException, SolicitudNoEncontradaError):
        auditar_acceso(
            db, usuario, "acceso_denegado",
            f"detalle solicitud {id_solicitud}", request,
        )
        db.commit()  # persiste aunque el request termine en rollback
        raise
    auditar_acceso(
        db, usuario, "acceso_solicitud",
        f"detalle solicitud {resultado.num_solicitud}", request,
    )
    return resultado


@router.post(
    "/simit",
    response_model=SimitConsultaResponse,
    response_model_exclude_none=True,
)
def consultar_simit(
    payload: SimitConsultaRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    servicio: EvaluacionService = Depends(get_evaluacion_service),
) -> SimitConsultaResponse:
    """Paso 3 de originación ("puerta SIMIT"): estado de cuenta de
    tránsito de la persona. Reemplaza la verificación manual del
    asesor en el portal — la consulta siempre es en línea (el paso es
    inherentemente una visita al portal) y reutiliza el caché por
    documento (SIMIT_CACHE_DIAS) que también escribe el precache del
    consentimiento. Si el proveedor no responde, tiene_multas=None y
    el frontend vuelve al popup manual."""
    if not payload.autorizo_habeas:
        raise ValidacionError(
            "La consulta SIMIT requiere la autorización de tratamiento de datos (Habeas Data)."
        )
    if not get_settings().simit_habilitado:
        return SimitConsultaResponse(habilitado=False)
    try:
        res = servicio.consultar_simit_en_linea(
            payload.tipo_documento, payload.num_cedula
        )
    except DataCreditoError:
        return SimitConsultaResponse(habilitado=True)
    return SimitConsultaResponse(
        habilitado=True,
        tiene_multas=not res.paz_y_salvo,
        total_deuda=res.total_deuda,
        total_items=res.total_items,
        origen=res.origen,
    )




@router.post("", response_model=CrearSolicitudResponse, status_code=status.HTTP_201_CREATED)
def crear(
    payload: CrearSolicitudRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> CrearSolicitudResponse:
    return SolicitudService(db).crear(
        payload,
        ip=request.client.host if request.client else None,
        usuario=usuario,
    )


@router.post(
    "/rechazo-politicas",
    response_model=CrearSolicitudResponse,
    status_code=status.HTTP_201_CREATED,
)
def rechazo_politicas(
    payload: RechazoPoliticasRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> CrearSolicitudResponse:
    """El asesor confirmó en originación una política clave incumplida
    (multas en SIMIT): se radica la solicitud ya rechazada (R22) con los
    datos recopilados, sin perfil económico ni consulta al buró."""
    return SolicitudService(db).rechazar_por_politicas(
        payload,
        ip=request.client.host if request.client else None,
        usuario=usuario,
    )


@router.put("/{id_solicitud}", response_model=CrearSolicitudResponse)
def actualizar(
    id_solicitud: uuid.UUID,
    payload: CrearSolicitudRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> CrearSolicitudResponse:
    """Re-diligencia la radicación al retomar pasos pendientes (Habeas
    Data, evidencias, perfil económico): upsert sobre el mismo registro,
    no duplica. 409 si la solicitud ya tiene decisión."""
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    return servicio.actualizar(
        id_solicitud, payload, ip=request.client.host if request.client else None
    )


@router.post(
    "/{id_solicitud}/evaluar",
    response_model=ResultadoMotorResponse | ResultadoBinarioResponse,
)
def evaluar(
    id_solicitud: uuid.UUID,
    payload: EvaluarSolicitudRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    servicio: EvaluacionService = Depends(get_evaluacion_service),
    tasas: TasaMercadoService = Depends(get_tasa_mercado_service),
    db: Session = Depends(get_db),
) -> ResultadoMotorResponse:
    _rechazar_tasa_sobre_usura(payload, tasas)
    SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    resultado = servicio.evaluar_solicitud_db(id_solicitud, payload)
    # El asesor recibe la decisión y la oferta; el expediente interno
    # (score, causales, buró, traza) es solo del administrador.
    respuesta = (
        ResultadoMotorResponse.desde_resultado(resultado, str(id_solicitud))
        if usuario.es_admin()
        else ResultadoBinarioResponse.desde_resultado(resultado, str(id_solicitud))
    )
    aprobado = getattr(resultado.decision, "value", resultado.decision) == "Aprobado"
    _notificar(
        db,
        id_solicitud,
        "resultado_aprobado" if aprobado else "resultado_rechazado",
        datos={
            "monto": f"{float(getattr(resultado, 'cupo_sugerido', 0) or 0):,.0f}".replace(",", ".")
        },
    )
    return respuesta


@router.get("/{id_solicitud}/ofertas", response_model=list[OfertaResponse])
def ofertas(
    id_solicitud: uuid.UUID,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> list[OfertaResponse]:
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    return servicio.ofertas(id_solicitud)


@router.post("/{id_solicitud}/ofertas/seleccionar", response_model=OfertaResponse)
def seleccionar_oferta(
    id_solicitud: uuid.UUID,
    payload: SeleccionarOfertaRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> OfertaResponse:
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    oferta = servicio.seleccionar_oferta(id_solicitud, payload)
    _notificar(
        db,
        id_solicitud,
        "oferta",
        datos={
            "monto": f"{float(oferta.monto_aprobado or 0):,.0f}".replace(",", "."),
            "plazo": oferta.plazo_ofrecido or 0,
            "cuota": f"{float(oferta.cuota_mensual or 0):,.0f}".replace(",", "."),
        },
    )
    return oferta


@router.post("/{id_solicitud}/cancelar", response_model=SolicitudResumenResponse)
def cancelar(
    id_solicitud: uuid.UUID,
    payload: CancelarSolicitudRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> SolicitudResumenResponse:
    """Anula la solicitud con motivo obligatorio. 409 si ya está
    desembolsada o cancelada; el historial lo escribe el trigger de BD."""
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    return servicio.cancelar(
        id_solicitud, payload.motivo, usuario.es_admin()
    )


@router.put("/{id_solicitud}/datos-formalizacion", status_code=status.HTTP_204_NO_CONTENT)
def datos_formalizacion(
    id_solicitud: uuid.UUID,
    payload: DatosFormalizacionRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> None:
    """Información adicional del cliente (residencia, personal, financiera
    y laboral) capturada en la formalización, antes de la firma OTP."""
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    servicio.guardar_datos_formalizacion(id_solicitud, payload)


@router.put("/{id_solicitud}/venta-contado", status_code=status.HTTP_204_NO_CONTENT)
def venta_contado(
    id_solicitud: uuid.UUID,
    payload: VentaContadoRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> None:
    """Hoja de negocio de la venta de contado: vehículo, liquidación
    (anticipo, retoma, otros gastos, ciudad de matrícula) y a quién se
    expide la factura — puede ser un tercero ('facturar a')."""
    servicio = SolicitudService(db)
    servicio.verificar_alcance(id_solicitud, usuario)
    servicio.guardar_venta_contado(id_solicitud, payload)


@router.post("/{id_solicitud}/otp", response_model=GenerarOtpResponse, status_code=status.HTTP_201_CREATED)
def generar_otp(
    id_solicitud: uuid.UUID,
    payload: GenerarOtpRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> GenerarOtpResponse:
    """Emite un OTP por el canal pedido (tabla `otp`, solo hash)."""
    SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
    if solicitud is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    settings = get_settings()
    otp, codigo = OtpService(db).generar(
        id_solicitud,
        payload.accion,
        ip=request.client.host if request.client else None,
    )
    envio = NotificacionService().notificar(
        "otp",
        solicitud,
        datos={"codigo": codigo, "minutos": settings.otp_ttl_minutos},
        canal=payload.canal,
    )
    # El canal por el que realmente salió el código queda en el OTP para
    # sellar la firma con la autenticación correcta (otp_whatsapp/email).
    otp.autenticacion = envio["canal"]
    return GenerarOtpResponse(
        id_otp=otp.id_otp,
        expira_en_segundos=settings.otp_ttl_minutos * 60,
        canal=envio["canal"],
        destino=envio["destino"],
        estado_envio=envio["estado"],
        codigo_demo=codigo if settings.environment == "demo" else None,
    )


@router.post("/{id_solicitud}/otp/verificar", response_model=VerificarOtpResponse)
def verificar_otp(
    id_solicitud: uuid.UUID,
    payload: VerificarOtpRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> VerificarOtpResponse:
    """Valida el OTP; al aprobar la acción 'firma_pagare' firma la solicitud."""
    SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    try:
        otp = OtpService(db).verificar(id_solicitud, payload.accion, payload.codigo)
    except OtpError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    uuid_firma = None
    advertencia = None
    if payload.accion == "firma_pagare":
        solicitud = SolicitudRepository(db).obtener_detalle(id_solicitud)
        if solicitud is not None:
            uuid_firma = uuid.uuid4()
            solicitud.uuid_firma = uuid_firma
            solicitud.fecha_hora_firma = datetime.now(UTC)
            # Sella con el canal por el que salió el código (otp_whatsapp
            # u otp_email, según haya resuelto el envío).
            solicitud.autenticacion = f"otp_{otp.autenticacion or 'email'}"
            # La firma OTP también sella el consentimiento Habeas Data:
            # qué texto aceptó (versión + hash) y desde dónde firmó.
            SolicitudService(db).registrar_consentimiento(
                id_solicitud,
                "otp_firma",
                ip=request.client.host if request.client else None,
            )
        # La firma se persiste ANTES de generar el paquete: si la
        # generación falla, la firma queda sellada y el paquete se
        # puede regenerar sin repetir el OTP.
        db.commit()
        advertencia = _paquete_legalizacion(db, id_solicitud)
    return VerificarOtpResponse(
        verificado=True, uuid_firma=uuid_firma, advertencia=advertencia
    )


@router.post(
    "/{id_solicitud}/factura",
    response_model=FacturaRegistradaResponse,
    status_code=status.HTTP_201_CREATED,
)
def subir_factura(
    id_solicitud: uuid.UUID,
    request: Request,
    archivo: UploadFile = File(...),
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> FacturaRegistradaResponse:
    """Factura del vehículo emitida por el concesionario (tras la firma
    del pagaré). El PDF se lee y verifica contra la solicitud: pre-llena
    la prenda (motor/chasis/VIN/color) y mueve el ciclo a 'facturada'.
    Re-subirla reemplaza el archivo vigente (antes del desembolso)."""
    try:
        SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    except (HTTPException, SolicitudNoEncontradaError):
        auditar_acceso(
            db, usuario, "acceso_denegado",
            f"carga factura solicitud {id_solicitud}", request,
        )
        db.commit()  # persiste aunque el request termine en rollback
        raise
    servicio = FacturaService(db)
    factura = servicio.registrar_factura(
        id_solicitud, archivo, cargada_por=usuario.nombre
    )
    entrega = servicio.enviar_documentos_finales(id_solicitud)
    auditar_acceso(
        db, usuario, "carga_factura",
        f"factura {archivo.filename} solicitud {id_solicitud}", request,
    )
    return FacturaRegistradaResponse(**factura, entrega_documentos=entrega)


@router.get("/{id_solicitud}/factura")
def descargar_factura(
    id_solicitud: uuid.UUID,
    request: Request,
    usuario: UsuarioActual = Depends(usuario_actual),
    db: Session = Depends(get_db),
) -> FileResponse:
    """El archivo de la factura vigente (sesión + alcance; 404 sin
    factura — no se revela ni su existencia fuera del alcance)."""
    try:
        SolicitudService(db).verificar_alcance(id_solicitud, usuario)
        ruta, mime, nombre = FacturaService(db).factura_archivo(id_solicitud)
    except (HTTPException, SolicitudNoEncontradaError):
        auditar_acceso(
            db, usuario, "acceso_denegado",
            f"factura solicitud {id_solicitud}", request,
        )
        db.commit()  # persiste aunque el request termine en rollback
        raise
    auditar_acceso(
        db, usuario, "acceso_factura",
        f"factura solicitud {id_solicitud}", request,
    )
    return FileResponse(ruta, media_type=mime, filename=nombre)


@router.patch("/{id_solicitud}/vehiculo", response_model=VehiculoPrendaResponse)
def actualizar_prenda(
    id_solicitud: uuid.UUID,
    payload: PrendaVehiculoRequest,
    request: Request,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> VehiculoPrendaResponse:
    """Confirma/corrige la identificación de la moto prendada (motor,
    chasis, VIN, color y también marca/referencia/modelo: la captura de
    originación pudo no coincidir con la factura). Solo estando
    'facturada'; regenera los documentos legales con los datos finales."""
    try:
        SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    except (HTTPException, SolicitudNoEncontradaError):
        auditar_acceso(
            db, usuario, "acceso_denegado",
            f"prenda solicitud {id_solicitud}", request,
        )
        db.commit()  # persiste aunque el request termine en rollback
        raise
    vehiculo = FacturaService(db).actualizar_prenda(id_solicitud, payload)
    auditar_acceso(
        db, usuario, "actualiza_prenda",
        f"datos prenda solicitud {id_solicitud}", request,
    )
    return VehiculoPrendaResponse(**vehiculo)


@router.post("/{id_solicitud}/desembolso", response_model=DesembolsoResponse, status_code=status.HTTP_201_CREATED)
def registrar_desembolso(
    id_solicitud: uuid.UUID,
    payload: RegistrarDesembolsoRequest,
    usuario: UsuarioActual = Depends(requiere_roles("admin", "asesor", "concesionario")),
    db: Session = Depends(get_db),
) -> DesembolsoResponse:
    """Formaliza el crédito sobre la oferta seleccionada y confirma el
    desembolso a la cuenta de ahorros del cliente. Idempotente: si el
    crédito ya tiene desembolso confirmado devuelve el existente."""
    SolicitudService(db).verificar_alcance(id_solicitud, usuario)
    desembolso = DesembolsoService(db).registrar(id_solicitud, payload)
    _notificar(db, id_solicitud, "desembolso")
    return desembolso
