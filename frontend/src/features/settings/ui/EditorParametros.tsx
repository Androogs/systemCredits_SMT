import { useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import type { ParametrosMotor, ValorParametro } from '../api/parametrosApi'

type CampoParametro = {
  key: string
  label: string
  ayuda?: string
}

type GrupoParametros = {
  titulo: string
  descripcion: string
  campos: CampoParametro[]
}

// Estructura de la bandeja del motor: cada sección colapsable lista
// primero sus exclusiones (checkboxes en tarjeta) y luego los inputs.
// El conteo "· N campos" se calcula con los campos que el backend expone.
const GRUPOS: GrupoParametros[] = [
  {
    titulo: 'Elegibilidad y exclusiones',
    descripcion:
      'Reglas que descartan al cliente antes de evaluar su perfil crediticio.',
    campos: [
      {
        key: 'activar_exclusion_persona_juridica',
        label: 'Excluir personas jurídicas',
      },
      {
        key: 'activar_exclusion_score_0',
        label: 'Excluir score 0 (sin historia)',
      },
      {
        key: 'activar_exclusion_score_3_fallecido',
        label: 'Excluir score 3 (fallecido)',
      },
      {
        key: 'activar_exclusion_score_4_codeudor',
        label: 'Excluir score código 4 (codeudor)',
      },
      { key: 'edad_minima_be', label: 'Edad mínima (años)' },
      {
        key: 'edad_maxima_be',
        label: 'Edad máxima exclusiva (años)',
        ayuda: 'El cliente debe ser menor que esta edad.',
      },
      {
        key: 'scores_exclusion',
        label: 'Scores de exclusión',
        ayuda: 'Separados por coma.',
      },
    ],
  },
  {
    titulo: 'Políticas de buró',
    descripcion:
      'Estados, calificaciones y ventana histórica consultados en HDC+.',
    campos: [
      { key: 'saldo_mora_be', label: 'Saldo de mora mínimo (COP)' },
      {
        key: 'estados_buro_embargo',
        label: 'Estados de embargo',
        ayuda: 'Códigos separados por coma.',
      },
      {
        key: 'estados_buro_cartera_castigada',
        label: 'Estados de cartera castigada',
        ayuda: 'Códigos separados por coma.',
      },
      {
        key: 'estados_buro_dudoso_recaudo',
        label: 'Estados de dudoso recaudo',
        ayuda: 'Códigos separados por coma.',
      },
      {
        key: 'estados_buro_pago_total',
        label: 'Estados de pago total',
        ayuda: 'Códigos separados por coma.',
      },
      {
        key: 'evento_cancelacion_mal_manejo',
        label: 'Evento de cancelación por mal manejo',
      },
      {
        key: 'calificaciones_negativas',
        label: 'Calificaciones negativas',
        ayuda: 'Letras separadas por coma.',
      },
      {
        key: 'codigos_reestructuracion',
        label: 'Códigos de reestructuración',
        ayuda: 'Códigos separados por coma.',
      },
      {
        key: 'tokens_reestructuracion',
        label: 'Palabras clave de reestructuración',
        ayuda: 'Palabras separadas por coma.',
      },
      {
        key: 'meses_ventana_buro',
        label: 'Ventana histórica del buró (meses)',
      },
      {
        key: 'umbral_mora_30_historica',
        label: 'Máximo de moras históricas de 30 días',
      },
      {
        key: 'umbral_mora_60_historica',
        label: 'Máximo de moras históricas de 60 días',
      },
      {
        key: 'umbral_mora_90_historica',
        label: 'Máximo de moras históricas de 90 días',
      },
      {
        key: 'umbral_reestructuraciones',
        label: 'Máximo de reestructuraciones',
      },
    ],
  },
  {
    titulo: 'Score y experiencia crediticia',
    descripcion:
      'Cortes de score por ocupación (A > B > C > D) y códigos aceptados del buró.',
    campos: [
      { key: 'score_ep_1', label: 'Empleado/Pensionado — corte A' },
      { key: 'score_ep_2', label: 'Empleado/Pensionado — corte B' },
      { key: 'score_ep_3', label: 'Empleado/Pensionado — corte C' },
      { key: 'score_ep_4', label: 'Empleado/Pensionado — corte D' },
      { key: 'score_if_1', label: 'Independiente/FFMM — corte A' },
      { key: 'score_if_2', label: 'Independiente/FFMM — corte B' },
      { key: 'score_if_3', label: 'Independiente/FFMM — corte C' },
      { key: 'score_if_4', label: 'Independiente/FFMM — corte D' },
      {
        key: 'score_piso_experiencia',
        label: 'Piso de experiencia crediticia',
        ayuda: 'Por debajo de este score el cliente no tiene experiencia.',
      },
      {
        key: 'codigos_score',
        label: 'Códigos de modelo de score',
        ayuda: 'Orden de preferencia, separados por coma.',
      },
      {
        key: 'quanto_factor',
        label: 'Factor Quanto → score',
        ayuda: 'Multiplica el Quanto para convertirlo en score.',
      },
    ],
  },
  {
    titulo: 'Ingreso y perfil laboral',
    descripcion:
      'Pisos de ingreso en SMMLV por ocupación y nivel, y continuidad exigida.',
    campos: [
      { key: 'ingreso_e_1', label: 'Empleado — ingreso nivel alto (SMMLV)' },
      { key: 'ingreso_e_2', label: 'Empleado — ingreso nivel medio (SMMLV)' },
      { key: 'ingreso_e_3', label: 'Empleado — ingreso nivel bajo (SMMLV)' },
      {
        key: 'ingreso_pf_1',
        label: 'Pensionado/FFMM — ingreso nivel alto (SMMLV)',
      },
      {
        key: 'ingreso_pf_2',
        label: 'Pensionado/FFMM — ingreso nivel medio (SMMLV)',
      },
      {
        key: 'ingreso_pf_3',
        label: 'Pensionado/FFMM — ingreso nivel bajo (SMMLV)',
      },
      {
        key: 'ingreso_i_1',
        label: 'Independiente — ingreso nivel alto (SMMLV)',
      },
      {
        key: 'ingreso_i_2',
        label: 'Independiente — ingreso nivel medio (SMMLV)',
      },
      {
        key: 'ingreso_i_3',
        label: 'Independiente — ingreso nivel bajo (SMMLV)',
      },
      {
        key: 'ingreso_i_4',
        label: 'Independiente — ingreso nivel gris (SMMLV)',
      },
      {
        key: 'meses_cont_1',
        label: 'Continuidad — contrato indefinido (meses)',
      },
      {
        key: 'meses_cont_2',
        label: 'Continuidad — contrato fijo u obra (meses)',
      },
      { key: 'anios_cam_1', label: 'Cámara de Comercio — nivel alto (años)' },
      { key: 'anios_cam_2', label: 'Cámara de Comercio — nivel medio (años)' },
      { key: 'anios_cam_3', label: 'Cámara de Comercio — nivel bajo (años)' },
      { key: 'anios_cam_4', label: 'Cámara de Comercio — nivel gris (años)' },
    ],
  },
  {
    titulo: 'Endeudamiento',
    descripcion:
      'Banda de endeudamiento sobre el ingreso en que se rechaza la solicitud.',
    campos: [
      {
        key: 'endeu_1',
        label: 'Umbral superior (%)',
        ayuda: 'Por encima de este porcentaje se rechaza.',
      },
      {
        key: 'endeu_2',
        label: 'Umbral inferior de la banda (%)',
        ayuda:
          'Debe ser menor que el superior; dentro de la banda también se rechaza.',
      },
    ],
  },
  {
    titulo: 'Gastos personales estimados',
    descripcion:
      'Porción del ingreso que se descuenta como gastos, por banda de SMMLV.',
    campos: [
      {
        key: 'gastos_personales_umbral_medio',
        label: 'Umbral SMMLV nivel medio',
      },
      {
        key: 'gastos_personales_umbral_alto',
        label: 'Umbral SMMLV nivel alto',
      },
      { key: 'gastos_personales_pct_bajo', label: 'Gastos — ingreso bajo (%)' },
      {
        key: 'gastos_personales_pct_medio',
        label: 'Gastos — ingreso medio (%)',
      },
      { key: 'gastos_personales_pct_alto', label: 'Gastos — ingreso alto (%)' },
      {
        key: 'gastos_personales_pct_quanto',
        label: 'Gastos sobre Quanto (%)',
      },
    ],
  },
  {
    titulo: 'Capacidad de pago',
    descripcion:
      'Porción del ingreso disponible que puede comprometerse en la cuota.',
    campos: [
      { key: 'capacidad_pago_pct', label: 'Capacidad general (%)' },
      {
        key: 'capacidad_pago_pct_asesor_digital',
        label: 'Capacidad — canal asesor digital (%)',
      },
      {
        key: 'capacidad_pago_umbral_ingreso_minimo',
        label: 'Umbral de ingreso mínimo (SMMLV)',
      },
      {
        key: 'capacidad_pago_pct_ingreso_minimo',
        label: 'Capacidad bajo ingreso mínimo (%)',
      },
      {
        key: 'capacidad_pago_factor_comportamiento',
        label: 'Factor por comportamiento de pago',
        ayuda: '1.0 = riesgo bajo, valores menores reducen la capacidad.',
      },
      {
        key: 'capacidad_pago_factor_macro',
        label: 'Factor macroeconómico',
        ayuda: '1.0 = condiciones normales.',
      },
      {
        key: 'capacidad_pago_limite_ingresos_pct',
        label: 'Tope de cuota vs. ingresos declarados',
        ayuda: 'Fracción máxima del ingreso que puede ocupar la cuota.',
      },
      {
        key: 'capacidad_pago_pct_region_nacional',
        label: 'Capacidad — región nacional (%)',
      },
      {
        key: 'capacidad_pago_pct_region_costa',
        label: 'Capacidad — Costa (%)',
        ayuda: 'Variante regional definida; el motor aún usa la nacional.',
      },
      {
        key: 'capacidad_pago_pct_region_andina',
        label: 'Capacidad — Andina (%)',
        ayuda: 'Variante regional definida; el motor aún usa la nacional.',
      },
      {
        key: 'capacidad_pago_pct_region_pacifico',
        label: 'Capacidad — Pacífico (%)',
        ayuda: 'Variante regional definida; el motor aún usa la nacional.',
      },
    ],
  },
  {
    titulo: 'Oferta sugerida y auxiliares',
    descripcion:
      'Parámetros del cupo y de la estimación de obligaciones del buró.',
    campos: [
      {
        key: 'cupo_sugerido_tasa_pct',
        label: 'Tasa mensual del cupo sugerido (%)',
      },
      {
        key: 'cupo_sugerido_plazo_meses',
        label: 'Plazo del cupo sugerido (meses)',
      },
      { key: 'cupo_sugerido_tope', label: 'Tope del cupo sugerido (COP)' },
      {
        key: 'tasa_gasto_financiero_pct',
        label: 'Tasa de gasto financiero estimado (%)',
        ayuda: 'Cuando el buró no reporta la cuota de una obligación.',
      },
      {
        key: 'plazo_rotativo_default_meses',
        label: 'Plazo rotativo por defecto (meses)',
      },
      { key: 'max_aportantes', label: 'Máximo de aportantes de ingreso' },
      {
        key: 'meses_promedio_valor_ingreso',
        label: 'Meses para el promedio del valor ingreso',
      },
    ],
  },
]

function esListaNumerica(valor: ValorParametro): valor is number[] {
  return (
    Array.isArray(valor) &&
    valor.every((elemento) => typeof elemento === 'number')
  )
}

function ControlParametro({
  campo,
  valor,
  bloqueado,
  deshabilitado,
  onChange,
}: {
  campo: CampoParametro
  valor: ValorParametro
  bloqueado: boolean
  deshabilitado: boolean
  onChange: (valor: ValorParametro) => void
}) {
  const id = `parametro-${campo.key}`

  if (typeof valor === 'boolean') {
    return (
      <label className="flex items-center justify-between gap-3 rounded-md border border-zinc-200 bg-white px-3 py-2.5 text-sm transition">
        <span className="min-w-0">{campo.label}</span>
        <input
          id={id}
          type="checkbox"
          checked={valor}
          disabled={deshabilitado || bloqueado}
          onChange={(event) => onChange(event.target.checked)}
          aria-label={campo.label}
          className="h-5 w-5 shrink-0 accent-brand-600"
        />
      </label>
    )
  }

  const esLista = Array.isArray(valor)
  const tipoListaNumerica = esLista && esListaNumerica(valor)
  const texto = esLista ? valor.join(', ') : String(valor)

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={id}
        className="text-[11px] font-medium uppercase tracking-wide text-zinc-600"
      >
        {campo.label}
      </label>
      <input
        id={id}
        type={esLista || typeof valor === 'string' ? 'text' : 'number'}
        step="any"
        value={texto}
        disabled={deshabilitado || bloqueado}
        onChange={(event) => {
          const entrada = event.target.value
          if (esLista) {
            const elementos = entrada
              .split(',')
              .map((elemento) => elemento.trim())
              .filter(Boolean)
            onChange(tipoListaNumerica ? elementos.map(Number) : elementos)
          } else if (typeof valor === 'number') {
            onChange(entrada === '' ? 0 : Number(entrada))
          } else {
            onChange(entrada)
          }
        }}
        className="h-11 w-full rounded-lg border border-zinc-200 bg-white px-3 text-base disabled:bg-zinc-100 disabled:text-zinc-500 sm:h-9 sm:rounded-md sm:text-sm"
        aria-describedby={campo.ayuda ? `${id}-ayuda` : undefined}
      />
      {campo.ayuda && (
        <p id={`${id}-ayuda`} className="text-[11px] text-zinc-500">
          {campo.ayuda}
        </p>
      )}
      {bloqueado && (
        <p className="text-[11px] text-amber-700">
          Fijado por variable de entorno
        </p>
      )}
    </div>
  )
}

function Grupo({
  grupo,
  parametros,
  bloqueados,
  deshabilitado,
  onChange,
}: {
  grupo: GrupoParametros
  parametros: ParametrosMotor
  bloqueados: Set<string>
  deshabilitado: boolean
  onChange: (key: string, valor: ValorParametro) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const campos = grupo.campos.filter((campo) => campo.key in parametros)

  if (campos.length === 0) return null

  // Las exclusiones booleanas van primero, como tarjetas, y el resto
  // de campos en la retícula de inputs.
  const booleanos = campos.filter(
    (campo) => typeof parametros[campo.key] === 'boolean',
  )
  const resto = campos.filter(
    (campo) => typeof parametros[campo.key] !== 'boolean',
  )

  return (
    <section className="rounded-lg border border-zinc-200 bg-white">
      <button
        type="button"
        aria-expanded={abierto}
        className="flex w-full items-center gap-3 p-5 text-left"
        onClick={() => setAbierto((v) => !v)}
      >
        <div className="min-w-0 flex-1">
          <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold">
            {grupo.titulo}
          </h3>
          <p className="mt-1 text-xs text-zinc-500">
            {grupo.descripcion} · {campos.length} campos
          </p>
        </div>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-300 ${
            abierto ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        />
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          abierto ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
        }`}
      >
        <div className="overflow-hidden">
          <div className="px-5 pb-5">
            {booleanos.length > 0 && (
              <div className="mb-4 grid gap-2 sm:grid-cols-2">
                {booleanos.map((campo) => (
                  <ControlParametro
                    key={campo.key}
                    campo={campo}
                    valor={parametros[campo.key]}
                    bloqueado={bloqueados.has(campo.key)}
                    deshabilitado={deshabilitado}
                    onChange={(valor) => onChange(campo.key, valor)}
                  />
                ))}
              </div>
            )}
            {resto.length > 0 && (
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {resto.map((campo) => (
                  <ControlParametro
                    key={campo.key}
                    campo={campo}
                    valor={parametros[campo.key]}
                    bloqueado={bloqueados.has(campo.key)}
                    deshabilitado={deshabilitado}
                    onChange={(valor) => onChange(campo.key, valor)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export function EditorParametros({
  seccion,
  parametros,
  bloqueados,
  cargando,
  deshabilitado,
  error,
  onRetry,
  onChange,
}: {
  seccion: 'motor' | 'riesgo'
  parametros: ParametrosMotor | null
  bloqueados: string[]
  cargando: boolean
  deshabilitado: boolean
  error: string | null
  onRetry: () => void
  onChange: (key: string, valor: ValorParametro) => void
}) {
  // La vista de riesgo es el subconjunto de reglas de elegibilidad/buró;
  // la del motor muestra la bandeja completa.
  const grupos = seccion === 'riesgo' ? GRUPOS.slice(0, 2) : GRUPOS
  const bloqueadosSet = new Set(bloqueados)

  if (cargando && !parametros) {
    return (
      <div
        role="status"
        className="rounded-lg border bg-white p-6 text-sm text-zinc-600"
      >
        Cargando parámetros desde el backend…
      </div>
    )
  }

  if (!parametros) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 p-5"
      >
        <p className="text-sm font-medium text-red-800">
          No fue posible cargar los parámetros del motor.
        </p>
        <p className="mt-1 break-words text-xs text-red-700">
          {error ?? 'La respuesta del backend está vacía.'}
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 h-8 rounded-md border border-red-300 bg-white px-3 text-xs font-medium text-red-800"
        >
          Reintentar
        </button>
      </div>
    )
  }

  const contenido: ReactNode[] = grupos.map((grupo) => (
    <Grupo
      key={grupo.titulo}
      grupo={grupo}
      parametros={parametros}
      bloqueados={bloqueadosSet}
      deshabilitado={deshabilitado}
      onChange={onChange}
    />
  ))

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
        Estos valores se cargan y guardan en el backend y alimentan directamente
        el motor de decisión. El servidor valida la coherencia de las reglas
        antes de aplicar los cambios.
      </div>
      {bloqueados.length > 0 && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
          {bloqueados.length} parámetro(s) están fijados por variables de
          entorno y no se pueden modificar desde esta pantalla.
        </div>
      )}
      {contenido}
    </div>
  )
}
