import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  BadgeCheck,
  Check,
  MailCheck,
  MessageCircle,
  X,
  XCircle,
} from 'lucide-react'
import { currency } from '../../../shared/lib/formatters'
import { cuotaAnualidad } from '../../../shared/lib/finanzas'
import {
  CREDICONTADO_PLAZO_MAX,
  CREDICONTADO_PLAZO_MIN,
  tramoCredicontado,
} from '../../../shared/lib/credicontado'
import { useCuentaAscendente } from '../../../shared/lib/useCuentaAscendente'
import {
  marcaDeConcesionario,
  obtenerConcesionario,
  useRol,
} from '../../../shared/lib/sesion'
import { emitirToast } from '../../../shared/lib/toastBus'
import { MODO_DEMO } from '../../../env'
import Alerta from '../../../shared/ui/Alerta'
import CampoNumerico from '../../../shared/ui/CampoNumerico'
import ConfettiCelebracion from '../../../shared/ui/ConfettiCelebracion'
import type { ResultadoEvaluacionCredito } from '../model/resultado-evaluacion'
import {
  GASTOS_ADMINISTRATIVOS,
  PRIMA_SEGURO_VIDA_PCT,
} from '../model/resultado-evaluacion'
import type { SimulacionPrevia } from '../model/borrador'
import { MARCAS_VEHICULO, REFERENCIAS_VEHICULO } from '../model/concesionarios'
import {
  generarOtp,
  guardarDatosFormalizacion,
  obtenerOfertas,
  obtenerSolicitud,
  seleccionarOferta,
  verificarOtp,
  type DatosFormalizacionPayload,
  type OfertaApi,
} from '../api/originacionApi'
import DatosClienteFormalizacion from './DatosClienteFormalizacion'
import SelectorMarca from './SelectorMarca'
import { datosFormDesdeApi, type DatosForm } from '../model/datos-formalizacion'
import type { DatosSolicitud } from './CrearSolicitud'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import CabeceraEtapaOriginacion from './CabeceraEtapaOriginacion'
import './CabeceraEtapaOriginacion.css'
import './ResultadoCredito.css'
import { MARCA } from '../../../shared/lib/marca'

export interface OfertaSeleccionada {
  monto: number
  plazoMeses: number
  cuotaMensual: number
  desembolsoEstimado: number
  /** Presente cuando la oferta quedó confirmada en el backend. */
  idOferta?: number
}

interface ResultadoCreditoProps {
  resultado: ResultadoEvaluacionCredito
  /** ID de la solicitud persistida (habilita ofertas y selección reales). */
  idSolicitud?: string
  formalizacionIniciada: boolean
  onModificar: () => void
  onFormalizar: (oferta: OfertaSeleccionada) => void
  /** Cierra el proceso tras un rechazo: el veredicto ya quedó persistido. */
  onFinalizar?: () => void
  /** Simulación de origen: precarga valor de la moto y plazo. */
  simulacion?: SimulacionPrevia
  /** Datos del paso 4: la ocupación adapta la sección laboral y la empresa
   * precarga el formulario de formalización. */
  solicitud?: DatosSolicitud
  /** Si es true, no renderiza cabecera ni seguimiento (para usar dentro de otro paso). */
  compacto?: boolean
}

function ResultadoCredito({
  resultado,
  idSolicitud,
  formalizacionIniciada,
  onModificar,
  onFormalizar,
  onFinalizar,
  simulacion,
  solicitud,
  compacto = false,
}: ResultadoCreditoProps) {
  const aprobado = resultado.decision === 'APROBADO'
  const rechazado = resultado.decision === 'RECHAZADO'
  const esCredicontado = solicitud?.lineaCredito === 'Credicontado'
  // Las causales de la decisión son dato sensible: solo el administrador.
  const vistaBinaria = useRol() !== 'admin'

  const [ofertas, setOfertas] = useState<OfertaApi[]>([])
  const [errorOfertas, setErrorOfertas] = useState<string | null>(null)
  const [confirmando, setConfirmando] = useState(false)

  // Firma del pagaré: vehículo → datos del cliente → OTP al WhatsApp
  // (cae a correo si el envío falla); la verificación firma la
  // solicitud (uuid_firma) y genera el paquete legal.
  const [pasoFirma, setPasoFirma] = useState<'vehiculo' | 'datos' | 'otp'>(
    'vehiculo',
  )
  const [otpCanal, setOtpCanal] = useState<'whatsapp' | 'email'>('whatsapp')
  const [otpDestino, setOtpDestino] = useState<string | null>(null)
  const [otpDemo, setOtpDemo] = useState<string | null>(null)
  const [otpCodigo, setOtpCodigo] = useState('')
  const [enviandoOtp, setEnviandoOtp] = useState(false)
  const [errorOtp, setErrorOtp] = useState<string | null>(null)
  const [errorDatos, setErrorDatos] = useState<string | null>(null)

  // Precarga del formulario de datos del cliente: lo ya capturado en el
  // paso 4 (empresa/entidad pagadora) más lo ya persistido (retomar).
  const [inicialDatos, setInicialDatos] = useState<Partial<DatosForm> | null>(
    null,
  )
  const [direccionRegistrada, setDireccionRegistrada] = useState<string | null>(
    null,
  )
  const [cargandoDatos, setCargandoDatos] = useState(false)
  const [datosCargados, setDatosCargados] = useState(false)
  // El héroe de aprobación celebra un momento, se colapsa a una tira
  // compacta y de ahí puede ocultarse del todo: queda un chip mínimo
  // para reabrirlo si el asesor quiere verlo otra vez.
  const [heroeEstado, setHeroeEstado] = useState<
    'expandido' | 'tira' | 'oculto'
  >('expandido')

  useEffect(() => {
    if (!aprobado || formalizacionIniciada) return
    const t = window.setTimeout(
      () => setHeroeEstado((e) => (e === 'expandido' ? 'tira' : e)),
      6500,
    )
    return () => window.clearTimeout(t)
  }, [aprobado, formalizacionIniciada])

  useEffect(() => {
    if (pasoFirma !== 'vehiculo') {
      setHeroeEstado((e) => (e === 'expandido' ? 'tira' : e))
    }
  }, [pasoFirma])

  // Celebración sonora: suena completa al mostrar el cupo aprobado; si
  // el navegador bloquea el autoplay sin gesto previo queda en silencio.
  useEffect(() => {
    if (!aprobado || formalizacionIniciada) return
    const audio = new Audio('/audio/aprobado.mp4')
    audio.play().catch(() => undefined)
    return () => audio.pause()
  }, [aprobado, formalizacionIniciada])

  useEffect(() => {
    if (pasoFirma !== 'datos' || datosCargados) return
    const empresa = (
      solicitud?.empresa ||
      solicitud?.entidadPagadora ||
      ''
    ).trim()
    const fallback: Partial<DatosForm> = empresa
      ? { nombreEmpresa: empresa }
      : {}
    if (!idSolicitud) {
      setInicialDatos(fallback)
      setDatosCargados(true)
      return
    }
    setCargandoDatos(true)
    obtenerSolicitud(idSolicitud)
      .then((detalle) => {
        setInicialDatos({
          ...fallback,
          ...datosFormDesdeApi(
            detalle.contacto_vivienda,
            detalle.datos_laborales,
          ),
        })
        setDireccionRegistrada(detalle.contacto_vivienda?.direccion ?? null)
      })
      .catch(() => setInicialDatos(fallback))
      .finally(() => {
        setCargandoDatos(false)
        setDatosCargados(true)
      })
  }, [pasoFirma, datosCargados, idSolicitud, solicitud])

  useEffect(() => {
    if (!aprobado || !idSolicitud) return
    obtenerOfertas(idSolicitud)
      .then(setOfertas)
      .catch(() =>
        setErrorOfertas(
          'No fue posible cargar las ofertas del backend; se muestra la estimación local.',
        ),
      )
  }, [aprobado, idSolicitud])

  const ofertaElegible = ofertas.find((o) => o.elegible)

  const cupoMaximo = ofertaElegible?.monto_aprobado
    ? Number(ofertaElegible.monto_aprobado)
    : resultado.montoSugerido
  const tasaOferta = ofertaElegible?.tasa_ofrecida
    ? Number(ofertaElegible.tasa_ofrecida)
    : resultado.tasaMensual
  // Credicontado financia a tasa cero (N/A en la tabla): el negocio
  // cobra cuota inicial más fondo de garantía en vez de intereses.
  const tasaEfectiva = esCredicontado ? 0 : tasaOferta

  // Si el asesor llegó desde el simulador, el plazo simulado es la
  // intención del cliente y prima sobre el del resultado/oferta.
  const [plazo, setPlazo] = useState(
    simulacion?.plazoMeses ?? resultado.plazoMeses,
  )

  // Datos del vehículo a financiar (formalización). La marca se sugiere
  // según el concesionario del asesor de la cuenta; si el nombre no deja
  // inferir una marca financiable, el asesor la elige.
  const marcaSugerida = (nombre: string) => {
    const inferida = marcaDeConcesionario(nombre)
    return MARCAS_VEHICULO.includes(inferida) ? inferida : ''
  }
  const [concesionario] = useState(obtenerConcesionario)
  const [marca, setMarca] = useState(() =>
    marcaSugerida(obtenerConcesionario()),
  )
  const [referencia, setReferencia] = useState('')
  const [modelo, setModelo] = useState<number | null>(null)
  const [color, setColor] = useState('')
  const [valorMoto, setValorMoto] = useState<number | null>(
    simulacion?.valorMoto ?? null,
  )
  // El descuento es uno solo: en pesos O en porcentaje, nunca los dos.
  const [tipoDescuento, setTipoDescuento] = useState<'valor' | 'porcentaje'>(
    'valor',
  )
  const [descuento, setDescuento] = useState<number | null>(0)
  const [descuentoPct, setDescuentoPct] = useState<number | null>(0)
  const [accesorios, setAccesorios] = useState<number | null>(0)
  const [matricula, setMatricula] = useState<number | null>(0)
  const [soat, setSoat] = useState<number | null>(0)
  const [impuestos, setImpuestos] = useState<number | null>(0)
  const [avalPct, setAvalPct] = useState<number | null>(0)
  // Fee de originación fijo ($200.000): no lo edita el asesor, pero sí
  // entra al saldo y se muestra al cliente en el panel de la moto.
  const gastosAdmin = GASTOS_ADMINISTRATIVOS

  // Saldo a financiar = valor neto de la moto tras descuentos, más los
  // adicionales financiados (accesorios, matrícula, SOAT, impuestos),
  // el aval y los gastos administrativos de originación.
  const descuentoAplicado =
    tipoDescuento === 'valor'
      ? (descuento ?? 0)
      : ((valorMoto ?? 0) * (descuentoPct ?? 0)) / 100
  const valorNeto = Math.max(0, (valorMoto ?? 0) - descuentoAplicado)
  const avalValor = (valorNeto * (avalPct ?? 0)) / 100
  const saldoBase =
    valorNeto +
    (accesorios ?? 0) +
    (matricula ?? 0) +
    (soat ?? 0) +
    (impuestos ?? 0) +
    avalValor +
    (gastosAdmin ?? 0)
  // Credicontado: el cliente paga la cuota inicial de contado y solo se
  // financia el resto; el fondo de garantía se reporta sobre el saldo.
  const tramo = esCredicontado ? tramoCredicontado(plazo) : null
  const cuotaInicialValor = tramo
    ? Math.round(saldoBase * tramo.cuotaInicial)
    : 0
  const saldoFinanciar = Math.round(saldoBase - cuotaInicialValor)
  const fondoGarantiaValor = tramo
    ? Math.round(saldoFinanciar * tramo.fondo)
    : 0
  const saldoInvalido = saldoFinanciar <= 0
  const superaCupo = cupoMaximo > 0 && saldoFinanciar > cupoMaximo

  // El plazo que el cliente puede tomar nunca supera al ofertado: el
  // motor evaluó ese término (capacidad.plazo_cupo) y el backend lo
  // rechaza con 422. Si el simulador traía más, se topa aquí.
  useEffect(() => {
    if (ofertaElegible?.plazo_ofrecido) {
      setPlazo((p) =>
        p
          ? Math.min(p, ofertaElegible.plazo_ofrecido!)
          : ofertaElegible.plazo_ofrecido!,
      )
    }
  }, [ofertaElegible?.plazo_ofrecido])

  // Credicontado solo financia a 4–12 meses: el plazo heredado de la
  // evaluación o del simulador (que llega hasta 48) se topa al rango.
  useEffect(() => {
    if (esCredicontado) {
      setPlazo((p) =>
        Math.min(
          CREDICONTADO_PLAZO_MAX,
          Math.max(CREDICONTADO_PLAZO_MIN, p || CREDICONTADO_PLAZO_MIN),
        ),
      )
    }
  }, [esCredicontado])

  // El máximo de plazo no es un rango comercial quemado: es el plazo
  // que el motor evaluó y la oferta fijó (el cliente solo puede bajar).
  // En Credicontado lo impone la tabla: 4–12 meses.
  const plazoMinimo = esCredicontado ? CREDICONTADO_PLAZO_MIN : 12
  const plazoMaximo = esCredicontado
    ? CREDICONTADO_PLAZO_MAX
    : (ofertaElegible?.plazo_ofrecido ?? 48)
  const plazoInvalido = plazo < plazoMinimo || plazo > plazoMaximo
  const cuotaMensual = useMemo(
    // La cuota del pagaré/carta es la total: anualidad + prima de
    // seguro de vida (% mensual sobre el saldo financiado).
    () =>
      plazoInvalido || saldoInvalido
        ? 0
        : Math.round(
            cuotaAnualidad(saldoFinanciar, tasaEfectiva, plazo) +
              (saldoFinanciar * PRIMA_SEGURO_VIDA_PCT) / 100,
          ),
    [saldoFinanciar, plazo, tasaEfectiva, plazoInvalido, saldoInvalido],
  )
  // El concesionario recibe el saldo menos el fee de originación, que
  // queda en la financiera.
  const desembolsoEstimado = Math.max(0, saldoFinanciar - (gastosAdmin ?? 0))

  // Desglose de la cuota para el panel de la moto — la misma
  // organización del simulador: anualidad + seguro de vida.
  const calculosValidos = !saldoInvalido && !plazoInvalido
  const cuotaFinanciacion = calculosValidos
    ? cuotaAnualidad(saldoFinanciar, tasaEfectiva, plazo)
    : 0
  const primaVida = saldoInvalido
    ? 0
    : (saldoFinanciar * PRIMA_SEGURO_VIDA_PCT) / 100
  // El cupo aprobado cuenta de 0 → valor para dar emoción al resultado.
  const cupoAnim = useCuentaAscendente(aprobado ? cupoMaximo : 0)

  // Congela los términos elegidos en la oferta: debe correr ANTES del
  // OTP, porque al verificar el código el backend sella la firma y
  // genera el paquete legal con la oferta seleccionada.
  const confirmarOferta = (): Promise<OfertaSeleccionada> => {
    const oferta: OfertaSeleccionada = {
      monto: saldoFinanciar,
      plazoMeses: plazo,
      cuotaMensual,
      desembolsoEstimado,
      idOferta: ofertaElegible!.id_oferta,
    }
    return seleccionarOferta(
      idSolicitud!,
      ofertaElegible!.id_oferta,
      saldoFinanciar,
      plazo,
      {
        marca: marca || null,
        referencia: referencia.trim() || null,
        modelo: modelo != null ? String(modelo) : null,
        color: color.trim() || null,
        valor_moto_iva: valorMoto,
        descuento: tipoDescuento === 'valor' ? descuento : null,
        descuento_pct: tipoDescuento === 'porcentaje' ? descuentoPct : null,
        accesorios,
        matricula,
        soat,
        impuestos,
        aval_pct: avalPct,
        gastos_administrativos: gastosAdmin,
      },
    ).then(() => oferta)
  }

  // Firma del pagaré con OTP: se envía el código al correo del cliente
  // y solo tras verificarlo se confirma la oferta. Sin solicitud
  // persistida (modo demo) se formaliza directo.
  const iniciarFirma = () => {
    if (plazoInvalido || saldoInvalido || superaCupo) return
    if (ofertaElegible?.expirada) {
      setErrorOfertas(
        'La oferta expiró; cierra esta pantalla y genera una nueva evaluación.',
      )
      return
    }
    if (!idSolicitud || !ofertaElegible) {
      onFormalizar({
        monto: saldoFinanciar,
        plazoMeses: plazo,
        cuotaMensual,
        desembolsoEstimado,
      })
      return
    }
    setErrorOtp(null)
    setEnviandoOtp(true)
    generarOtp(idSolicitud)
      .then((resp) => {
        setOtpCanal(resp.canal)
        setOtpDestino(resp.destino)
        setOtpDemo(resp.codigo_demo)
        setOtpCodigo('')
        setPasoFirma('otp')
      })
      .catch(() =>
        setErrorOtp('No se pudo enviar el código; intenta de nuevo.'),
      )
      .finally(() => setEnviandoOtp(false))
  }

  // Datos del cliente: se capturan tras el vehículo y antes del OTP; se
  // persisten en la solicitud para que los documentos de legalización los
  // incluyan al regenerarse tras la firma.
  const continuarConDatos = (datos: DatosFormalizacionPayload) => {
    if (!idSolicitud) {
      iniciarFirma()
      return
    }
    setErrorDatos(null)
    setConfirmando(true)
    guardarDatosFormalizacion(idSolicitud, datos)
      .then(() => iniciarFirma())
      .catch(() =>
        setErrorDatos(
          'No se pudieron guardar los datos del cliente; intenta de nuevo.',
        ),
      )
      .finally(() => setConfirmando(false))
  }

  const verificarFirma = () => {
    if (!idSolicitud || !ofertaElegible || otpCodigo.length !== 6) return
    setErrorOtp(null)
    setConfirmando(true)
    // Orden: seleccionar la oferta (congela monto/plazo/vehículo) y
    // recién entonces verificar el OTP: la firma y el paquete legal se
    // generan sobre los términos finales, y si la selección falla el
    // código sigue vigente para reintentar tras corregir.
    confirmarOferta()
      .then((oferta) =>
        verificarOtp(idSolicitud, otpCodigo).then(() => {
          emitirToast({
            tipo: 'exito',
            titulo: 'Pagaré firmado',
            mensaje: 'La oferta y el vehículo quedaron formalizados.',
          })
          onFormalizar(oferta)
        }),
      )
      .catch((error: unknown) => {
        setConfirmando(false)
        setErrorOtp(
          error instanceof Error
            ? error.message
            : 'El código no es válido; intenta de nuevo.',
        )
      })
  }

  const titulo = aprobado ? 'Oferta de crédito generada' : 'Solicitud rechazada'
  const descripcion = aprobado
    ? 'Confirma los datos del vehículo y la financiación para continuar.'
    : 'La solicitud no cumple las políticas de crédito vigentes.'

  return (
    <div className="resultado-credito">
      {!compacto && (
        <>
          <CabeceraEtapaOriginacion
            paso={5}
            titulo={titulo}
            descripcion={descripcion}
          />
          <SeguimientoOriginacion pasoActual={5} />
        </>
      )}

      {/* Con la formalización ya iniciada el aviso verde de abajo cubre el
          estado: ni héroe ni tira para no duplicar banners. */}
      {!(aprobado && formalizacionIniciada) &&
        (aprobado && heroeEstado === 'oculto' ? (
          <button
            type="button"
            className="resultado-credito__chip"
            aria-expanded="false"
            title="Mostrar el resultado de la aprobación"
            onClick={() => setHeroeEstado('expandido')}
          >
            <BadgeCheck size={14} aria-hidden="true" />
            Crédito Aprobado
          </button>
        ) : aprobado && heroeEstado === 'tira' ? (
          <div className="resultado-credito__resumen" role="status">
            <ConfettiCelebracion />
            <BadgeCheck size={18} aria-hidden="true" />
            <span className="resultado-credito__resumen-texto">
              <strong>Crédito Aprobado</strong>
              <span>
                {MARCA.nombre} · Cupo {currency(cupoMaximo)}
                {idSolicitud
                  ? ` · Solicitud ${idSolicitud.slice(0, 8).toUpperCase()}`
                  : ' · Demostración'}
              </span>
            </span>
            <button
              type="button"
              className="resultado-credito__resumen-ver"
              aria-expanded="false"
              onClick={() => setHeroeEstado('expandido')}
            >
              Ver resultado
            </button>
            <button
              type="button"
              className="resultado-credito__resumen-cerrar"
              aria-label="Ocultar el aviso de aprobación"
              onClick={() => setHeroeEstado('oculto')}
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div
            className={`resultado-credito__veredicto resultado-credito__veredicto--${
              aprobado ? 'aprobado' : 'rechazado'
            }`}
            role="status"
          >
            {aprobado && <ConfettiCelebracion />}
            <span
              className="resultado-credito__veredicto-icono"
              aria-hidden="true"
            >
              {aprobado ? (
                <BadgeCheck size={42} strokeWidth={1.8} />
              ) : (
                <XCircle size={42} strokeWidth={1.8} />
              )}
            </span>
            <span className="resultado-credito__veredicto-eyebrow">
              {aprobado ? '¡Buenas noticias!' : 'Resultado de la evaluación'}
            </span>
            <strong className="resultado-credito__veredicto-titulo">
              {aprobado ? '¡Crédito Aprobado!' : 'Crédito no Aprobado'}
            </strong>
            {aprobado ? (
              <span className="resultado-credito__veredicto-cupo">
                <small>Cupo aprobado hasta</small>
                <b>{currency(Math.round(cupoAnim))}</b>
              </span>
            ) : (
              <p className="resultado-credito__veredicto-sub">
                Puedes solicitar análisis individual a crédito si consideras que
                el cliente tiene una novedad especial.
              </p>
            )}
            <small className="resultado-credito__veredicto-radicado">
              {idSolicitud
                ? `Solicitud ${idSolicitud.slice(0, 8).toUpperCase()}`
                : 'Evaluación de demostración'}
            </small>
          </div>
        ))}

      {formalizacionIniciada && (
        <Alerta variante="exito">
          Formalización iniciada. Las condiciones quedan listas para validación
          documental y firma.
          {idSolicitud && (
            <>
              {' '}
              El siguiente paso es la firma del pagaré en el detalle de la
              solicitud:{' '}
              <Link to={`/solicitudes/${idSolicitud}`}>Ir a formalización</Link>
              .
            </>
          )}
        </Alerta>
      )}

      {errorOfertas && <Alerta variante="advertencia">{errorOfertas}</Alerta>}

      {aprobado ? (
        <div className="resultado-credito__contenido">
          <section className="resultado-credito__oferta">
            <header className="resultado-credito__oferta-head">
              <h2>Información de crédito</h2>
              {solicitud?.lineaCredito === 'Credicontado' && (
                <img
                  src="/brand/credicontado.png"
                  alt="Credicontado"
                  className="resultado-credito__linea-logo"
                />
              )}
            </header>

            <div className="resultado-credito__seleccion">
              <div className="resultado-credito__seleccion-head">
                <strong>
                  {pasoFirma === 'otp'
                    ? 'Firma del pagaré'
                    : pasoFirma === 'datos'
                      ? 'Datos del cliente'
                      : 'Detalles de la financiación'}
                </strong>
              </div>
              {pasoFirma === 'vehiculo' && simulacion && (
                <p className="resultado-credito__inclusion">
                  Precargado desde el simulador: moto{' '}
                  {currency(simulacion.valorMoto)}, adicionales{' '}
                  {currency(simulacion.adicionales)} (repartirlos entre
                  accesorios, matrícula, SOAT e impuestos) y cuota estimada{' '}
                  {currency(simulacion.cuotaMensual)} a {simulacion.plazoMeses}{' '}
                  meses.
                </p>
              )}
              {pasoFirma === 'otp' ? (
                <div className="resultado-credito__otp">
                  {otpCanal === 'whatsapp' ? (
                    <MessageCircle
                      size={30}
                      strokeWidth={1.6}
                      aria-hidden="true"
                      className="resultado-credito__otp-icono"
                    />
                  ) : (
                    <MailCheck
                      size={30}
                      strokeWidth={1.6}
                      aria-hidden="true"
                      className="resultado-credito__otp-icono"
                    />
                  )}
                  <p className="resultado-credito__otp-texto">
                    Enviamos un código de verificación
                    {otpDestino ? (
                      <>
                        {' '}
                        {otpCanal === 'whatsapp'
                          ? 'al WhatsApp '
                          : 'al correo '}
                        <strong>{otpDestino}</strong> del cliente
                      </>
                    ) : otpCanal === 'whatsapp' ? (
                      ' al WhatsApp del cliente'
                    ) : (
                      ' al correo del cliente'
                    )}
                    . Digítalo para firmar el pagaré y formalizar la solicitud.
                  </p>
                  {MODO_DEMO && otpDemo && (
                    <p className="resultado-credito__otp-demo" role="note">
                      Demo — código: <strong>{otpDemo}</strong>
                    </p>
                  )}
                  <label
                    className="resultado-credito__otp-campo"
                    htmlFor="otp-codigo"
                  >
                    Código de verificación
                    <input
                      id="otp-codigo"
                      className="input-base"
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      maxLength={6}
                      placeholder="000000"
                      value={otpCodigo}
                      aria-invalid={Boolean(errorOtp)}
                      onChange={(e) =>
                        setOtpCodigo(
                          e.target.value.replace(/\D/g, '').slice(0, 6),
                        )
                      }
                    />
                  </label>
                  {errorOtp && (
                    <p className="resultado-credito__plazo-error" role="alert">
                      {errorOtp}
                    </p>
                  )}
                  <div className="resultado-credito__otp-acciones">
                    <button
                      type="button"
                      className="resultado-credito__secundario"
                      onClick={() => setPasoFirma('datos')}
                      disabled={confirmando}
                    >
                      Volver a los datos
                    </button>
                    <button
                      type="button"
                      className="resultado-credito__secundario"
                      onClick={iniciarFirma}
                      disabled={enviandoOtp || confirmando}
                    >
                      {enviandoOtp ? 'Enviando…' : 'Reenviar código'}
                    </button>
                    <button
                      type="button"
                      className="resultado-credito__primario"
                      onClick={verificarFirma}
                      disabled={
                        otpCodigo.length !== 6 || confirmando || enviandoOtp
                      }
                    >
                      {confirmando ? 'Firmando…' : 'Firmar y formalizar'}
                    </button>
                  </div>
                </div>
              ) : pasoFirma === 'datos' ? (
                cargandoDatos || !inicialDatos ? (
                  <p className="datos-cliente__cargando">
                    Cargando datos guardados…
                  </p>
                ) : (
                  <DatosClienteFormalizacion
                    deshabilitado={
                      formalizacionIniciada || confirmando || enviandoOtp
                    }
                    error={errorDatos ?? errorOtp}
                    enviando={confirmando || enviandoOtp}
                    ocupacion={solicitud?.ocupacion}
                    direccionRegistrada={direccionRegistrada}
                    inicial={inicialDatos}
                    onVolver={() => setPasoFirma('vehiculo')}
                    onContinuar={continuarConDatos}
                  />
                )
              ) : (
                <div className="resultado-credito__grid">
                  <label>
                    Marca
                    <SelectorMarca
                      value={marca}
                      disabled={formalizacionIniciada || confirmando}
                      onChange={setMarca}
                    />
                  </label>
                  <label>
                    Referencia
                    <input
                      className="input-base"
                      value={referencia}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="PULSAR NS 160FI UG"
                      list="rc-referencias"
                      onChange={(e) => setReferencia(e.target.value)}
                    />
                    <datalist id="rc-referencias">
                      {(REFERENCIAS_VEHICULO[marca] ?? []).map((r) => (
                        <option key={r} value={r} />
                      ))}
                    </datalist>
                  </label>
                  <label>
                    Modelo (año)
                    <CampoNumerico
                      className="input-base"
                      value={modelo}
                      minimo={1990}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder={String(new Date().getFullYear())}
                      onValor={(n) => setModelo(n)}
                    />
                  </label>
                  <label>
                    Color
                    <input
                      className="input-base"
                      value={color}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="NEGRO CRISTAL ONIX"
                      onChange={(e) => setColor(e.target.value)}
                    />
                  </label>
                  <label>
                    Valor moto + IVA
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={valorMoto}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="6.899.000"
                      onValor={(n) => setValorMoto(n)}
                    />
                  </label>
                  <div className="resultado-credito__descuento">
                    <span>
                      Descuento
                      <span
                        className="resultado-credito__toggle"
                        role="group"
                        aria-label="Tipo de descuento"
                      >
                        <button
                          type="button"
                          className={
                            tipoDescuento === 'valor'
                              ? 'resultado-credito__toggle-op resultado-credito__toggle-op--activo'
                              : 'resultado-credito__toggle-op'
                          }
                          disabled={formalizacionIniciada || confirmando}
                          onClick={() => setTipoDescuento('valor')}
                        >
                          $
                        </button>
                        <button
                          type="button"
                          className={
                            tipoDescuento === 'porcentaje'
                              ? 'resultado-credito__toggle-op resultado-credito__toggle-op--activo'
                              : 'resultado-credito__toggle-op'
                          }
                          disabled={formalizacionIniciada || confirmando}
                          onClick={() => setTipoDescuento('porcentaje')}
                        >
                          %
                        </button>
                      </span>
                    </span>
                    {tipoDescuento === 'valor' ? (
                      <CampoNumerico
                        className="input-base"
                        formatoMiles
                        minimo={0}
                        value={descuento}
                        disabled={formalizacionIniciada || confirmando}
                        aria-label="Descuento en pesos"
                        placeholder="0"
                        onValor={(n) => setDescuento(n)}
                      />
                    ) : (
                      <CampoNumerico
                        className="input-base"
                        minimo={0}
                        maximo={100}
                        value={descuentoPct}
                        disabled={formalizacionIniciada || confirmando}
                        aria-label="Descuento en porcentaje"
                        placeholder="0"
                        onValor={(n) => setDescuentoPct(n)}
                      />
                    )}
                  </div>
                  <label>
                    Accesorios
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={accesorios}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="180.000"
                      onValor={(n) => setAccesorios(n)}
                    />
                  </label>
                  <label>
                    Matrícula
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={matricula}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="450.000"
                      onValor={(n) => setMatricula(n)}
                    />
                  </label>
                  <label>
                    SOAT
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={soat}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="368.300"
                      onValor={(n) => setSoat(n)}
                    />
                  </label>
                  <label>
                    Impuesto por cilindraje
                    <CampoNumerico
                      className="input-base"
                      formatoMiles
                      minimo={0}
                      value={impuestos}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="135.000"
                      onValor={(n) => setImpuestos(n)}
                    />
                  </label>
                  <label>
                    Aval %
                    <CampoNumerico
                      className="input-base"
                      minimo={0}
                      maximo={100}
                      value={avalPct}
                      disabled={formalizacionIniciada || confirmando}
                      placeholder="0"
                      onValor={(n) => setAvalPct(n)}
                    />
                  </label>
                  <div className="resultado-credito__plazo">
                    <label htmlFor="rc-plazo">Plazo</label>
                    <CampoNumerico
                      id="rc-plazo"
                      className="input-base"
                      value={plazo}
                      minimo={plazoMinimo}
                      maximo={plazoMaximo}
                      disabled={formalizacionIniciada || confirmando}
                      onValor={(n) => setPlazo(n ?? 0)}
                      aria-invalid={plazoInvalido}
                      aria-describedby="rc-plazo-ayuda"
                    />
                    <small id="rc-plazo-ayuda">
                      meses · {plazoMinimo}–{plazoMaximo}
                    </small>
                  </div>
                </div>
              )}
              {pasoFirma === 'vehiculo' && plazoInvalido && (
                <p className="resultado-credito__plazo-error" role="alert">
                  El plazo debe estar entre {plazoMinimo} y {plazoMaximo} meses
                  {esCredicontado
                    ? ' (rango de la línea Credicontado).'
                    : ', el término que la evaluación aprobó.'}
                </p>
              )}
              {pasoFirma === 'vehiculo' && !saldoInvalido && superaCupo && (
                <p className="resultado-credito__plazo-error" role="alert">
                  El saldo a financiar supera el cupo aprobado (
                  {currency(cupoMaximo)}); ajusta el valor o los descuentos.
                </p>
              )}
            </div>
          </section>

          <aside className="resultado-credito__vehiculo">
            <div className="resultado-credito__vehiculo-head">
              <h2>La moto del cliente</h2>
              <span className="resultado-credito__vehiculo-chips">
                {plazoInvalido ? '—' : `${plazo} meses`} ·{' '}
                {esCredicontado
                  ? 'sin interés'
                  : `${tasaOferta.toFixed(2)} % M.V.`}
              </span>
            </div>
            <div className="resultado-credito__vehiculo-hero">
              <div>
                <strong>
                  {[marca, referencia.trim()].filter(Boolean).join(' ') ||
                    'Financiamiento de vehículo'}
                </strong>
                <small>
                  {[modelo, color.trim()].filter(Boolean).join(' · ') ||
                    concesionario}
                </small>
              </div>
            </div>

            <div className="resultado-credito__vehiculo-cuota">
              <small>Cuota mensual estimada</small>
              <strong>{calculosValidos ? currency(cuotaMensual) : '—'}</strong>
              <span className="resultado-credito__vehiculo-dia">
                ≈{' '}
                {calculosValidos
                  ? currency(Math.round(cuotaMensual / 30))
                  : '—'}
                <em> por día</em>
              </span>
            </div>

            <dl className="resultado-credito__vehiculo-stats">
              <div>
                <dt>Cuota financiación</dt>
                <dd>
                  {calculosValidos
                    ? currency(Math.round(cuotaFinanciacion))
                    : '—'}
                </dd>
              </div>
              <div>
                <dt>Seguro de vida</dt>
                <dd>
                  {calculosValidos ? currency(Math.round(primaVida)) : '—'}
                </dd>
              </div>
            </dl>

            <dl className="resultado-credito__vehiculo-datos">
              <div>
                <dt>Valor moto + IVA</dt>
                <dd>{valorMoto ? currency(valorMoto) : '—'}</dd>
              </div>
              <div>
                <dt>Gastos administrativos</dt>
                <dd>{currency(gastosAdmin ?? 0)}</dd>
              </div>
              {tramo && (
                <>
                  <div>
                    <dt>
                      Cuota inicial ({Math.round(tramo.cuotaInicial * 100)}%)
                    </dt>
                    <dd>{currency(cuotaInicialValor)}</dd>
                  </div>
                  <div>
                    <dt>
                      Fondo de garantía ({Math.round(tramo.fondo * 100)}%)
                    </dt>
                    <dd>{currency(fondoGarantiaValor)}</dd>
                  </div>
                </>
              )}
              <div className="resultado-credito__vehiculo-saldo">
                <dt>Saldo a financiar</dt>
                <dd>{saldoInvalido ? '—' : currency(saldoFinanciar)}</dd>
              </div>
            </dl>

            <p className="resultado-credito__inclusion">
              La moto se entrega en {concesionario}; la entrega se agenda tras
              la formalización.
            </p>
          </aside>
        </div>
      ) : (
        <>
          {/* Las causales del rechazo son sensibles: solo administrador. */}
          {!vistaBinaria && (
            <Alerta variante="error" titulo="Detalle del motor (administrador)">
              {resultado.causales.length ? (
                <ul>
                  {resultado.causales.map((causal) => (
                    <li key={causal.codigo}>
                      <strong>{causal.codigo}</strong> — {causal.descripcion}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>El motor no reportó causales específicas.</p>
              )}
              {resultado.advertencias.length > 0 && (
                <p>
                  <small>{resultado.advertencias.join(' ')}</small>
                </p>
              )}
              <small>Auditoría: {resultado.auditoria}</small>
            </Alerta>
          )}
        </>
      )}

      <footer className="resultado-credito__acciones">
        <button
          className="resultado-credito__secundario"
          type="button"
          onClick={onModificar}
          disabled={formalizacionIniciada || confirmando || enviandoOtp}
        >
          <ArrowLeft size={15} aria-hidden="true" />
          {rechazado ? 'Reabrir solicitud' : 'Modificar oferta'}
        </button>
        {rechazado && onFinalizar && (
          <button
            className="resultado-credito__primario"
            type="button"
            onClick={onFinalizar}
          >
            Finalizar proceso
            <Check size={15} aria-hidden="true" />
          </button>
        )}
        {aprobado && pasoFirma === 'vehiculo' && (
          <button
            className="resultado-credito__primario"
            type="button"
            onClick={() => setPasoFirma('datos')}
            disabled={
              formalizacionIniciada ||
              confirmando ||
              enviandoOtp ||
              plazoInvalido ||
              saldoInvalido ||
              superaCupo
            }
          >
            {formalizacionIniciada
              ? 'Formalización iniciada'
              : 'Continuar a formalización'}
            {!formalizacionIniciada && <Check size={15} aria-hidden="true" />}
          </button>
        )}
      </footer>
    </div>
  )
}

export default ResultadoCredito
