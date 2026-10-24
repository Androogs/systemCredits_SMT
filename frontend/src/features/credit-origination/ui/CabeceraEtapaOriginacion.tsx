import { MODO_DEMO } from '../../../env'
import {
  obtenerConcesionario,
  obtenerUsuario,
} from '../../../shared/lib/sesion'

interface CabeceraEtapaOriginacionProps {
  paso: number
  titulo: string
  descripcion?: string
}

function CabeceraEtapaOriginacion({
  paso,
  titulo,
  descripcion,
}: CabeceraEtapaOriginacionProps) {
  const asesor = obtenerUsuario()?.nombre ?? 'Asesor'
  const sede = obtenerConcesionario()

  return (
    <header className="cabecera-etapa">
      <div className="cabecera-etapa__texto">
        <p>Originación Individual · Paso {paso}</p>
        <h1>{titulo}</h1>
        {descripcion && <span>{descripcion}</span>}
      </div>
      <aside className="cabecera-etapa__contexto">
        <dl>
          <div>
            <dt>Asesor</dt>
            <dd>{asesor}</dd>
          </div>
          <div>
            <dt>Concesionario</dt>
            <dd>{sede}</dd>
          </div>
        </dl>
        {MODO_DEMO && (
          <span className="cabecera-etapa__servidor">
            <span aria-hidden="true" />
            Modo de demostración
          </span>
        )}
      </aside>
    </header>
  )
}

export default CabeceraEtapaOriginacion
