import {
  AlertTriangle,
  BadgeCheck,
  Loader2,
  RotateCw,
  XCircle,
} from 'lucide-react'
import type { ResultadoSimitData } from '../api/simitApi'
import './ResultadoSimit.css'

export type EstadoSimit = 'consultando' | 'error' | 'listo'

interface ResultadoSimitProps {
  estado: EstadoSimit
  numeroDocumento: string
  resultado?: ResultadoSimitData | null
  mensajeError?: string
  /** Solo se muestra si el cliente está a paz y salvo. */
  onContinuar: () => void
  /** Reintenta la consulta cuando SIMIT falló. */
  onReintentar: () => void
  /** Cierra la solicitud rechazada y vuelve al inicio. */
  onFinalizar: () => void
}

const formatoPesos = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  maximumFractionDigits: 0,
})

function formatearDeuda(valor: string): string {
  const numero = Number(valor)
  return Number.isFinite(numero) ? formatoPesos.format(numero) : valor
}

function formatearCedula(cedula: string): string {
  const limpia = cedula.replace(/\D/g, '')
  return limpia ? Number(limpia).toLocaleString('es-CO') : cedula
}

export default function ResultadoSimit({
  estado,
  numeroDocumento,
  resultado,
  mensajeError,
  onContinuar,
  onReintentar,
  onFinalizar,
}: ResultadoSimitProps) {
  const cedula = formatearCedula(numeroDocumento)
  const esDemo = resultado?.origen?.startsWith('mock') ?? false

  if (estado === 'consultando') {
    return (
      <section className="resultado-simit" aria-live="polite" aria-busy="true">
        <div className="resultado-simit__icono resultado-simit__icono--neutro">
          <Loader2
            className="resultado-simit__giro"
            size={40}
            aria-hidden="true"
          />
        </div>
        <h2 className="resultado-simit__titulo">Consultando SIMIT</h2>
        <p className="resultado-simit__texto">
          Verificando multas de tránsito para la cédula {cedula}.
        </p>
      </section>
    )
  }

  if (estado === 'error' || !resultado) {
    return (
      <section className="resultado-simit resultado-simit--alerta" role="alert">
        <div className="resultado-simit__icono resultado-simit__icono--alerta">
          <AlertTriangle size={40} aria-hidden="true" />
        </div>
        <h2 className="resultado-simit__titulo">No pudimos verificar SIMIT</h2>
        <p className="resultado-simit__texto">
          {mensajeError ?? 'La consulta no respondió.'} La solicitud no puede
          continuar sin esta verificación.
        </p>
        <div className="resultado-simit__acciones">
          <button
            type="button"
            className="resultado-simit__boton"
            onClick={onReintentar}
          >
            <RotateCw size={18} aria-hidden="true" />
            Reintentar consulta
          </button>
          <button
            type="button"
            className="resultado-simit__boton resultado-simit__boton--secundario"
            onClick={onFinalizar}
          >
            Volver al inicio
          </button>
        </div>
      </section>
    )
  }

  if (!resultado.paz_y_salvo) {
    return (
      <section
        className="resultado-simit resultado-simit--rechazado"
        role="alert"
      >
        <div className="resultado-simit__icono resultado-simit__icono--rechazado">
          <XCircle size={44} aria-hidden="true" />
        </div>
        <h2 className="resultado-simit__titulo">Crédito no aprobado</h2>
        <p className="resultado-simit__texto">
          El cliente registra multas de tránsito pendientes en SIMIT.
        </p>

        <dl className="resultado-simit__detalle">
          <div>
            <dt>Cédula</dt>
            <dd>{cedula}</dd>
          </div>
          <div>
            <dt>Multas pendientes</dt>
            <dd>{resultado.total_items}</dd>
          </div>
          <div>
            <dt>Valor adeudado</dt>
            <dd>{formatearDeuda(resultado.total_deuda)}</dd>
          </div>
        </dl>

        <p className="resultado-simit__nota">
          Cuando el cliente esté a paz y salvo en SIMIT, puede iniciar una nueva
          solicitud.
        </p>
        {esDemo && (
          <p className="resultado-simit__demo">
            Resultado de prueba (modo demo)
          </p>
        )}

        <div className="resultado-simit__acciones">
          <button
            type="button"
            className="resultado-simit__boton"
            onClick={onFinalizar}
          >
            Volver al inicio
          </button>
        </div>
      </section>
    )
  }

  return (
    <section
      className="resultado-simit resultado-simit--aprobado"
      aria-live="polite"
    >
      <div className="resultado-simit__icono resultado-simit__icono--aprobado">
        <BadgeCheck size={44} aria-hidden="true" />
      </div>
      <h2 className="resultado-simit__titulo">Sin multas pendientes</h2>
      <p className="resultado-simit__texto">
        La cédula {cedula} está a paz y salvo en SIMIT. Puedes continuar con la
        evidencia y los datos del cliente.
      </p>
      {esDemo && (
        <p className="resultado-simit__demo">Resultado de prueba (modo demo)</p>
      )}
      <div className="resultado-simit__acciones">
        <button
          type="button"
          className="resultado-simit__boton"
          onClick={onContinuar}
          autoFocus
        >
          Continuar con el OCR
        </button>
      </div>
    </section>
  )
}
