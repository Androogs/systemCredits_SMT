import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import QRCode from 'qrcode'
import { useMutation, useQuery } from '@tanstack/react-query'
import Boton from '../../../shared/ui/Boton'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import {
  crearSesionCaptura,
  estadoSesionCaptura,
  type EstadoSesionApi,
  type TipoEvidencia,
} from '../api/originacionApi'
import { env } from '../../../env'
import './CapturaCedula.css'

const API = env.VITE_API_URL.replace(/\/$/, '')

/**
 * Resultado del paso 3. `score`, `matchRegistraduria` y `liveness` quedan
 * en null porque la captura remota del MVP aún no corre validación
 * biométrica: solo persiste la evidencia (cédula + video de prueba de
 * vida) para revisión del asesor.
 */
export interface ResultadoBiometrico {
  /** `id_sesion` de la sesión de captura en el backend. */
  sessionId: string
  /** Token del enlace: se envía al crear la solicitud para enlazar evidencias. */
  sesionToken?: string
  /** true si el paso se omitió con el atajo de desarrollo (sin evidencias). */
  omitida?: boolean
  score: number | null
  evidencia: {
    anverso?: string
    reverso?: string
    selfie?: string
    video?: string
  }
  matchRegistraduria: boolean | null
  liveness: boolean | null
  finalizadoEn: string
}

type Modo = 'tablet' | 'handoff'

const REQUISITOS: { tipo: TipoEvidencia; label: string; detail: string }[] = [
  {
    tipo: 'cedula_frontal',
    label: 'Cédula — parte frontal',
    detail: 'Foto en vivo de la cara con datos personales.',
  },
  {
    tipo: 'cedula_reverso',
    label: 'Cédula — parte posterior',
    detail: 'Foto en vivo de la cara con el código de barras.',
  },
  {
    tipo: 'video_prueba_vida',
    label: 'Video de prueba de vida',
    detail: 'Cámara frontal: rostro del cliente con la cédula al lado.',
  },
]

const urlCaptura = (token: string) =>
  `${window.location.origin}/captura/${token}`

const urlEvidencia = (id: number) => `${API}/api/evidencias/${id}/contenido`

interface CapturaCedulaProps {
  onContinue?: (resultado: ResultadoBiometrico) => void
  onBack?: () => void
  /** Si es true, no renderiza header ni seguimiento (para usar dentro de otro paso). */
  compacto?: boolean
}

function CapturaCedula({
  onContinue,
  onBack,
  compacto = false,
}: CapturaCedulaProps) {
  const [modo, setModo] = useState<Modo>('handoff')
  const qrRef = useRef<HTMLCanvasElement>(null)

  const sesionMut = useMutation({ mutationFn: crearSesionCaptura })
  const sesion = sesionMut.data ?? null

  // La sesión se crea al entrar al paso para que el QR esté listo de
  // inmediato; si caduca, el asesor puede regenerarla.
  useEffect(() => {
    if (!sesionMut.data && !sesionMut.isPending) sesionMut.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Polling del estado: cada 3s hasta que la captura se complete o expire.
  const estado = useQuery<EstadoSesionApi>({
    queryKey: ['sesion-captura', sesion?.id_sesion],
    queryFn: () => estadoSesionCaptura(sesion!.id_sesion),
    enabled: Boolean(sesion?.id_sesion),
    refetchInterval: (q) =>
      q.state.data?.estado === 'completada' ||
      q.state.data?.estado === 'expirada'
        ? false
        : 3_000,
  })

  const estadoSesion = estado.data?.estado ?? sesion?.estado ?? 'pendiente'
  const evidencias = estado.data?.evidencias ?? []
  const completada = estadoSesion === 'completada'
  const expirada = estadoSesion === 'expirada'
  const link = sesion ? urlCaptura(sesion.token) : null

  // Dibuja el QR cuando el enlace está disponible.
  useEffect(() => {
    if (!link || !qrRef.current) return
    QRCode.toCanvas(qrRef.current, link, {
      width: 192,
      margin: 1,
      errorCorrectionLevel: 'M',
    }).catch(() => undefined)
  }, [link])

  const resultado: ResultadoBiometrico | null =
    completada && sesion
      ? {
          sessionId: sesion.id_sesion,
          sesionToken: sesion.token,
          score: null,
          evidencia: {
            anverso: evidencias.find((e) => e.tipo === 'cedula_frontal')
              ? urlEvidencia(
                  evidencias.find((e) => e.tipo === 'cedula_frontal')!
                    .id_evidencia,
                )
              : undefined,
            reverso: evidencias.find((e) => e.tipo === 'cedula_reverso')
              ? urlEvidencia(
                  evidencias.find((e) => e.tipo === 'cedula_reverso')!
                    .id_evidencia,
                )
              : undefined,
            video: evidencias.find((e) => e.tipo === 'video_prueba_vida')
              ? urlEvidencia(
                  evidencias.find((e) => e.tipo === 'video_prueba_vida')!
                    .id_evidencia,
                )
              : undefined,
          },
          matchRegistraduria: null,
          liveness: null,
          finalizadoEn: new Date().toISOString(),
        }
      : null

  return (
    <div className="captura">
      {!compacto && (
        <header className="captura__header">
          <div className="captura__header-copy">
            <p className="captura__eyebrow">Originación Individual · Paso 3</p>
            <h1>Captura del Documento de Identidad</h1>
            <p className="captura__subtitle">
              Cédula y video de prueba de vida
            </p>
            <p className="captura__lede">
              El cliente captura su cédula y graba un video corto con el
              documento junto a su rostro, desde su celular o en este
              dispositivo. Las evidencias quedan asociadas a la solicitud.
            </p>
          </div>

          <aside
            className="captura__panel"
            aria-label="Contexto de la radicación"
          >
            <dl className="captura__meta">
              <div>
                <dt>Vigencia del enlace</dt>
                <dd>
                  {sesion
                    ? new Date(sesion.expira_en).toLocaleTimeString('es-CO')
                    : '—'}
                </dd>
              </div>
            </dl>
            <span className="captura__server">
              <span aria-hidden="true" />
              Captura remota activa
            </span>
          </aside>
        </header>
      )}

      {!compacto && <SeguimientoOriginacion pasoActual={3} />}

      <div
        className={`captura__form${compacto ? ' captura__form--compacto' : ''}`}
      >
        <div className="captura__form-head">
          <div>
            <h2>Captura remota de evidencias</h2>
            <p>
              Sin instalar apps: el cliente abre el enlace en el navegador de su
              celular y usa la cámara directamente.
            </p>
          </div>
        </div>

        {sesionMut.isError && (
          <div className="captura__error-panel" role="alert">
            <div className="captura__error-copy">
              <strong>No se pudo crear la sesión de captura</strong>
              <p>
                {sesionMut.error instanceof Error
                  ? sesionMut.error.message
                  : 'Verifica la conexión con el servidor e intenta de nuevo.'}
              </p>
              <div className="captura__error-actions">
                <Boton
                  type="button"
                  variante="secundario"
                  tamano="compacto"
                  onClick={() => sesionMut.mutate()}
                >
                  Reintentar
                </Boton>
              </div>
            </div>
          </div>
        )}

        {sesion && !completada && (
          <>
            {/* Selector de dispositivo */}
            <div
              role="tablist"
              aria-label="Dispositivo de captura"
              className="captura__modos"
            >
              <button
                type="button"
                role="tab"
                aria-selected={modo === 'handoff'}
                onClick={() => setModo('handoff')}
                className={`captura__modo${modo === 'handoff' ? ' is-selected' : ''}`}
              >
                <span className="captura__modo-copy">
                  <span className="captura__modo-title">
                    <strong>En el celular del cliente</strong>
                    <span className="captura__modo-badge">Recomendado</span>
                  </span>
                  <small>
                    El cliente escanea el QR o abre el enlace y captura con su
                    propio celular.
                  </small>
                </span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={modo === 'tablet'}
                onClick={() => setModo('tablet')}
                className={`captura__modo${modo === 'tablet' ? ' is-selected' : ''}`}
              >
                <span className="captura__modo-copy">
                  <span className="captura__modo-title">
                    <strong>En este dispositivo</strong>
                    <span className="captura__modo-badge captura__modo-badge--soft">
                      Alternativa
                    </span>
                  </span>
                  <small>
                    Abre la página de captura aquí y entrega el dispositivo al
                    cliente.
                  </small>
                </span>
              </button>
            </div>

            {expirada ? (
              <div className="captura__error-panel" role="alert">
                <div className="captura__error-copy">
                  <strong>El enlace expiró</strong>
                  <p>
                    Por seguridad los enlaces tienen vigencia corta. Genera uno
                    nuevo para continuar.
                  </p>
                  <div className="captura__error-actions">
                    <Boton
                      type="button"
                      variante="secundario"
                      tamano="compacto"
                      onClick={() => sesionMut.mutate()}
                    >
                      Generar nuevo enlace
                    </Boton>
                  </div>
                </div>
              </div>
            ) : modo === 'handoff' ? (
              <div className="captura__handoff">
                <div className="captura__qr">
                  <div className="captura__qr-frame">
                    <canvas
                      ref={qrRef}
                      aria-label="Código QR del enlace de captura"
                    />
                  </div>
                  <span className="captura__qr-sesion">
                    Sesión {sesion.id_sesion.slice(0, 8)}
                  </span>
                </div>

                <div className="captura__handoff-copy">
                  <h3>Pídele al cliente que escanee el código</h3>
                  <ol className="captura__handoff-list">
                    <li>
                      <span className="captura__handoff-num" aria-hidden="true">
                        1
                      </span>
                      <p>Abre la cámara del celular y apunta al código QR.</p>
                    </li>
                    <li>
                      <span className="captura__handoff-num" aria-hidden="true">
                        2
                      </span>
                      <p>
                        La página de captura pide foto frontal y posterior de la
                        cédula y un video corto con el documento junto al
                        rostro.
                      </p>
                    </li>
                    <li>
                      <span className="captura__handoff-num" aria-hidden="true">
                        3
                      </span>
                      <p>
                        Esta pantalla se actualiza sola cuando llega cada
                        evidencia. No la cierres.
                      </p>
                    </li>
                  </ol>

                  <p className="captura__enlace">
                    Enlace: <code>{link}</code>
                  </p>
                  <div className="captura__esperando" role="status">
                    <span
                      className="captura__esperando-dot"
                      aria-hidden="true"
                    />
                    Esperando captura del cliente…
                  </div>
                </div>
              </div>
            ) : (
              <div className="captura__idle">
                <div className="captura__instrucciones" role="note">
                  <h3>Captura en este dispositivo</h3>
                  <ol className="captura__instrucciones-list">
                    <li>
                      <span
                        className="captura__instrucciones-num"
                        aria-hidden="true"
                      >
                        1
                      </span>
                      <span>
                        Se abre la página de captura en una pestaña nueva.
                      </span>
                    </li>
                    <li>
                      <span
                        className="captura__instrucciones-num"
                        aria-hidden="true"
                      >
                        2
                      </span>
                      <span>
                        Entrega el dispositivo al cliente para capturar.
                      </span>
                    </li>
                    <li>
                      <span
                        className="captura__instrucciones-num"
                        aria-hidden="true"
                      >
                        3
                      </span>
                      <span>Esta ventana se actualiza sola al terminar.</span>
                    </li>
                  </ol>
                </div>
                <Boton
                  type="button"
                  onClick={() =>
                    link && window.open(link, '_blank', 'noopener')
                  }
                >
                  Abrir página de captura
                </Boton>
              </div>
            )}

            {/* Progreso de evidencias en tiempo real */}
            {!expirada && (
              <ul
                className="captura__requisitos"
                aria-label="Evidencias recibidas"
              >
                {REQUISITOS.map((r) => {
                  const recibida = evidencias.some((e) => e.tipo === r.tipo)
                  return (
                    <li
                      key={r.tipo}
                      className={`captura__requisito${recibida ? ' is-done' : ''}`}
                    >
                      <span
                        className="captura__requisito-icon"
                        aria-hidden="true"
                      >
                        {recibida ? (
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
                        ) : (
                          <span className="captura__requisito-dot" />
                        )}
                      </span>
                      <div className="captura__requisito-copy">
                        <strong>{r.label}</strong>
                        <small>{r.detail}</small>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </>
        )}

        {completada && resultado && (
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
                <strong>Evidencias recibidas</strong>
                <span>
                  Cédula frontal, posterior y video de prueba de vida
                  almacenados. La validación de identidad queda pendiente de
                  revisión.
                </span>
              </div>
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
                <dd>Pendiente — no integrado</dd>
              </div>
              <div>
                <dt>Prueba de vida</dt>
                <dd>Video recibido — pendiente de revisión</dd>
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
                {resultado.evidencia.anverso && (
                  <a
                    className="captura__evidencia-chip"
                    href={resultado.evidencia.anverso}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Cédula frontal
                  </a>
                )}
                {resultado.evidencia.reverso && (
                  <a
                    className="captura__evidencia-chip"
                    href={resultado.evidencia.reverso}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Cédula posterior
                  </a>
                )}
                {resultado.evidencia.video && (
                  <a
                    className="captura__evidencia-chip"
                    href={resultado.evidencia.video}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Video de verificación
                  </a>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="captura__actions">
          <div className="captura__actions-left">
            {onBack && (
              <Boton
                variante="secundario"
                tamano="compacto"
                iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
                type="button"
                onClick={onBack}
              >
                Volver al paso anterior
              </Boton>
            )}
            <p className="captura__actions-note">
              <span
                className={`captura__dot${!completada ? ' captura__dot--live' : ''}`}
                aria-hidden="true"
              />
              {completada &&
                (compacto
                  ? 'Puedes continuar a la revisión de datos.'
                  : 'Puedes continuar al procesamiento OCR.')}
              {expirada && 'Enlace expirado — genera uno nuevo.'}
              {!completada && !expirada && 'Esperando evidencias del cliente…'}
            </p>
            {/* Atajo solo en desarrollo: permite recorrer el wizard sin
                completar la captura remota. No existe en build de producción. */}
            {import.meta.env.DEV && !completada && (
              <button
                type="button"
                className="captura__modo-cambiar"
                onClick={() =>
                  onContinue?.({
                    sessionId: '',
                    omitida: true,
                    score: null,
                    evidencia: {},
                    matchRegistraduria: null,
                    liveness: null,
                    finalizadoEn: new Date().toISOString(),
                  })
                }
              >
                Omitir captura (pruebas)
              </button>
            )}
          </div>

          {completada && resultado && (
            <Boton
              type="button"
              onClick={() => onContinue?.(resultado)}
              iconoFin={<ArrowRight size={15} aria-hidden="true" />}
            >
              {compacto ? 'Continuar' : 'Continuar a Procedimiento'}
            </Boton>
          )}
        </div>
      </div>
    </div>
  )
}

export default CapturaCedula
