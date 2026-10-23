import type { ReactNode } from 'react'
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

const GRUPOS_RIESGO: GrupoParametros[] = [
  {
    titulo: 'Elegibilidad y edad',
    descripcion:
      'Exclusiones globales que se aplican antes de evaluar el perfil.',
    campos: [
      { key: 'edad_minima_be', label: 'Edad mínima (años)' },
      {
        key: 'edad_maxima_be',
        label: 'Edad máxima exclusiva (años)',
        ayuda: 'El cliente debe ser menor a esta edad.',
      },
      {
        key: 'activar_exclusion_persona_juridica',
        label: 'Excluir personas jurídicas',
      },
      { key: 'activar_exclusion_score_0', label: 'Excluir score 0' },
      {
        key: 'activar_exclusion_score_3_fallecido',
        label: 'Excluir score 3 (fallecido)',
      },
      {
        key: 'activar_exclusion_score_4_codeudor',
        label: 'Excluir score con código de exclusión 4',
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
]

const GRUPOS_MOTOR: GrupoParametros[] = [
  {
    titulo: 'Score y experiencia crediticia',
    descripcion:
      'Cortes por perfil y códigos de score aceptados desde el buró.',
    campos: [
      { key: 'score_ep_1', label: 'Score EP nivel A' },
      { key: 'score_ep_2', label: 'Score EP nivel B' },
      { key: 'score_ep_3', label: 'Score EP nivel C' },
      { key: 'score_ep_4', label: 'Score EP nivel D' },
      { key: 'score_if_1', label: 'Score IF nivel A' },
      { key: 'score_if_2', label: 'Score IF nivel B' },
      { key: 'score_if_3', label: 'Score IF nivel C' },
      { key: 'score_if_4', label: 'Score IF nivel D' },
      {
        key: 'score_piso_experiencia',
        label: 'Piso de experiencia crediticia',
      },
      {
        key: 'codigos_score',
        label: 'Códigos de modelo de score',
        ayuda: 'Orden de preferencia, separados por coma.',
      },
      { key: 'quanto_factor', label: 'Factor de conversión de Quanto' },
    ],
  },
  {
    titulo: 'Ingreso y perfil laboral',
    descripcion: 'Ingreso mínimo en SMMLV por perfil y continuidad laboral.',
    campos: [
      { key: 'ingreso_e_1', label: 'Ingreso empleado nivel alto (SMMLV)' },
      { key: 'ingreso_e_2', label: 'Ingreso empleado nivel medio (SMMLV)' },
      { key: 'ingreso_e_3', label: 'Ingreso empleado nivel bajo (SMMLV)' },
      {
        key: 'ingreso_pf_1',
        label: 'Ingreso pensionado/FFMM nivel alto (SMMLV)',
      },
      {
        key: 'ingreso_pf_2',
        label: 'Ingreso pensionado/FFMM nivel medio (SMMLV)',
      },
      {
        key: 'ingreso_pf_3',
        label: 'Ingreso pensionado/FFMM nivel bajo (SMMLV)',
      },
      { key: 'ingreso_i_1', label: 'Ingreso independiente nivel alto (SMMLV)' },
      {
        key: 'ingreso_i_2',
        label: 'Ingreso independiente nivel medio (SMMLV)',
      },
      { key: 'ingreso_i_3', label: 'Ingreso independiente nivel bajo (SMMLV)' },
      { key: 'ingreso_i_4', label: 'Ingreso independiente nivel gris (SMMLV)' },
      { key: 'meses_cont_1', label: 'Continuidad contrato indefinido (meses)' },
      { key: 'meses_cont_2', label: 'Continuidad contrato fijo/obra (meses)' },
      {
        key: 'anios_cam_1',
        label: 'Antigüedad Cámara de Comercio nivel alto (años)',
      },
      {
        key: 'anios_cam_2',
        label: 'Antigüedad Cámara de Comercio nivel medio (años)',
      },
      {
        key: 'anios_cam_3',
        label: 'Antigüedad Cámara de Comercio nivel bajo (años)',
      },
      {
        key: 'anios_cam_4',
        label: 'Antigüedad Cámara de Comercio nivel gris (años)',
      },
    ],
  },
  {
    titulo: 'Capacidad y cupo',
    descripcion:
      'Gastos estimados, capacidad de pago y límites de la oferta sugerida.',
    campos: [
      {
        key: 'gastos_personales_pct_bajo',
        label: 'Gastos personales nivel bajo (%)',
      },
      {
        key: 'gastos_personales_pct_medio',
        label: 'Gastos personales nivel medio (%)',
      },
      {
        key: 'gastos_personales_pct_alto',
        label: 'Gastos personales nivel alto (%)',
      },
      {
        key: 'gastos_personales_umbral_medio',
        label: 'Umbral SMMLV nivel medio',
      },
      {
        key: 'gastos_personales_umbral_alto',
        label: 'Umbral SMMLV nivel alto',
      },
      { key: 'gastos_personales_pct_quanto', label: 'Gastos sobre Quanto (%)' },
      { key: 'capacidad_pago_pct', label: 'Capacidad de pago máxima (%)' },
      {
        key: 'cupo_sugerido_tasa_pct',
        label: 'Tasa mensual para cupo sugerido (%)',
      },
      {
        key: 'cupo_sugerido_plazo_meses',
        label: 'Plazo del cupo sugerido (meses)',
      },
      { key: 'cupo_sugerido_tope', label: 'Tope del cupo sugerido (COP)' },
      {
        key: 'tasa_gasto_financiero_pct',
        label: 'Tasa de gasto financiero estimado (%)',
      },
      {
        key: 'plazo_rotativo_default_meses',
        label: 'Plazo rotativo por defecto (meses)',
      },
      { key: 'max_aportantes', label: 'Máximo de aportantes' },
      {
        key: 'meses_promedio_valor_ingreso',
        label: 'Promedio de Valor Ingreso (meses)',
      },
    ],
  },
  {
    titulo: 'Endeudamiento',
    descripcion:
      'Porcentajes de endeudamiento definidos por la política del motor.',
    campos: [
      { key: 'endeu_1', label: 'Umbral superior de endeudamiento (%)' },
      { key: 'endeu_2', label: 'Umbral de endeudamiento para rechazo (%)' },
    ],
  },
  {
    titulo: 'Política de edad y exclusiones',
    descripcion:
      'Edades mínimas/máximas y exclusiones globales aplicadas antes de evaluar.',
    campos: [
      { key: 'edad_minima_be', label: 'Edad mínima (años)' },
      {
        key: 'edad_maxima_be',
        label: 'Edad máxima exclusiva (años)',
        ayuda: 'El cliente debe ser menor a esta edad.',
      },
      {
        key: 'activar_exclusion_persona_juridica',
        label: 'Excluir personas jurídicas',
      },
      { key: 'activar_exclusion_score_0', label: 'Excluir score 0' },
      {
        key: 'activar_exclusion_score_3_fallecido',
        label: 'Excluir score 3 (fallecido)',
      },
      {
        key: 'activar_exclusion_score_4_codeudor',
        label: 'Excluir score con código de exclusión 4',
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
      {
        key: 'saldo_mora_be',
        label: 'Saldo de mora mínimo (COP)',
      },
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
      <label className="flex min-h-12 items-center justify-between gap-3 rounded-lg border p-3 text-sm sm:rounded-md">
        <span>{campo.label}</span>
        <input
          id={id}
          type="checkbox"
          checked={valor}
          disabled={deshabilitado || bloqueado}
          onChange={(event) => onChange(event.target.checked)}
          aria-label={campo.label}
          className="h-5 w-5 shrink-0 accent-zinc-900"
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
  const campos = grupo.campos.filter((campo) => campo.key in parametros)

  if (campos.length === 0) return null

  return (
    <section className="rounded-lg border border-zinc-200 bg-white p-5">
      <div className="mb-4">
        <h3 className="text-sm font-semibold">{grupo.titulo}</h3>
        <p className="mt-1 text-xs text-zinc-500">{grupo.descripcion}</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {campos.map((campo) => (
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
  const grupos = seccion === 'riesgo' ? GRUPOS_RIESGO : GRUPOS_MOTOR
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
