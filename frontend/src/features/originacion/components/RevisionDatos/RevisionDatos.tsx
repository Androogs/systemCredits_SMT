import { useMemo, useState, type FormEvent } from 'react'
import { ArrowLeft, ArrowRight } from 'lucide-react'
import './RevisionDatos.css'

// --- STUBS TEMPORALES para que compile aunque no tengas los módulos ---
// Cuando encuentres tu Boton real, borra esto y vuelve a poner el import

const Boton = ({ children, onClick, type, variante, tamano, iconoInicio, iconoFin,...props }: any) => (
  <button type={type || 'button'} onClick={onClick} className={`btn btn--${variante || 'primario'}`} {...props}>
    {iconoInicio}{children}{iconoFin}
  </button>
)
const emitirToast = (args: any) => console.log('TOAST:', args)
const SeguimientoOriginacion = ({ pasoActual }: { pasoActual: number }) => (
  <div style={{padding:'8px', background:'#f0f0f0', borderRadius:'8px', margin:'12px 0'}}>Paso {pasoActual} de 5</div>
)
// Schema dummy - acepta todo para que no bloquee el formulario
const datosPersonalesSchema = {
  safeParse: (datos: any) => ({ success: true, data: datos, error: { issues: [] } })
} as any

// Tipos que antes venían de originacionApi
type CampoOCRApi = { valor: string; confianza: number }
type ResultadoOCRApi = {
  disponible?: boolean
  tipo_cedula?: string
  advertencias?: string[]
  observaciones?: string[]
  numero_documento?: CampoOCRApi
  nombres?: CampoOCRApi
  apellidos?: CampoOCRApi
  sexo?: CampoOCRApi
  fecha_nacimiento?: CampoOCRApi
  fecha_expedicion?: CampoOCRApi
  lugar_nacimiento?: CampoOCRApi
  ciudad_expedicion?: CampoOCRApi
  [key: string]: any
}
// --- FIN STUBS ---

export interface DatosRevisados {
  nombres: string
  apellidos: string
  numeroIdentificacion: string
  sexo: string
  fechaNacimiento: string
  lugarNacimiento: string
  fechaExpedicion: string
  ciudadExpedicion: string
}

interface RevisionDatosProps {
  onContinue?: (datos: DatosRevisados) => void
  onBack?: () => void
  inicial?: Partial<DatosRevisados>
  compacto?: boolean
  ocr?: ResultadoOCRApi | null
}

const CONFIANZA_MAXIMA = 100
const CONFIANZA_DUDOSA = 75

type CampoId = 'nombres' | 'apellidos' | 'numeroIdentificacion' | 'sexo' | 'fechaNacimiento' | 'lugarNacimiento' | 'fechaExpedicion' | 'ciudadExpedicion'

interface DefinicionCampo {
  id: CampoId
  label: string
  tipo: 'text' | 'select' | 'date'
  opciones?: string[]
  dudoso?: boolean
  ayudaDudoso?: string
  soloLectura?: boolean
  placeholder?: string
}

const CAMPO_OCR: Record<CampoId, keyof ResultadoOCRApi> = {
  nombres: 'nombres',
  apellidos: 'apellidos',
  numeroIdentificacion: 'numero_documento',
  sexo: 'sexo',
  fechaNacimiento: 'fecha_nacimiento',
  lugarNacimiento: 'lugar_nacimiento',
  fechaExpedicion: 'fecha_expedicion',
  ciudadExpedicion: 'ciudad_expedicion',
}

const camposBase: DefinicionCampo[] = [
  { id: 'nombres', label: 'Nombres', tipo: 'text' },
  { id: 'apellidos', label: 'Apellidos', tipo: 'text' },
  { id: 'numeroIdentificacion', label: 'N° de Identificación', tipo: 'text', soloLectura: true },
  { id: 'sexo', label: 'Sexo', tipo: 'select', opciones: ['Masculino (M)', 'Femenino (F)', 'No binario'] },
  { id: 'fechaNacimiento', label: 'Fecha de Nacimiento', tipo: 'date' },
  { id: 'lugarNacimiento', label: 'Lugar de Nacimiento', tipo: 'text', dudoso: true, ayudaDudoso: 'Campo dudoso. Confirmar con el físico de la cédula.' },
  { id: 'fechaExpedicion', label: 'Fecha de Expedición', tipo: 'date' },
  { id: 'ciudadExpedicion', label: 'Ciudad de Expedición', tipo: 'text', placeholder: 'Ej: Palmira, Valle del Cauca' },
]

function campoOCR(ocr: ResultadoOCRApi | null | undefined, id: CampoId): CampoOCRApi | undefined {
  const valor = ocr?.[CAMPO_OCR[id]]
  return valor && typeof valor === 'object' && 'confianza' in valor? (valor as CampoOCRApi) : undefined
}

function construirCampos(ocr: ResultadoOCRApi | null | undefined): DefinicionCampo[] {
  return camposBase.map((campo) => {
    if (campo.dudoso || campo.soloLectura ||!ocr?.disponible) return campo
    const leido = campoOCR(ocr, campo.id)
    if (leido?.valor && leido.confianza > 0 && leido.confianza < CONFIANZA_DUDOSA) {
      return {...campo, dudoso: true, ayudaDudoso: `El OCR leyó este dato con baja confianza (${Math.round(leido.confianza)} %). Confírmalo.` }
    }
    return campo
  })
}

const valoresIniciales: DatosRevisados = {
  nombres: '', apellidos: '', numeroIdentificacion: '', sexo: '',
  fechaNacimiento: '', lugarNacimiento: '', fechaExpedicion: '', ciudadExpedicion: '',
}

function normalizarSexo(valor: string): string {
  const plano = valor.trim().toUpperCase()
  if (!plano) return ''
  if (plano.startsWith('F')) return 'Femenino (F)'
  if (plano.startsWith('M')) return 'Masculino (M)'
  return valor
}

function mapearOCR(ocr: ResultadoOCRApi | null | undefined): Partial<DatosRevisados> {
  if (!ocr) return {}
  const salida: Partial<DatosRevisados> = {}
  const doc = ocr.numero_documento?.valor?.replace(/\D/g, '')?? ''
  if (doc) salida.numeroIdentificacion = doc
  if (ocr.nombres?.valor) salida.nombres = ocr.nombres.valor
  if (ocr.apellidos?.valor) salida.apellidos = ocr.apellidos.valor
  if (ocr.fecha_nacimiento?.valor) salida.fechaNacimiento = ocr.fecha_nacimiento.valor
  if (ocr.fecha_expedicion?.valor) salida.fechaExpedicion = ocr.fecha_expedicion.valor
  const sexo = normalizarSexo(ocr.sexo?.valor?? '')
  if (sexo) salida.sexo = sexo
  if (ocr.lugar_nacimiento?.valor) salida.lugarNacimiento = ocr.lugar_nacimiento.valor
  if (ocr.ciudad_expedicion?.valor) salida.ciudadExpedicion = ocr.ciudad_expedicion.valor
  return salida
}

const ETIQUETA_TIPO: Record<string, string> = {
  blanca: 'Cédula digital (blanca)',
  amarilla: 'Cédula amarilla con hologramas',
}

function RevisionDatos({ onContinue, onBack, inicial, compacto = false, ocr = null }: RevisionDatosProps) {
  const [datos, setDatos] = useState<DatosRevisados>(() => ({
   ...valoresIniciales,
   ...mapearOCR(ocr),
   ...Object.fromEntries(Object.entries(inicial?? {}).filter(([, v]) => v!== undefined && v!== '')),
  }))
  const [dudososConfirmados, setDudososConfirmados] = useState<Record<string, boolean>>({})
  const [tocados, setTocados] = useState<Partial<Record<CampoId, boolean>>>({})
  const [intentado, setIntentado] = useState(false)
  const [registrado, setRegistrado] = useState(false)
  const [advertenciasVistas, setAdvertenciasVistas] = useState(false)

  const campos = useMemo(() => construirCampos(ocr), [ocr])
  const advertenciasOCR = ocr?.advertencias?? []
  const observacionesOCR = ocr?.observaciones?? []
  const tipoCedula = ocr?.tipo_cedula? ETIQUETA_TIPO[ocr.tipo_cedula] : null

  const errores = useMemo(() => {
    const resultado = datosPersonalesSchema.safeParse(datos)
    if (resultado.success) return {}
    const lista: Partial<Record<CampoId, string>> = {}
    for (const issue of resultado.error.issues) {
      const campo = issue.path[0] as CampoId
      if (campo &&!(campo in lista)) lista[campo] = issue.message
    }
    return lista
  }, [datos])

  const confianzaOCR = useMemo(() => {
    const confianzas = camposBase.map((c) => campoOCR(ocr, c.id)).filter((c): c is CampoOCRApi => Boolean(c?.valor)).map((c) => c.confianza).filter((c) => c > 0)
    if (confianzas.length === 0) return 50
    return confianzas.reduce((a, b) => a + b, 0) / confianzas.length
  }, [ocr])

  const camposDudosos = useMemo(() => campos.filter((c) => c.dudoso), [campos])
  const dudososConfirmadosCount = camposDudosos.filter((c) => dudososConfirmados[c.id]).length
  const bonusPorConfirmacion = camposDudosos.length > 0? (CONFIANZA_MAXIMA - confianzaOCR) / camposDudosos.length : 0
  const confianzaActual = Math.min(CONFIANZA_MAXIMA, confianzaOCR + dudososConfirmadosCount * bonusPorConfirmacion)
  const confianzaCompleta = confianzaActual >= CONFIANZA_MAXIMA
  const nivelConfianza = confianzaCompleta? 'VALIDADO' : confianzaActual >= 95? 'ALTO' : confianzaActual >= 85? 'MEDIO' : 'BAJO'
  const dudososPendientes = camposDudosos.filter((c) =>!dudososConfirmados[c.id])

  const mostrarError = (campo: CampoId) => Boolean(errores[campo]) && (intentado || tocados[campo])
  const marcarTocado = (campo: CampoId) => setTocados((prev) => ({...prev, [campo]: true }))
  const confirmarDudoso = (campo: DefinicionCampo) => {
    setDudososConfirmados((prev) => ({...prev, [campo.id]: true }))
    emitirToast({ tipo: 'exito', titulo: 'Campo confirmado', mensaje: `${campo.label} fue validado.` })
  }
  const actualizar = (campo: CampoId, valor: string) => {
    setDatos((prev) => ({...prev, [campo]: valor }))
    setRegistrado(false)
  }
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setIntentado(true)
    if (Object.keys(errores).length > 0 || dudososPendientes.length > 0) {
      setRegistrado(false)
      return
    }
    setRegistrado(true)
    onContinue?.(datos)
  }

  return (
    <div className="revision">
      {!compacto && (
        <header className="revision__header">
          <div className="revision__header-copy">
            <p className="revision__eyebrow">Originación Individual · Paso 3</p>
            <h1>Revisión de Datos Extraídos</h1>
            <p className="revision__subtitle">Confirmación de Datos OCR</p>
            <p className="revision__lede">Valida la precisión de los datos extraídos por el sistema.</p>
          </div>
          <aside className="revision__panel">
            <dl className="revision__meta"><div><dt>Asesor</dt><dd>Carlos Mendoza</dd></div><div><dt>Sede</dt><dd>Palmira - Centro Interno</dd></div></dl>
          </aside>
        </header>
      )}
      {!compacto && <SeguimientoOriginacion pasoActual={3} />}
      <form className={`revision__form${compacto? ' revision__form--compacto' : ''}`} onSubmit={handleSubmit} noValidate>
        <div className="revision__form-head">
          <div>
            <h2>Datos extraídos de la cédula</h2>
            <p>{tipoCedula && <>Documento detectado: <strong>{tipoCedula}</strong>. </>}Los campos marcados con * son obligatorios.</p>
          </div>
        </div>
        <div className="revision__confianza">
          <div className="revision__confianza-copy">
            <span className="revision__confianza-label">Nivel de Confianza Global</span>
            <small>{dudososConfirmadosCount}/{camposDudosos.length} campos dudosos confirmados.</small>
          </div>
          <div className="revision__confianza-metrica">
            <div className="revision__confianza-medidor"><span className={`revision__confianza-barra${confianzaCompleta? ' is-completa' : ''}`} style={{ width: `${confianzaActual}%` }} /></div>
            <strong className={`revision__confianza-valor${confianzaCompleta? ' is-completa' : ''}`}>{confianzaActual.toFixed(1)}% · {nivelConfianza}</strong>
          </div>
        </div>

        {advertenciasOCR.length > 0 &&!advertenciasVistas && (
          <div className="revision__banner revision__banner--warn" role="alert">
            <strong>Los datos no coinciden.</strong>
            <span className="revision__banner-sub">Verifica con la cédula física antes de continuar.</span>
            <ul className="revision__ocr-lista">{advertenciasOCR.map((aviso: string) => <li key={aviso}>{aviso}</li>)}</ul>
            <Boton variante="terciario" tamano="compacto" type="button" onClick={() => setAdvertenciasVistas(true)}>Entendido</Boton>
          </div>
        )}
        {observacionesOCR.length > 0 && (
          <div className="revision__banner revision__banner--warn"><strong>Revisa la captura.</strong><ul className="revision__ocr-lista">{observacionesOCR.map((nota: string) => <li key={nota}>{nota}</li>)}</ul></div>
        )}
        {registrado && <div className="revision__banner revision__banner--ok"><strong>Datos confirmados.</strong></div>}
        {intentado && dudososPendientes.length > 0 && <div className="revision__banner revision__banner--warn"><strong>Campos dudosos pendientes.</strong></div>}

        <div className="revision__grid">
          {campos.map((campo) => {
            const error = mostrarError(campo.id)
            const dudosoPendiente = campo.dudoso &&!dudososConfirmados[campo.id]
            const esSoloLectura = campo.soloLectura === true
            return (
              <div key={campo.id} className={`revision__field${error? ' has-error' : ''}${dudosoPendiente? ' is-dudoso' : ''}${esSoloLectura? ' is-readonly' : ''}`}>
                <label htmlFor={`rev-${campo.id}`}>{campo.label} {dudosoPendiente && <span className="revision__badge-dudoso">Requiere confirmación</span>}</label>
                {campo.tipo === 'select'? (
                  <div className="revision__input-wrap">
                    <select id={`rev-${campo.id}`} value={datos[campo.id]} onChange={(e) => actualizar(campo.id, e.target.value)} onBlur={() => marcarTocado(campo.id)}>
                      <option value="" disabled>Selecciona una opción…</option>
                      {campo.opciones?.map((opcion) => <option key={opcion} value={opcion}>{opcion}</option>)}
                    </select>
                  </div>
                ) : (
                  <input id={`rev-${campo.id}`} type={campo.tipo === 'date'? 'date' : 'text'} value={datos[campo.id]} readOnly={esSoloLectura} placeholder={campo.placeholder} onChange={(e) => actualizar(campo.id, e.target.value)} onBlur={() => marcarTocado(campo.id)} />
                )}
                {campo.dudoso && dudosoPendiente && (
                  <div className="revision__aviso-dudoso">
                    <div className="revision__aviso-body"><p>{campo.ayudaDudoso}</p><Boton variante="terciario" tamano="compacto" type="button" onClick={() => confirmarDudoso(campo)}>Confirmar campo</Boton></div>
                  </div>
                )}
                {error && <p className="revision__error">{errores[campo.id]}</p>}
              </div>
            )
          })}
        </div>

        <div className="revision__actions">
          <div className="revision__actions-left">
            {onBack && <Boton variante="secundario" tamano="compacto" iconoInicio={<ArrowLeft size={14} />} onClick={onBack}>Volver</Boton>}
            <p className="revision__actions-note">{dudososPendientes.length === 0? 'Todos los campos confirmados.' : `${dudososPendientes.length} por confirmar.`}</p>
          </div>
          <Boton type="submit" iconoFin={<ArrowRight size={15} />}>Confirmar y Continuar</Boton>
        </div>
      </form>
    </div>
  )
}

export default RevisionDatos