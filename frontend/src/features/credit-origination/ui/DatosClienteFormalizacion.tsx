import { useState, type FormEvent } from 'react'
import CampoNumerico from '../../../shared/ui/CampoNumerico'
import type { DatosFormalizacionPayload } from '../api/originacionApi'
import type { DatosForm, ValorSiNo } from '../model/datos-formalizacion'

/** Campos del formulario que responden con toggle Sí/No. */
const CAMPOS_SINO: { campo: keyof DatosForm; etiqueta: string }[] = [
  { campo: 'zonaRural', etiqueta: 'Zona rural' },
  { campo: 'esCabezaFamilia', etiqueta: '¿Es cabeza de familia?' },
  { campo: 'bienesRaices', etiqueta: '¿Cuenta con bienes raíces?' },
  { campo: 'cuentaVehiculo', etiqueta: '¿Cuenta con vehículo?' },
  { campo: 'tieneMoto', etiqueta: 'Moto' },
  { campo: 'tieneCarro', etiqueta: 'Carro' },
  { campo: 'primeraMoto', etiqueta: '¿Primera moto?' },
]

const FORM_INICIAL: DatosForm = {
  viaPrincipal: '',
  numeroVia: '',
  letraVia: '',
  sector: '',
  numeroCruce: '',
  letraCruce: '',
  numeroFinal: '',
  otrasCaracteristicas: '',
  barrio: '',
  ciudad: '',
  estrato: '',
  tipoVivienda: '',
  zonaRural: '',
  estadoCivil: '',
  personasACargo: '',
  numHijos: '',
  esCabezaFamilia: '',
  bienesRaices: '',
  cuentaVehiculo: '',
  tieneMoto: '',
  tieneCarro: '',
  primeraMoto: '',
  queFinancia: 'moto',
  nombreEmpresa: '',
  ciudadEmpresa: '',
  fechaIngreso: '',
  nivelEducativo: '',
  profesion: '',
  cargo: '',
  actividadComercial: '',
}

const VIAS_PRINCIPALES = [
  'Calle',
  'Carrera',
  'Avenida',
  'Diagonal',
  'Transversal',
  'Circular',
]

const SECTORES = ['Norte', 'Sur', 'Este', 'Occidente', 'Bis']

const ESTRATOS = ['1', '2', '3', '4', '5', '6']

const TIPOS_VIVIENDA = ['Propia', 'Arrendada', 'Familiar']

const ESTADOS_CIVILES = [
  'Soltero(a)',
  'Casado(a)',
  'Unión libre',
  'Viudo(a)',
  'Divorciado(a)',
]

const NIVELES_EDUCATIVOS = [
  'Primaria',
  'Bachillerato',
  'Técnico',
  'Tecnológico',
  'Profesional',
  'Posgrado',
]

const aBool = (v: ValorSiNo): boolean | null => (v === '' ? null : v === 'si')

const aNumero = (v: string): number | null => (v === '' ? null : Number(v))

const aTexto = (v: string): string | null => {
  const t = v.trim()
  return t === '' ? null : t
}

/** Vista previa de la dirección colombiana compuesta. */
function vistaPrevia(f: DatosForm): string {
  const principal = [f.viaPrincipal, f.numeroVia, f.letraVia, f.sector]
    .filter(Boolean)
    .join(' ')
  const cruce = [f.numeroCruce, f.letraCruce].filter(Boolean).join(' ')
  const tramo = [cruce && `No. ${cruce}`, f.numeroFinal]
    .filter(Boolean)
    .join('-')
  const base = [principal, tramo].filter(Boolean).join(' ')
  return f.otrasCaracteristicas ? `${base}, ${f.otrasCaracteristicas}` : base
}

interface DatosClienteFormalizacionProps {
  deshabilitado?: boolean
  /** Error del guardado o del envío del OTP. */
  error?: string | null
  enviando?: boolean
  /** Ocupación del paso 4: adapta la sección laboral. */
  ocupacion?: string
  /** Dirección ya persistida (retomar): se muestra como referencia. */
  direccionRegistrada?: string | null
  /** Valores precargados (empresa capturada, datos ya guardados). */
  inicial?: Partial<DatosForm>
  onVolver: () => void
  onContinuar: (datos: DatosFormalizacionPayload) => void
}

/** Formulario de datos del cliente en la formalización: se diligencia
 * después de la información del vehículo y antes de enviar el OTP. */
function DatosClienteFormalizacion({
  deshabilitado = false,
  error,
  enviando = false,
  ocupacion,
  direccionRegistrada,
  inicial,
  onVolver,
  onContinuar,
}: DatosClienteFormalizacionProps) {
  const [f, setF] = useState<DatosForm>({ ...FORM_INICIAL, ...inicial })
  const [errorLocal, setErrorLocal] = useState<string | null>(null)

  const esEmpleado = ocupacion === 'Empleado'
  const esPensionadoFfmm =
    ocupacion === 'Pensionado' || ocupacion === 'Fuerzas Militares'

  const set = (campo: keyof DatosForm, valor: string) =>
    setF((prev) => ({ ...prev, [campo]: valor }))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const faltantes = CAMPOS_SINO.filter(({ campo }) => f[campo] === '').map(
      ({ etiqueta }) => etiqueta,
    )
    if (faltantes.length) {
      setErrorLocal(
        `Responde las preguntas de Sí/No pendientes: ${faltantes.join(', ')}.`,
      )
      return
    }
    setErrorLocal(null)
    onContinuar({
      via_principal: aTexto(f.viaPrincipal),
      numero_via: aTexto(f.numeroVia),
      letra_via: aTexto(f.letraVia),
      sector: aTexto(f.sector),
      numero_cruce: aTexto(f.numeroCruce),
      letra_cruce: aTexto(f.letraCruce),
      numero_final: aTexto(f.numeroFinal),
      otras_caracteristicas: aTexto(f.otrasCaracteristicas),
      barrio: aTexto(f.barrio),
      ciudad: aTexto(f.ciudad),
      estrato: aNumero(f.estrato),
      tipo_vivienda: aTexto(f.tipoVivienda),
      zona_rural: aBool(f.zonaRural),
      estado_civil: aTexto(f.estadoCivil),
      personas_a_cargo: aNumero(f.personasACargo),
      num_hijos: aNumero(f.numHijos),
      es_cabeza_familia: aBool(f.esCabezaFamilia),
      cuenta_bienes_raices: aBool(f.bienesRaices),
      cuenta_vehiculo: aBool(f.cuentaVehiculo),
      tiene_moto: aBool(f.tieneMoto),
      tiene_carro: aBool(f.tieneCarro),
      primera_moto: aBool(f.primeraMoto),
      estoy_financiando: f.queFinancia === 'moto',
      nombre_empresa: aTexto(f.nombreEmpresa),
      ciudad_empresa: aTexto(f.ciudadEmpresa),
      fecha_ingreso: f.fechaIngreso || null,
      nivel_educativo: aTexto(f.nivelEducativo),
      profesion: aTexto(f.profesion),
      cargo: aTexto(f.cargo),
      actividad_comercial: aTexto(f.actividadComercial),
    })
  }

  const toggle = (campo: keyof DatosForm, etiqueta: string) => (
    <div className="datos-cliente__sino">
      <span className="datos-cliente__sino-label" id={`dc-${campo}`}>
        {etiqueta}
      </span>
      <div
        className="datos-cliente__sino-ops"
        role="group"
        aria-labelledby={`dc-${campo}`}
      >
        {(
          [
            ['si', 'Sí'],
            ['no', 'No'],
          ] as const
        ).map(([valor, textoOp]) => (
          <button
            key={valor}
            type="button"
            className={`datos-cliente__sino-op${
              f[campo] === valor ? ' datos-cliente__sino-op--activo' : ''
            }`}
            aria-pressed={f[campo] === valor}
            disabled={deshabilitado}
            onClick={() => set(campo, valor)}
          >
            {textoOp}
          </button>
        ))}
      </div>
    </div>
  )

  const texto = (
    campo: keyof DatosForm,
    etiqueta: string,
    props: {
      required?: boolean
      placeholder?: string
      type?: string
      min?: number
      max?: number
      mostrarCero?: boolean
    } = {},
  ) => (
    <label>
      {etiqueta}
      {props.type === 'number' ? (
        <CampoNumerico
          className="input-base"
          value={f[campo] === '' ? null : Number(f[campo])}
          required={props.required}
          disabled={deshabilitado}
          placeholder={props.placeholder}
          minimo={props.min}
          maximo={props.max}
          mostrarCero={props.mostrarCero}
          onValor={(n) => set(campo, n == null ? '' : String(n))}
        />
      ) : (
        <input
          className="input-base"
          type={props.type ?? 'text'}
          value={f[campo]}
          required={props.required}
          disabled={deshabilitado}
          placeholder={props.placeholder}
          min={props.min}
          max={props.max}
          onChange={(e) => set(campo, e.target.value)}
        />
      )}
    </label>
  )

  const seleccion = (
    campo: keyof DatosForm,
    etiqueta: string,
    opciones: string[],
    obligatorio = true,
  ) => (
    <label>
      {etiqueta}
      <select
        className="input-base"
        value={f[campo]}
        required={obligatorio}
        disabled={deshabilitado}
        onChange={(e) => set(campo, e.target.value)}
      >
        <option value="">Seleccione</option>
        {opciones.map((op) => (
          <option key={op} value={op}>
            {op}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <form className="datos-cliente" onSubmit={submit}>
      <section className="datos-cliente__seccion">
        <header>
          <h3>Información de residencia</h3>
          <small>Dirección donde vive el cliente hoy</small>
        </header>
        <div className="resultado-credito__grid">
          {seleccion('viaPrincipal', 'Vía principal', VIAS_PRINCIPALES)}
          {texto('numeroVia', 'N°', { required: true, placeholder: '48' })}
          {texto('letraVia', 'Letra', { placeholder: 'A' })}
          {seleccion('sector', 'Sector', SECTORES, false)}
          {texto('numeroCruce', 'N°', { required: true, placeholder: '101' })}
          {texto('letraCruce', 'Letra', { placeholder: 'B' })}
          {texto('numeroFinal', 'N°', { required: true, placeholder: '40' })}
          {texto('otrasCaracteristicas', 'Otras características', {
            placeholder: 'Casa 10 · Apto 302',
          })}
        </div>
        {vistaPrevia(f).trim() && (
          <p className="datos-cliente__preview">
            Dirección: <strong>{vistaPrevia(f)}</strong>
          </p>
        )}
        {direccionRegistrada && (
          <p className="datos-cliente__preview">
            Ya registrada: {direccionRegistrada}
          </p>
        )}
        <div className="resultado-credito__grid">
          {texto('barrio', 'Barrio', {
            required: true,
            placeholder: 'La Flora',
          })}
          {texto('ciudad', 'Ciudad', { required: true, placeholder: 'Cali' })}
          {seleccion('estrato', 'Estrato', ESTRATOS)}
          {seleccion('tipoVivienda', 'Tipo de vivienda', TIPOS_VIVIENDA)}
          {toggle('zonaRural', 'Zona rural')}
        </div>
      </section>

      <section className="datos-cliente__seccion">
        <header>
          <h3>Información personal</h3>
          <small>Composición del hogar del cliente</small>
        </header>
        <div className="resultado-credito__grid">
          {seleccion('estadoCivil', 'Estado civil', ESTADOS_CIVILES)}
          {texto('personasACargo', 'Personas a cargo', {
            required: true,
            type: 'number',
            min: 0,
            placeholder: '0',
            mostrarCero: true,
          })}
          {texto('numHijos', 'Número de hijos', {
            required: true,
            type: 'number',
            min: 0,
            placeholder: '0',
            mostrarCero: true,
          })}
          {toggle('esCabezaFamilia', '¿Es cabeza de familia?')}
        </div>
      </section>

      <section className="datos-cliente__seccion">
        <header>
          <h3>Información financiera</h3>
          <small>Bienes con los que cuenta el cliente</small>
        </header>
        <div className="resultado-credito__grid">
          {toggle('bienesRaices', '¿Cuenta con bienes raíces?')}
          {toggle('cuentaVehiculo', '¿Cuenta con vehículo?')}
          {toggle('tieneMoto', 'Moto')}
          {toggle('tieneCarro', 'Carro')}
          {toggle('primeraMoto', '¿Primera moto?')}
        </div>
      </section>

      <section className="datos-cliente__seccion">
        <header>
          <h3>Información laboral</h3>
          <small>
            {esPensionadoFfmm
              ? 'El cliente reporta sus ingresos por una entidad pagadora'
              : esEmpleado
                ? 'Empleador y actividad del cliente'
                : 'Actividad económica del cliente'}
          </small>
        </header>
        <div className="resultado-credito__grid">
          {!esPensionadoFfmm && (
            <>
              {texto(
                'nombreEmpresa',
                ocupacion === 'Independiente'
                  ? 'Nombre del negocio'
                  : 'Nombre empresa',
                { placeholder: 'Empresa donde trabaja' },
              )}
              {texto('ciudadEmpresa', 'Ciudad', { placeholder: 'Cali' })}
              {esEmpleado &&
                texto('fechaIngreso', 'Fecha de ingreso', { type: 'date' })}
            </>
          )}
          {seleccion('nivelEducativo', 'Nivel educativo', NIVELES_EDUCATIVOS)}
          {texto('profesion', 'Profesión', { placeholder: 'Ej. Contador' })}
          {!esPensionadoFfmm &&
            esEmpleado &&
            texto('cargo', 'Cargo', {
              placeholder: 'Ej. Auxiliar administrativo',
            })}
          {!esPensionadoFfmm &&
            texto('actividadComercial', 'Actividad comercial', {
              placeholder: 'Ej. Comercio',
            })}
        </div>
      </section>

      {(errorLocal ?? error) && (
        <p className="resultado-credito__plazo-error" role="alert">
          {errorLocal ?? error}
        </p>
      )}

      <div className="resultado-credito__otp-acciones">
        <button
          type="button"
          className="resultado-credito__secundario"
          onClick={onVolver}
          disabled={deshabilitado}
        >
          Volver al vehículo
        </button>
        <button
          type="submit"
          className="resultado-credito__primario"
          disabled={deshabilitado}
        >
          {enviando ? 'Guardando…' : 'Guardar datos y continuar'}
        </button>
      </div>
    </form>
  )
}

export default DatosClienteFormalizacion
