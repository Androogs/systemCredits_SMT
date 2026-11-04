import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import { useRol } from '../../../shared/lib/sesion'
import {
  ApiError,
  obtenerOpcionesFiltro,
  rechazarPorPoliticas,
} from '../api/originacionApi'
import {
  construirRechazoPoliticasPayload,
  type IdentidadSolicitante,
} from '../model/mapeos-api'
import './RechazoPoliticas.css'

interface RechazoPoliticasProps {
  identidad: IdentidadSolicitante | null
  sesionCapturaToken?: string
  /** La solicitud quedó persistida: el proceso de originación terminó. */
  onRegistrada: () => void
  onNuevaSolicitud: () => void
  onVolverSolicitudes: () => void
  /** Solo antes de registrar (error o falta de datos): vuelve al paso 3. */
  onBack: () => void
}

/**
 * Cierre por política clave incumplida (multas en SIMIT): radica la
 * solicitud ya rechazada con lo recopilado y muestra el resultado.
 */
function RechazoPoliticas({
  identidad,
  sesionCapturaToken,
  onRegistrada,
  onNuevaSolicitud,
  onVolverSolicitudes,
  onBack,
}: RechazoPoliticasProps) {
  // El concesionario radica a nombre de un asesor de su sede (el backend
  // lo exige); el asesor y el admin radican a su nombre de inmediato.
  const eligeAsesor = useRol() === 'concesionario'
  const [idAsesor, setIdAsesor] = useState<number | ''>('')
  const { data: opciones } = useQuery({
    queryKey: ['opciones-filtro'],
    queryFn: obtenerOpcionesFiltro,
    staleTime: 60_000,
    enabled: eligeAsesor,
  })

  const registro = useMutation({
    mutationFn: () =>
      rechazarPorPoliticas(
        construirRechazoPoliticasPayload(
          identidad!,
          sesionCapturaToken,
          idAsesor === '' ? undefined : idAsesor,
        ),
      ),
    onSuccess: () => onRegistrada(),
  })

  // Un solo envío aunque StrictMode monte el efecto dos veces: el POST no
  // es idempotente y duplicaría la solicitud.
  const enviado = useRef(false)
  useEffect(() => {
    if (!identidad || eligeAsesor || enviado.current) return
    enviado.current = true
    registro.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (registro.isSuccess) {
    const num = registro.data.num_solicitud
    return (
      <section className="rechazo-politicas" aria-labelledby="rechazo-titulo">
        <div className="rechazo-politicas__tarjeta">
          <span className="rechazo-politicas__icono" aria-hidden="true">
            <X size={30} strokeWidth={2.4} />
          </span>
          <p className="rechazo-politicas__eyebrow">
            Originación Individual · Validación Inicial
          </p>
          <h1 id="rechazo-titulo">Crédito no aprobado</h1>
          <p className="rechazo-politicas__texto">
            Los datos de la validación inicial no cumplen las políticas de
            crédito vigentes. La solicitud quedó registrada
            {num != null ? ` como #${num}` : ''} con decisión rechazada y está
            visible en el panel de solicitudes.
          </p>
          <div className="rechazo-politicas__acciones">
            <Boton type="button" onClick={onNuevaSolicitud}>
              Nueva solicitud
            </Boton>
            <Boton
              type="button"
              variante="secundario"
              onClick={onVolverSolicitudes}
            >
              Volver a solicitudes
            </Boton>
          </div>
        </div>
      </section>
    )
  }

  const error = !identidad
    ? 'Faltan datos del cliente (documento o nombre) para registrar la solicitud.'
    : registro.isError
      ? registro.error instanceof ApiError
        ? registro.error.message
        : 'No se pudo registrar la solicitud. Intenta de nuevo.'
      : null

  return (
    <section className="rechazo-politicas" aria-live="polite">
      <div className="rechazo-politicas__tarjeta">
        <p className="rechazo-politicas__eyebrow">
          Originación Individual · Validación Inicial
        </p>
        <h1>
          {error
            ? 'No se pudo registrar'
            : registro.isPending || !eligeAsesor
              ? 'Registrando la solicitud…'
              : 'Registrar solicitud rechazada'}
        </h1>
        {eligeAsesor && !registro.isPending && (
          <label className="rechazo-politicas__asesor">
            Asesor a cuyo nombre queda la solicitud
            <select
              className="input-base"
              value={idAsesor}
              onChange={(e) =>
                setIdAsesor(e.target.value ? Number(e.target.value) : '')
              }
            >
              <option value="">Seleccionar…</option>
              {(opciones?.asesores ?? []).map((a) => (
                <option key={a.id_asesor} value={a.id_asesor}>
                  {a.nombre}
                </option>
              ))}
            </select>
          </label>
        )}
        {error && (
          <p className="rechazo-politicas__error" role="alert">
            {error}
          </p>
        )}
        <div className="rechazo-politicas__acciones">
          <Boton type="button" variante="secundario" onClick={onBack}>
            Volver al paso anterior
          </Boton>
          {identidad && (eligeAsesor || registro.isError) && (
            <Boton
              type="button"
              cargando={registro.isPending}
              disabled={eligeAsesor && idAsesor === ''}
              onClick={() => registro.mutate()}
            >
              {registro.isError ? 'Reintentar' : 'Registrar solicitud'}
            </Boton>
          )}
        </div>
      </div>
    </section>
  )
}

export default RechazoPoliticas
