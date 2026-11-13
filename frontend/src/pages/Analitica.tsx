import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bike, Building2 } from 'lucide-react'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Skeleton from '../shared/ui/Skeleton'
import { currency, number } from '../shared/lib/formatters'
import {
  obtenerAnalitica,
  type CausalSedeApi,
  type DimensionSegmentosApi,
  type FilaAsesorApi,
  type FilaEfectividadApi,
  type PerfilSedeApi,
} from '../features/credit-origination/api/originacionApi'

const REFRESCO_MS = 30_000
const TOPE_SEGMENTOS = 7

/** Colores de las barras apiladas: mismo lenguaje que la dona del
    Resumen (verde=bueno, azul=medio, ámbar/rojo=riesgo, gris=sin dato). */
const COLORES_SCORE: Record<string, string> = {
  A: '#10b981',
  B: '#2f74c0',
  C: '#f59e0b',
  D: '#ef4444',
  sin_evaluar: '#e2e8f0',
}
const COLORES_INGRESO: Record<string, string> = {
  ALTO: '#10b981',
  MEDIO: '#2f74c0',
  BAJO: '#f59e0b',
  GRIS: '#a78bfa',
  sin_evaluar: '#e2e8f0',
}
const OCUPACION_LABELS: Record<string, string> = {
  empleado: 'Empleado',
  independiente: 'Independiente',
  pensionado: 'Pensionado',
  fuerzas_militares: 'Fuerzas Militares',
  sin_dato: 'Sin dato',
}

function useAnalitica(desde: string, hasta: string) {
  return useQuery({
    queryKey: ['metricas-analitica', desde || null, hasta || null],
    queryFn: () =>
      obtenerAnalitica({
        desde: desde || undefined,
        hasta: hasta || undefined,
      }),
    refetchInterval: REFRESCO_MS,
  })
}

function Th({ children, derecha }: { children: string; derecha?: boolean }) {
  return (
    <th scope="col" className={`px-4 py-3 ${derecha ? 'text-right' : ''}`}>
      {children}
    </th>
  )
}

/** Barra apilada de una distribución {clave: n}; las claves sin
    color propio quedan en gris claro. */
function BarraApilada({
  datos,
  colores,
  total,
}: {
  datos: Record<string, number>
  colores: Record<string, string>
  total: number
}) {
  const orden = Object.keys(colores).filter((k) => (datos[k] ?? 0) > 0)
  return (
    <div className="space-y-1.5">
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-100">
        {orden.map((k) => (
          <div
            key={k}
            className="h-full"
            style={{
              width: `${total ? (datos[k] / total) * 100 : 0}%`,
              backgroundColor: colores[k] ?? '#cbd5e1',
            }}
            title={`${k === 'sin_evaluar' ? 'Sin evaluar' : k}: ${number(datos[k])}`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-slate-600">
        {orden.map((k) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: colores[k] ?? '#cbd5e1' }}
            />
            {k === 'sin_evaluar' ? 'Sin evaluar' : k} {number(datos[k])}
          </span>
        ))}
      </div>
    </div>
  )
}

function TablaEfectividad({
  filas,
  titulo,
}: {
  filas: FilaEfectividadApi[]
  titulo: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
            <Th>{titulo}</Th>
            <Th derecha>Radicadas</Th>
            <Th derecha>Aprobadas</Th>
            <Th derecha>Efectividad</Th>
            <Th derecha>Créditos</Th>
            <Th derecha>Rechazadas</Th>
            <Th derecha>Saldo aprobado</Th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.nombre} className="border-t border-slate-100">
              <td className="px-4 py-2.5 font-medium text-slate-800">
                {f.nombre}
              </td>
              <td className="px-4 py-2.5 text-right">{number(f.radicadas)}</td>
              <td className="px-4 py-2.5 text-right">{number(f.aprobadas)}</td>
              <td className="px-4 py-2.5 text-right font-semibold text-brand-700">
                {f.efectividad}%
              </td>
              <td className="px-4 py-2.5 text-right">{number(f.creditos)}</td>
              <td className="px-4 py-2.5 text-right text-slate-600">
                {number(f.rechazadas)}
              </td>
              <td className="px-4 py-2.5 text-right">
                {currency(Number(f.saldo_aprobado))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Una dimensión de segmentación (ej. "Estado civil"): top N segmentos
    por radicadas con opción de expandir el resto. */
function SeccionDimension({ dim }: { dim: DimensionSegmentosApi }) {
  const [expandida, setExpandida] = useState(false)
  const visibles = expandida
    ? dim.segmentos
    : dim.segmentos.slice(0, TOPE_SEGMENTOS)
  const restantes = dim.segmentos.length - TOPE_SEGMENTOS
  return (
    <section>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {dim.dimension}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-400">
            <th scope="col" className="px-2 py-2">
              Segmento
            </th>
            <th scope="col" className="px-2 py-2 text-right">
              Radicadas
            </th>
            <th scope="col" className="px-2 py-2 text-right">
              Aprobadas
            </th>
            <th scope="col" className="px-2 py-2 text-right">
              Créditos
            </th>
            <th scope="col" className="px-2 py-2 text-right">
              Efectividad
            </th>
          </tr>
        </thead>
        <tbody>
          {visibles.map((s) => (
            <tr key={s.segmento} className="border-t border-slate-100">
              <td
                className="max-w-56 truncate px-2 py-2 text-slate-800"
                title={s.segmento}
              >
                {s.segmento}
              </td>
              <td className="px-2 py-2 text-right">{number(s.radicadas)}</td>
              <td
                className="px-2 py-2 text-right"
                title={
                  s.radicadas
                    ? `${((s.aprobadas / s.radicadas) * 100).toFixed(1)}% aprobadas`
                    : undefined
                }
              >
                {number(s.aprobadas)}
              </td>
              <td className="px-2 py-2 text-right">{number(s.creditos)}</td>
              <td className="px-2 py-2 text-right font-medium text-brand-700">
                {s.radicadas ? Math.round((s.creditos / s.radicadas) * 100) : 0}
                %
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {restantes > 0 && (
        <button
          type="button"
          onClick={() => setExpandida((e) => !e)}
          className="mt-1.5 px-2 text-xs font-semibold text-brand-600 hover:underline"
        >
          {expandida ? 'Ver menos' : `Ver ${restantes} más`}
        </button>
      )}
    </section>
  )
}

export default function Analitica() {
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [vista, setVista] = useState<'sede' | 'marca'>('sede')
  const { data, isLoading, error } = useAnalitica(desde, hasta)

  const filasEfectividad = useMemo(
    () => (vista === 'sede' ? data?.por_sede : data?.por_marca) ?? [],
    [data, vista],
  )

  return (
    <>
      <Encabezado
        title="Analítica"
        subtitle="Efectividad y perfil por sector — insumo para campañas"
      />
      <div className="space-y-6 overflow-auto p-6">
        {error != null && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            <p role="alert">
              No se pudo cargar la analítica
              {error instanceof Error ? `: ${error.message}` : '.'}
            </p>
          </Tarjeta>
        )}

        {/* Filtros de rango por fecha de radicación */}
        <Tarjeta className="flex flex-wrap items-end gap-4">
          <label className="text-sm text-slate-600">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Desde
            </span>
            <input
              type="date"
              value={desde}
              onChange={(e) => setDesde(e.target.value)}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none"
            />
          </label>
          <label className="text-sm text-slate-600">
            <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
              Hasta
            </span>
            <input
              type="date"
              value={hasta}
              onChange={(e) => setHasta(e.target.value)}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none"
            />
          </label>
          {(desde || hasta) && (
            <button
              type="button"
              onClick={() => {
                setDesde('')
                setHasta('')
              }}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Limpiar
            </button>
          )}
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            {data?.historico_completo === false || desde || hasta
              ? `Rango aplicado · ${number(data?.total_radicadas ?? 0)} radicadas`
              : 'Histórico completo'}
          </span>
        </Tarjeta>

        {isLoading || !data ? (
          <div className="space-y-4">
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-44 w-full" />
            <Skeleton className="h-60 w-full" />
          </div>
        ) : (
          <>
            {/* Efectividad por sede / marca */}
            <Tarjeta className="p-0">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">
                    Efectividad por {vista === 'sede' ? 'sede' : 'marca'}
                  </h2>
                  <p className="text-xs text-slate-500">
                    Radicaciones y conversión a crédito en el periodo.
                  </p>
                </div>
                <div className="flex rounded-lg border border-slate-200 p-0.5 text-xs font-semibold">
                  {(
                    [
                      ['sede', 'Sede', Building2],
                      ['marca', 'Marca', Bike],
                    ] as const
                  ).map(([v, label, Icon]) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => setVista(v)}
                      className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 transition ${
                        vista === v
                          ? 'bg-brand-500 text-white shadow-sm'
                          : 'text-slate-500 hover:bg-slate-100 hover:text-brand-500'
                      }`}
                    >
                      <Icon size={13} /> {label}
                    </button>
                  ))}
                </div>
              </div>
              <TablaEfectividad
                filas={filasEfectividad}
                titulo={vista === 'sede' ? 'Sede' : 'Marca'}
              />
            </Tarjeta>

            {/* Efectividad por asesor */}
            <Tarjeta className="p-0">
              <div className="border-b border-slate-100 px-5 py-4">
                <h2 className="text-sm font-semibold text-slate-900">
                  Efectividad por asesor
                </h2>
                <p className="text-xs text-slate-500">
                  Quién radicó cada solicitud y cuántos créditos cerró.
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-xs uppercase text-slate-500">
                      <Th>Asesor</Th>
                      <Th derecha>Radicadas</Th>
                      <Th derecha>Créditos</Th>
                      <Th derecha>Efectividad</Th>
                      <Th derecha>Aprobadas</Th>
                      <Th derecha>Formalizadas</Th>
                      <Th derecha>Saldo aprobado</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.por_asesor.map((f: FilaAsesorApi) => (
                      <tr
                        key={f.cedula ?? f.asesor}
                        className="border-t border-slate-100"
                      >
                        <td className="px-4 py-2.5">
                          <div className="font-medium text-slate-800">
                            {f.asesor}
                          </div>
                          {f.cedula && (
                            <div className="text-xs text-slate-500">
                              CC {f.cedula}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {number(f.radicadas)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {number(f.creditos)}
                        </td>
                        <td className="px-4 py-2.5 text-right font-semibold text-brand-700">
                          {f.efectividad}%
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {number(f.aprobadas)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {number(f.formalizadas)}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {currency(Number(f.saldo_aprobado))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Tarjeta>

            {/* Perfil por sede */}
            <Tarjeta>
              <h2 className="text-sm font-semibold text-slate-900">
                Perfil por sede
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                Mezcla de perfil de score y de ingreso de la evaluación vigente,
                con la edad promedio y la ocupación del cliente.
              </p>
              <div className="space-y-5">
                {data.perfil_por_sede.map((p: PerfilSedeApi) => (
                  <div
                    key={p.nombre}
                    className="rounded-xl border border-slate-100 p-4"
                  >
                    <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
                      <h3 className="text-sm font-semibold text-slate-800">
                        {p.nombre}
                        <span className="ml-2 text-xs font-normal text-slate-500">
                          {number(p.radicadas)} solicitudes
                          {p.edad_promedio != null &&
                            ` · ${p.edad_promedio} años promedio`}
                        </span>
                      </h3>
                      <div className="flex flex-wrap gap-2 text-[11px] text-slate-600">
                        {Object.entries(p.ocupacion).map(([k, v]) => (
                          <span
                            key={k}
                            className="rounded-full bg-slate-100 px-2 py-0.5"
                          >
                            {OCUPACION_LABELS[k] ?? k}: {number(v)}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                          Perfil de score
                        </p>
                        <BarraApilada
                          datos={p.score}
                          colores={COLORES_SCORE}
                          total={p.radicadas}
                        />
                      </div>
                      <div>
                        <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                          Perfil de ingreso
                        </p>
                        <BarraApilada
                          datos={p.ingreso}
                          colores={COLORES_INGRESO}
                          total={p.radicadas}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Tarjeta>

            {/* Causales de rechazo por sede */}
            <Tarjeta>
              <h2 className="text-sm font-semibold text-slate-900">
                Causales de rechazo por sede
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                Top 5 de causales activas entre las rechazadas del periodo.
              </p>
              <div className="grid gap-4 lg:grid-cols-2">
                {data.causales_por_sede.map((c: CausalSedeApi) => (
                  <div
                    key={c.nombre}
                    className="rounded-xl border border-slate-100 p-4"
                  >
                    <h3 className="mb-2 text-sm font-semibold text-slate-800">
                      {c.nombre}
                      <span className="ml-2 text-xs font-normal text-slate-500">
                        {number(c.rechazadas)} rechazadas
                      </span>
                    </h3>
                    {c.causales.length === 0 ? (
                      <p className="text-xs text-slate-500">
                        Sin rechazos en el periodo.
                      </p>
                    ) : (
                      <table className="w-full text-sm">
                        <tbody>
                          {c.causales.map((ca) => (
                            <tr
                              key={ca.codigo}
                              className="border-t border-slate-100"
                            >
                              <td className="w-14 px-2 py-1.5 font-mono text-xs font-semibold text-slate-700">
                                {ca.codigo}
                              </td>
                              <td className="px-2 py-1.5 text-xs text-slate-600">
                                {ca.descripcion}
                              </td>
                              <td className="px-2 py-1.5 text-right text-xs font-semibold text-slate-800">
                                {number(ca.total)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                ))}
              </div>
            </Tarjeta>

            {/* Perfil para campañas */}
            <Tarjeta>
              <h2 className="text-sm font-semibold text-slate-900">
                Perfil para campañas
              </h2>
              <p className="mb-4 text-xs text-slate-500">
                Segmentos por dimensión con radicadas, aprobadas, créditos y
                efectividad — base para elegir a quién ofrecer la próxima
                campaña. Aprobadas incluye los créditos ya cerrados.
              </p>
              <div className="space-y-6">
                {data.segmentos.map((dim) => (
                  <SeccionDimension key={dim.dimension} dim={dim} />
                ))}
              </div>
            </Tarjeta>
          </>
        )}
      </div>
    </>
  )
}
