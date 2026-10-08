/**
 * Página pública de captura remota de evidencias (sin autenticación).
 *
 * El asesor genera un link/QR desde el paso 3 del wizard; el cliente lo
 * abre en su celular. El `token` de la URL es la única autorización y
 * caduca en ~30 min. Se capturan: cédula frontal, cédula reverso y un
 * video selfie corto con la cédula junto al rostro (prueba de vida).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  estadoCaptura,
  subirEvidencia,
  type EstadoCapturaApi,
  type TipoEvidencia,
} from '../features/credit-origination/api/originacionApi'
import './CapturaMovil.css'

const DURACION_VIDEO_MAX_SEG = 10

type EstadoSubida = 'idle' | 'subiendo' | 'ok' | 'error'

interface EstadoEvidencia {
  subida: EstadoSubida
  mensaje?: string
}

/** MIME de video soportado por este navegador (Safari iOS graba mp4). */
function mimeVideo(): string | null {
  if (typeof MediaRecorder === 'undefined') return null
  for (const mime of [
    'video/webm;codecs=vp9',
    'video/webm;codecs=vp8',
    'video/webm',
    'video/mp4',
  ]) {
    if (MediaRecorder.isTypeSupported(mime)) return mime
  }
  return null
}

function extensionDe(mime: string): string {
  return mime.includes('mp4') ? 'mp4' : 'webm'
}

export default function CapturaMovil() {
  const { token = '' } = useParams()
  const consulta = useQuery({
    queryKey: ['captura', token],
    queryFn: () => estadoCaptura(token),
    retry: (fallos, error: unknown) => {
      // Token inválido/expirado: no reintentar — el estado es definitivo.
      const status = (error as { status?: number })?.status
      return status !== 404 && status !== 422 && fallos < 2
    },
    refetchInterval: (q) =>
      q.state.data?.estado === 'completada' ? false : 10_000,
  })

  const datos = consulta.data
  const errorEstado = consulta.error as { status?: number } | undefined

  if (consulta.isLoading) {
    return (
      <main className="captura-movil">
        <p className="captura-movil__aviso" role="status">
          Verificando enlace de captura…
        </p>
      </main>
    )
  }

  if (consulta.isError || !datos) {
    const expirado =
      errorEstado?.status === 422 &&
      String((errorEstado as { detalle?: string })?.detalle ?? '').includes(
        'expir',
      )
    return (
      <main className="captura-movil">
        <div
          className="captura-movil__aviso captura-movil__aviso--error"
          role="alert"
        >
          <h1>{expirado ? 'El enlace expiró' : 'Enlace no válido'}</h1>
          <p>
            {expirado
              ? 'Por seguridad el enlace tiene vigencia corta. Pídele al asesor que genere uno nuevo.'
              : 'Este enlace de captura no existe o ya fue utilizado. Verifica que abriste el link completo o pide uno nuevo al asesor.'}
          </p>
        </div>
      </main>
    )
  }

  return (
    <main className="captura-movil">
      <header className="captura-movil__header">
        <p className="captura-movil__marca">Inversiones Pacífico · SUMOTO</p>
        <h1>Verificación de identidad</h1>
        <p>
          Toma las fotos de tu cédula y graba un video corto sosteniéndola junto
          a tu rostro. Las evidencias se envían directo al asesor.
        </p>
      </header>

      <TarjetaFoto
        token={token}
        tipo="cedula_frontal"
        titulo="1 · Cédula — parte frontal"
        ayuda="Encuadra la cara con tu foto y datos. Sin brillos ni sombras."
        subidaInicial={datos}
      />
      <TarjetaFoto
        token={token}
        tipo="cedula_reverso"
        titulo="2 · Cédula — parte posterior"
        ayuda="Encuadra la cara con el código de barras."
        subidaInicial={datos}
      />
      <TarjetaVideo token={token} estado={datos} />

      {datos.estado === 'completada' ? (
        <div
          className="captura-movil__aviso captura-movil__aviso--ok"
          role="status"
        >
          <h2>Captura completada</h2>
          <p>
            Recibimos las tres evidencias. Ya puedes cerrar esta página y avisar
            al asesor.
          </p>
        </div>
      ) : (
        <p className="captura-movil__nota">
          El enlace es personal y caduca en pocos minutos. No lo compartas.
        </p>
      )}
    </main>
  )
}

// ---------- Foto de cédula (cámara trasera) ----------

interface TarjetaFotoProps {
  token: string
  tipo: TipoEvidencia
  titulo: string
  ayuda: string
  subidaInicial: EstadoCapturaApi
}

function TarjetaFoto({
  token,
  tipo,
  titulo,
  ayuda,
  subidaInicial,
}: TarjetaFotoProps) {
  const qc = useQueryClient()
  const yaSubida = subidaInicial.evidencias.some((e) => e.tipo === tipo)
  const [estado, setEstado] = useState<EstadoEvidencia>({
    subida: yaSubida ? 'ok' : 'idle',
  })
  const [previsualizacion, setPrevisualizacion] = useState<string | null>(null)
  const [archivo, setArchivo] = useState<Blob | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => {
      if (previsualizacion) URL.revokeObjectURL(previsualizacion)
    }
  }, [previsualizacion])

  const subida = useMutation({
    mutationFn: (blob: Blob) =>
      subirEvidencia(token, tipo, blob, nombreArchivo(blob, tipo)),
    onMutate: () => setEstado({ subida: 'subiendo' }),
    onSuccess: () => {
      setEstado({ subida: 'ok' })
      qc.invalidateQueries({ queryKey: ['captura', token] })
    },
    onError: (err) =>
      setEstado({
        subida: 'error',
        mensaje:
          err instanceof Error ? err.message : 'No se pudo subir el archivo.',
      }),
  })

  const alElegir = (files: FileList | null) => {
    const file = files?.[0]
    if (!file) return
    if (previsualizacion) URL.revokeObjectURL(previsualizacion)
    setArchivo(file)
    setPrevisualizacion(URL.createObjectURL(file))
    setEstado({ subida: 'idle' })
  }

  return (
    <section
      className={`captura-movil__card captura-movil__card--${estado.subida}`}
    >
      <h2>{titulo}</h2>
      <p className="captura-movil__ayuda">{ayuda}</p>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="captura-movil__input"
        onChange={(e) => alElegir(e.target.files)}
        aria-label={titulo}
      />

      {previsualizacion && (
        <img
          src={previsualizacion}
          alt={`Vista previa — ${titulo}`}
          className="captura-movil__preview"
        />
      )}

      <div className="captura-movil__acciones">
        {estado.subida === 'ok' ? (
          <span className="captura-movil__ok" role="status">
            ✓ Recibida
          </span>
        ) : archivo ? (
          <>
            <button
              type="button"
              className="captura-movil__boton"
              onClick={() => subida.mutate(archivo)}
              disabled={estado.subida === 'subiendo'}
            >
              {estado.subida === 'subiendo'
                ? 'Subiendo…'
                : estado.subida === 'error'
                  ? 'Reintentar subida'
                  : 'Enviar foto'}
            </button>
            <button
              type="button"
              className="captura-movil__boton captura-movil__boton--sec"
              onClick={() => inputRef.current?.click()}
              disabled={estado.subida === 'subiendo'}
            >
              Tomar otra
            </button>
          </>
        ) : (
          <button
            type="button"
            className="captura-movil__boton"
            onClick={() => inputRef.current?.click()}
          >
            Abrir cámara
          </button>
        )}
      </div>

      {estado.subida === 'error' && (
        <p className="captura-movil__error" role="alert">
          {estado.mensaje}
        </p>
      )}
    </section>
  )
}

function nombreArchivo(blob: Blob, tipo: TipoEvidencia): string {
  const ext = blob.type.includes('png')
    ? 'png'
    : blob.type.includes('webp')
      ? 'webp'
      : blob.type.includes('mp4')
        ? 'mp4'
        : blob.type.includes('video')
          ? 'webm'
          : 'jpg'
  return `${tipo}.${ext}`
}

// ---------- Video selfie con la cédula (cámara frontal) ----------

type FaseVideo =
  | 'idle'
  | 'preparando' // pidiendo permiso de cámara
  | 'vista' // vista previa en vivo
  | 'grabando'
  | 'grabado' // blob listo para subir
  | 'subiendo'
  | 'ok'
  | 'error-camara'

function TarjetaVideo({
  token,
  estado,
}: {
  token: string
  estado: EstadoCapturaApi
}) {
  const qc = useQueryClient()
  const yaSubido = estado.evidencias.some((e) => e.tipo === 'video_prueba_vida')
  const [fase, setFase] = useState<FaseVideo>(yaSubido ? 'ok' : 'idle')
  const [segundos, setSegundos] = useState(0)
  const [mensaje, setMensaje] = useState<string | null>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  const blobRef = useRef<Blob | null>(null)
  const mimeRef = useRef<string>('video/webm')

  const detenerCamara = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
  }, [])

  useEffect(() => detenerCamara, [detenerCamara])

  const subida = useMutation({
    mutationFn: (blob: Blob) =>
      subirEvidencia(
        token,
        'video_prueba_vida',
        blob,
        `video_prueba_vida.${extensionDe(mimeRef.current)}`,
      ),
    onMutate: () => setFase('subiendo'),
    onSuccess: () => {
      detenerCamara()
      setFase('ok')
      qc.invalidateQueries({ queryKey: ['captura', token] })
    },
    onError: (err) => {
      setMensaje(
        err instanceof Error ? err.message : 'No se pudo subir el video.',
      )
      setFase('grabado')
    },
  })

  const iniciarCamara = async () => {
    setMensaje(null)
    const mime = mimeVideo()
    if (!mime) {
      setMensaje(
        'Este navegador no soporta grabación de video. Usa Chrome, Safari o Edge actualizados.',
      )
      setFase('error-camara')
      return
    }
    setFase('preparando')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: true,
      })
      streamRef.current = stream
      mimeRef.current = mime
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => undefined)
      }
      setFase('vista')
    } catch {
      setMensaje(
        'No se pudo acceder a la cámara. Revisa los permisos del navegador para este sitio.',
      )
      setFase('error-camara')
    }
  }

  const grabar = () => {
    const stream = streamRef.current
    if (!stream) return
    const partes: BlobPart[] = []
    const recorder = new MediaRecorder(stream, { mimeType: mimeRef.current })
    recorderRef.current = recorder
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) partes.push(e.data)
    }
    recorder.onstop = () => {
      blobRef.current = new Blob(partes, { type: mimeRef.current })
      detenerCamara()
      setFase('grabado')
    }
    recorder.start(250)
    setSegundos(0)
    setFase('grabando')

    const inicio = Date.now()
    const tick = setInterval(() => {
      const transcurridos = Math.floor((Date.now() - inicio) / 1000)
      setSegundos(transcurridos)
      if (transcurridos >= DURACION_VIDEO_MAX_SEG) {
        clearInterval(tick)
        recorder.stop()
      }
    }, 250)
  }

  const regrabar = () => {
    blobRef.current = null
    setMensaje(null)
    iniciarCamara()
  }

  return (
    <section
      className={`captura-movil__card captura-movil__card--${fase === 'ok' ? 'ok' : 'idle'}`}
    >
      <h2>3 · Video de verificación</h2>
      <p className="captura-movil__ayuda">
        Graba un video corto (máx. {DURACION_VIDEO_MAX_SEG}s) con la cámara
        frontal: tu rostro visible y la cédula sostenida a un lado de tu cara.
      </p>

      <video
        ref={videoRef}
        className="captura-movil__video"
        playsInline
        muted
        autoPlay
        hidden={fase !== 'vista' && fase !== 'grabando'}
      />

      {fase === 'grabando' && (
        <p className="captura-movil__grabando" role="status">
          <span className="captura-movil__rec" aria-hidden="true" />
          Grabando… {segundos}s / {DURACION_VIDEO_MAX_SEG}s
        </p>
      )}

      <div className="captura-movil__acciones">
        {(fase === 'idle' || fase === 'error-camara') && (
          <button
            type="button"
            className="captura-movil__boton"
            onClick={iniciarCamara}
          >
            Abrir cámara frontal
          </button>
        )}
        {fase === 'preparando' && (
          <span className="captura-movil__ayuda" role="status">
            Solicitando permiso de cámara…
          </span>
        )}
        {fase === 'vista' && (
          <>
            <button
              type="button"
              className="captura-movil__boton"
              onClick={grabar}
            >
              Grabar video
            </button>
            <button
              type="button"
              className="captura-movil__boton captura-movil__boton--sec"
              onClick={() => {
                detenerCamara()
                setFase('idle')
              }}
            >
              Cancelar
            </button>
          </>
        )}
        {fase === 'grabando' && (
          <button
            type="button"
            className="captura-movil__boton captura-movil__boton--sec"
            onClick={() => recorderRef.current?.stop()}
          >
            Detener ahora
          </button>
        )}
        {fase === 'grabado' && (
          <>
            <button
              type="button"
              className="captura-movil__boton"
              onClick={() => blobRef.current && subida.mutate(blobRef.current)}
            >
              Enviar video
            </button>
            <button
              type="button"
              className="captura-movil__boton captura-movil__boton--sec"
              onClick={regrabar}
            >
              Regrabar
            </button>
          </>
        )}
        {fase === 'subiendo' && (
          <span className="captura-movil__ayuda" role="status">
            Subiendo video…
          </span>
        )}
        {fase === 'ok' && (
          <span className="captura-movil__ok" role="status">
            ✓ Video recibido
          </span>
        )}
      </div>

      {mensaje && (
        <p className="captura-movil__error" role="alert">
          {mensaje}
        </p>
      )}
    </section>
  )
}
