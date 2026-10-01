import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './CapturaCedula.css'

export interface ResultadoBiometrico {
  sessionId: string
  score: number
  evidencia: {
    anverso: string
    reverso: string
    selfie: string
    video?: string
  }
  matchRegistraduria: boolean
  liveness: boolean
  finalizadoEn: string
}

type Modo = 'tablet' | 'handoff'
type Fase =
  'idle' | 'iniciando' | 'capturando' | 'procesando' | 'completado' | 'error'

interface CapturaCedulaProps {
  onContinue?: (resultado: ResultadoBiometrico) => void
  onBack?: () => void
  /**
   * Función que dispara el SDK del proveedor.
   * En producción apunta a la URL firmada del SDK (Incode/MetaMap/Jumio).
   * `modo` indica si la captura se hace en la tablet del asesor o en el
   * celular del cliente vía handoff (QR).
   */
  lanzarSDK?: (modo: Modo) => Promise<ResultadoBiometrico>
}

const requisitos = [
  {
    id: 'anverso',
    label: 'Anverso de la cédula',
    detail: 'Cara frontal en vivo con cámara.',
  },
  {
    id: 'reverso',
    label: 'Reverso de la cédula',
    detail: 'Cara posterior en vivo con cámara.',
  },
  {
    id: 'selfie',
    label: 'Selfie del titular',
    detail: 'Verificación 1:1 contra Registraduría Nacional.',
  },
  {
    id: 'liveness',
    label: 'Prueba de vida',
    detail: 'Confirmación de presencia física.',
  },
  {
    id: 'video',
    label: 'Video de validación',
    detail: 'Clip de 3-5 segundos como evidencia.',
  },
] as const

const QR_SESION_DEMO = 'BIOM-A8F3C2'

/**
 * Simulación del SDK. En producción reemplaza este cuerpo por la llamada
 * real al proveedor (Incode, MetaMap, Jumio, etc.).
 */
async function simularSDK(
  onProgreso: (paso: number) => void,
): Promise<ResultadoBiometrico> {
  for (let i = 0; i < requisitos.length; i++) {
    await new Promise((r) => setTimeout(r, 1100))
    onProgreso(i + 1)
  }

  return {
    sessionId: `BIOM-${Date.now().toString(36).toUpperCase()}`,
    score: 98.4,
    evidencia: {
      anverso: 'https://cdn.proveedor.com/evidencia/anverso.jpg',
      reverso: 'https://cdn.proveedor.com/evidencia/reverso.jpg',
      selfie: 'https://cdn.proveedor.com/evidencia/selfie.jpg',
      video: 'https://cdn.proveedor.com/evidencia/liveness.mp4',
    },
    matchRegistraduria: true,
    liveness: true,
    finalizadoEn: new Date().toISOString(),
  }
}

function CapturaCedula({ onContinue, onBack, lanzarSDK }: CapturaCedulaProps) {
  const [modo, setModo] = useState<Modo>('tablet')
  const [fase, setFase] = useState<Fase>('idle')
  const [progreso, setProgreso] = useState(0)
  const [pasoActual, setPasoActual] = useState(0)
  const [resultado, setResultado] = useState<ResultadoBiometrico | null>(null)
  const [error, setError] = useState<string | null>(null)
  const sdkAbortRef = useRef(false)

  useEffect(() => {
    return () => {
      sdkAbortRef.current = true
    }
  }, [])

  const bloqueado =
    fase === 'iniciando' || fase === 'capturando' || fase === 'procesando'

  const iniciar = async (modoElegido: Modo = modo) => {
    setFase('iniciando')
    setProgreso(0)
    setPasoActual(0)
    setError(null)
    setResultado(null)
    sdkAbortRef.current = false

    try {
      await new Promise((r) => setTimeout(r, 800))
      if (sdkAbortRef.current) return
      setFase('capturando')

      const onProgreso = (paso: number) => {
        if (sdkAbortRef.current) return
        setPasoActual(paso)
        setProgreso(Math.round((paso / requisitos.length) * 100))
      }

      const res = lanzarSDK
        ? await lanzarSDK(modoElegido)
        : await simularSDK(onProgreso)

      if (sdkAbortRef.current) return

      setFase('procesando')
      await new Promise((r) => setTimeout(r, 700))
      if (sdkAbortRef.current) return

      setResultado(res)
      setFase('completado')
      setProgreso(100)
    } catch (e) {
      if (sdkAbortRef.current) return
      setError(
        e instanceof Error
          ? e.message
          : 'No se pudo completar la verificación biométrica.',
      )
      setFase('error')
    }
  }

  const cancelar = () => {
    sdkAbortRef.current = true
    setFase('idle')
    setProgreso(0)
    setPasoActual(0)
    setError(null)
  }

  const cambiarModo = (nuevo: Modo) => {
    if (bloqueado) return
    setModo(nuevo)
    setFase('idle')
    setError(null)
    setResultado(null)
  }

  const handleContinuar = () => {
    if (resultado) onContinue?.(resultado)
  }

  return (
    <div className="captura">
      {/* ---------- Encabezado ---------- */}
      <header className="captura__header">
        <div className="captura__header-copy">
          <p className="captura__eyebrow">Originación Individual · Paso 3</p>
          <h1>Verificación Biométrica de Identidad</h1>
          <p className="captura__subtitle">
            Captura de Cédula y Prueba de Vida
          </p>
          <p className="captura__lede">
            Selecciona el dispositivo donde el cliente hará la captura. El
            asesor supervisa el proceso y valida la evidencia antes de
            continuar. No se requiere capturar el teléfono del solicitante.
          </p>
        </div>

        <aside
          className="captura__panel"
          aria-label="Contexto de la radicación"
        >
          <dl className="captura__meta">
            <div>
              <dt>Asesor</dt>
              <dd>Carlos Mendoza</dd>
            </div>
            <div>
              <dt>Sede</dt>
              <dd>Palmira - Centro Interno</dd>
            </div>
          </dl>
          <span className="captura__server">
            <span aria-hidden="true" />
            Servidor de Validación Activo v2.4.12-Prod (SSL)
          </span>
        </aside>
      </header>

      <SeguimientoOriginacion pasoActual={3} />

      {/* ---------- Tarjeta principal ---------- */}
      <div className="captura__form">
        <div className="captura__form-head">
          <div>
            <h2>Verificación con Proveedor Certificado</h2>
            <p>
              El proceso completo toma aproximadamente 15 segundos y no requiere
              capturar el teléfono del cliente.
            </p>
          </div>
          <span className="captura__chip">Paso 3 de 12</span>
        </div>

        {/* Selector de modo */}
        {fase === 'idle' && (
          <div
            role="tablist"
            aria-label="Dispositivo de captura"
            className="captura__modos"
          >
            <button
              type="button"
              role="tab"
              aria-selected={modo === 'tablet'}
              onClick={() => cambiarModo('tablet')}
              className={`captura__modo${modo === 'tablet' ? ' is-selected' : ''}`}
            >
              <span className="captura__modo-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <rect
                    x="5"
                    y="3"
                    width="14"
                    height="18"
                    rx="2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                  <circle cx="12" cy="18" r="1" fill="currentColor" />
                </svg>
              </span>
              <span className="captura__modo-copy">
                <span className="captura__modo-title">
                  <strong>En esta tablet</strong>
                  <span className="captura__modo-badge">Recomendado</span>
                </span>
                <small>
                  Entrega el dispositivo al cliente. La captura y la evidencia
                  quedan atadas a la sesión del asesor.
                </small>
              </span>
            </button>

            <button
              type="button"
              role="tab"
              aria-selected={modo === 'handoff'}
              onClick={() => cambiarModo('handoff')}
              className={`captura__modo${modo === 'handoff' ? ' is-selected' : ''}`}
            >
              <span className="captura__modo-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <rect
                    x="7"
                    y="2.5"
                    width="10"
                    height="19"
                    rx="2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                  />
                  <circle cx="12" cy="18" r="0.9" fill="currentColor" />
                </svg>
              </span>
              <span className="captura__modo-copy">
                <span className="captura__modo-title">
                  <strong>En su celular</strong>
                  <span className="captura__modo-badge captura__modo-badge--soft">
                    Alternativa
                  </span>
                </span>
                <small>
                  Genera un código QR. El cliente escanea con su celular y hace
                  la captura allí.
                </small>
              </span>
            </button>
          </div>
        )}

        {/* ---------- Fase idle — Modo tablet ---------- */}
        {fase === 'idle' && modo === 'tablet' && (
          <div className="captura__idle">
            <div className="captura__instrucciones" role="note">
              <h3>
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path
                    d="M12 3 3 8v8l9 5 9-5V8l-9-5Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M12 12v9M12 12l9-4M12 12 3 8"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                </svg>
                Entrega la tablet al cliente antes de iniciar
              </h3>
              <ol className="captura__instrucciones-list">
                <li>
                  <span
                    className="captura__instrucciones-num"
                    aria-hidden="true"
                  >
                    1
                  </span>
                  <span>El asesor entrega el dispositivo al solicitante.</span>
                </li>
                <li>
                  <span
                    className="captura__instrucciones-num"
                    aria-hidden="true"
                  >
                    2
                  </span>
                  <span>
                    El cliente sigue las instrucciones del módulo en pantalla.
                  </span>
                </li>
                <li>
                  <span
                    className="captura__instrucciones-num"
                    aria-hidden="true"
                  >
                    3
                  </span>
                  <span>
                    Al finalizar, el asesor recupera el dispositivo para
                    continuar.
                  </span>
                </li>
              </ol>
            </div>

            <div className="captura__capturas">
              <span className="captura__capturas-label">
                El cliente capturará
              </span>
              <ol className="captura__capturas-list">
                {requisitos.map((r, i) => (
                  <li key={r.id}>
                    <span className="captura__capturas-num" aria-hidden="true">
                      {i + 1}
                    </span>
                    <div>
                      <strong>{r.label}</strong>
                      <small>{r.detail}</small>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <Boton
              type="button"
              onClick={() => iniciar('tablet')}
              iconoInicio={
                <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <rect
                    x="5"
                    y="3"
                    width="14"
                    height="18"
                    rx="2"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.7"
                  />
                  <circle cx="12" cy="18" r="1" fill="currentColor" />
                </svg>
              }
            >
              Iniciar Verificación Biométrica
            </Boton>
          </div>
        )}

        {/* ---------- Fase idle — Modo handoff ---------- */}
        {fase === 'idle' && modo === 'handoff' && (
          <div className="captura__handoff">
            <div className="captura__qr">
              <div className="captura__qr-frame">
                <QrPlaceholder />
              </div>
              <span className="captura__qr-sesion">
                Sesión {QR_SESION_DEMO}
              </span>
            </div>

            <div className="captura__handoff-copy">
              <h3>Pídele al cliente que escanee el código</h3>
              <ol className="captura__handoff-list">
                <li>
                  <span className="captura__handoff-num" aria-hidden="true">
                    1
                  </span>
                  <p>
                    El cliente abre la cámara del celular y apunta al código QR.
                  </p>
                </li>
                <li>
                  <span className="captura__handoff-num" aria-hidden="true">
                    2
                  </span>
                  <p>
                    Se abre el módulo del proveedor en el navegador del celular.
                    El cliente verá las mismas instrucciones y hará la captura
                    allí.
                  </p>
                </li>
                <li>
                  <span className="captura__handoff-num" aria-hidden="true">
                    3
                  </span>
                  <p>
                    Esta pantalla se actualizará automáticamente cuando el
                    cliente termine. No la cierres.
                  </p>
                </li>
              </ol>

              <div className="captura__esperando" role="status">
                <span className="captura__esperando-dot" aria-hidden="true" />
                Esperando que el cliente complete la verificación…
              </div>

              <div className="captura__handoff-actions">
                <Boton type="button" onClick={() => iniciar('handoff')}>
                  Simular que el cliente terminó
                </Boton>
                <button
                  type="button"
                  className="captura__modo-cambiar"
                  onClick={() => cambiarModo('tablet')}
                >
                  Cambiar a esta tablet
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ---------- Fase bloqueada ---------- */}
        {bloqueado && (
          <div className="captura__espera" aria-live="polite">
            <div className="captura__espera-header">
              <span className="captura__espera-spinner" aria-hidden="true" />
              <div>
                <strong>
                  {fase === 'iniciando' && 'Abriendo módulo del proveedor…'}
                  {fase === 'capturando' && 'Capturando evidencia biométrica…'}
                  {fase === 'procesando' &&
                    'Procesando respuesta del proveedor…'}
                </strong>
                <small>
                  {fase === 'iniciando' &&
                    'Estableciendo sesión segura con el SDK.'}
                  {fase === 'capturando' &&
                    (modo === 'tablet'
                      ? 'El solicitante debe seguir las instrucciones en pantalla.'
                      : 'El cliente está capturando desde su propio celular.')}
                  {fase === 'procesando' &&
                    'Verificando coincidencia con Registraduría Nacional.'}
                </small>
              </div>
            </div>

            <div
              className="captura__espera-barra"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progreso}
              aria-label="Progreso de la captura biométrica"
            >
              <span
                className="captura__espera-barra-fill"
                style={{ width: `${progreso}%` }}
              />
            </div>

            <ul className="captura__requisitos">
              {requisitos.map((r, i) => {
                const completado = i < pasoActual
                const enCurso = i === pasoActual && fase === 'capturando'
                const pendiente = !completado && !enCurso
                return (
                  <li
                    key={r.id}
                    className={`captura__requisito${
                      completado ? ' is-done' : enCurso ? ' is-active' : ''
                    }`}
                  >
                    <span
                      className="captura__requisito-icon"
                      aria-hidden="true"
                    >
                      {completado && (
                        <svg viewBox="0 0 24 24" focusable="false">
                          <path
                            d="M5 12.5 10 17l9-10"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2.4"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                      {enCurso && <span className="captura__requisito-pulse" />}
                      {pendiente && <span className="captura__requisito-dot" />}
                    </span>
                    <div className="captura__requisito-copy">
                      <strong>{r.label}</strong>
                      <small>{r.detail}</small>
                    </div>
                  </li>
                )
              })}
            </ul>

            <p className="captura__espera-nota">
              <span className="captura__dot" aria-hidden="true" />
              No cierres esta ventana mientras el proveedor responde.
            </p>
          </div>
        )}

        {/* ---------- Fase completada ---------- */}
        {fase === 'completado' && resultado && (
          <div className="captura__resultado" role="status">
            <div className="captura__resultado-hero">
              <span className="captura__resultado-check" aria-hidden="true">
                <svg viewBox="0 0 24 24" focusable="false">
                  <path
                    d="M5 12.5 10 17l9-10"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>
              <div className="captura__resultado-copy">
                <strong>Verificación biométrica exitosa</strong>
                <span>
                  El proveedor confirmó la identidad, la prueba de vida y la
                  vigencia del documento.
                </span>
              </div>
              <span className="captura__resultado-score">
                {resultado.score}%
              </span>
            </div>

            <dl className="captura__resultado-grid">
              <div>
                <dt>ID de sesión</dt>
                <dd>
                  <code>{resultado.sessionId}</code>
                </dd>
              </div>
              <div>
                <dt>Match Registraduría</dt>
                <dd className="captura__resultado-ok">
                  {resultado.matchRegistraduria ? 'Coincide' : 'No coincide'}
                </dd>
              </div>
              <div>
                <dt>Prueba de vida (Liveness)</dt>
                <dd className="captura__resultado-ok">
                  {resultado.liveness ? 'Aprobada' : 'Rechazada'}
                </dd>
              </div>
              <div>
                <dt>Finalizado</dt>
                <dd>
                  {new Date(resultado.finalizadoEn).toLocaleString('es-CO')}
                </dd>
              </div>
            </dl>

            <div className="captura__resultado-evidencia">
              <span className="captura__resultado-evidencia-label">
                Evidencia capturada
              </span>
              <div className="captura__evidencia-chips">
                <span className="captura__evidencia-chip">Anverso</span>
                <span className="captura__evidencia-chip">Reverso</span>
                <span className="captura__evidencia-chip">Selfie</span>
                {resultado.evidencia.video && (
                  <span className="captura__evidencia-chip">Video</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ---------- Fase error ---------- */}
        {fase === 'error' && (
          <div className="captura__error-panel" role="alert">
            <span className="captura__error-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" focusable="false">
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                />
                <path
                  d="M12 7.5v5.5"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <circle cx="12" cy="16.4" r="1.1" fill="currentColor" />
              </svg>
            </span>
            <div className="captura__error-copy">
              <strong>No se pudo completar la verificación</strong>
              <p>
                {error ??
                  'El proveedor rechazó la solicitud. Puedes reintentar o cambiar de dispositivo.'}
              </p>
              <div className="captura__error-actions">
                <Boton
                  variante="secundario"
                  tamano="compacto"
                  type="button"
                  onClick={() => iniciar()}
                >
                  Reintentar verificación
                </Boton>
                <button
                  type="button"
                  className="captura__modo-cambiar"
                  onClick={() =>
                    cambiarModo(modo === 'tablet' ? 'handoff' : 'tablet')
                  }
                >
                  {modo === 'tablet'
                    ? 'Intentar en su celular'
                    : 'Intentar en esta tablet'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ---------- Footer de acciones ---------- */}
        <div className="captura__actions">
          <div className="captura__actions-left">
            {onBack && (
              <Boton
                variante="secundario"
                tamano="compacto"
                iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
                type="button"
                onClick={onBack}
                disabled={bloqueado}
              >
                Volver al paso anterior
              </Boton>
            )}
            <p className="captura__actions-note">
              <span
                className={`captura__dot${
                  bloqueado ? ' captura__dot--live' : ''
                }`}
                aria-hidden="true"
              />
              {fase === 'idle' &&
                modo === 'tablet' &&
                'Listo para iniciar en esta tablet.'}
              {fase === 'idle' &&
                modo === 'handoff' &&
                'Esperando que el cliente escanee el código.'}
              {bloqueado && 'Esperando respuesta del proveedor…'}
              {fase === 'completado' &&
                'Puedes continuar al procesamiento OCR.'}
              {fase === 'error' &&
                'Verificación fallida · puedes reintentar o cambiar de dispositivo.'}
            </p>
          </div>

          {fase === 'completado' && (
            <Boton
              type="button"
              onClick={handleContinuar}
              iconoFin={<ArrowRight size={15} aria-hidden="true" />}
            >
              Continuar a Procedimiento
            </Boton>
          )}

          {bloqueado && (
            <button
              className="captura__modo-cambiar"
              type="button"
              onClick={cancelar}
            >
              Cancelar proceso
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * Placeholder de QR.
 * Cuando integres el handoff real, reemplaza este componente por
 * `qrcode.react` o `react-qr-code` pasando el `sessionId` como valor.
 */
function QrPlaceholder() {
  const pattern = [
    '1111111010011111111',
    '1000001011010000001',
    '1011101010111011101',
    '1011101001111011101',
    '1011101010111011101',
    '1000001000010000001',
    '1111111010101111111',
    '0000000011010000000',
    '1101011010110101101',
    '0010110101101011010',
    '1101001011010110101',
    '0000000010100000000',
    '1111111011011011011',
    '1000001010100100010',
    '1011101011011011101',
    '1011101001100010101',
    '1011101010111011101',
    '1000001011001010010',
    '1111111010101010101',
  ]

  return (
    <div
      className="captura__qr-grid"
      role="img"
      aria-label="Código QR de verificación biométrica"
    >
      {pattern.flatMap((row, r) =>
        row
          .split('')
          .map((cell, c) => (
            <span
              key={`${r}-${c}`}
              className={cell === '1' ? 'is-on' : 'is-off'}
            />
          )),
      )}
    </div>
  )
}

export default CapturaCedula
