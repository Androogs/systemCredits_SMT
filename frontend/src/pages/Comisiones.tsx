import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import { currency } from '../shared/lib/formatters'
import { useComisiones } from '../features/comisiones/api/comisionesApi'
import { useRol } from '../shared/lib/sesion'
import { HandCoins } from 'lucide-react'

/** Etiqueta "octubre de 2026" desde la clave "2026-10" del backend. */
const etiquetaMes = (clave: string): string => {
  if (clave === 'sin-fecha') return 'Sin fecha'
  const [anio, mes] = clave.split('-').map(Number)
  return new Date(anio, mes - 1, 1).toLocaleDateString('es-CO', {
    month: 'long',
    year: 'numeric',
  })
}

const fechaCorta = (iso: string | null): string =>
  iso
    ? new Date(iso).toLocaleDateString('es-CO', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
    : '—'

const cop = (v: string): string => currency(Number(v))

const TH =
  'px-5 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-slate-500'
const TH_R = `${TH} text-right`

/** Reporte de comisiones del asesor (D134): detalle por desembolso
 * confirmado y totales por mes. El admin ve además el radicador de
 * cada fila. La superficie es trabajo — la jerarquía la llevan el peso
 * y el espacio, no el acento. */
export default function Comisiones() {
  const { data, isLoading, isError, error } = useComisiones()
  const esAdmin = useRol() === 'admin'

  return (
    <>
      <Encabezado
        title={esAdmin ? 'Comisiones' : 'Mis comisiones'}
        subtitle="Comisión sobre desembolsos confirmados del producto propio"
      />
      <div className="space-y-5 overflow-auto p-4 sm:p-6">
        {isLoading && (
          <Tarjeta className="p-6 text-center text-sm text-zinc-600">
            Cargando comisiones…
          </Tarjeta>
        )}
        {isError && (
          <Tarjeta className="border-red-200 bg-red-50 p-5 text-center text-sm text-red-800">
            {error instanceof Error
              ? error.message
              : 'No pudimos cargar tus comisiones.'}
          </Tarjeta>
        )}
        {data && data.filas.length === 0 && (
          <Tarjeta className="p-8 text-center">
            <HandCoins
              className="mx-auto h-10 w-10 text-slate-300"
              aria-hidden="true"
            />
            <p className="mt-3 text-sm text-slate-500">
              Aún no hay desembolsos confirmados que generen comisión.
            </p>
          </Tarjeta>
        )}
        {data && data.filas.length > 0 && (
          <>
            {/* Resumen del periodo: superficie tintada, no gris — el
                total es una fila de la tabla, no una métrica flotante. */}
            <Tarjeta className="p-0">
              <h3 className="px-5 pb-2 pt-5 font-semibold text-slate-900">
                Totales por mes
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-slate-200 bg-[var(--surface-tint)]">
                      <th scope="col" className={TH}>
                        Mes
                      </th>
                      <th scope="col" className={TH_R}>
                        Desembolsos
                      </th>
                      <th scope="col" className={TH_R}>
                        Capital
                      </th>
                      <th scope="col" className={TH_R}>
                        Comisión{esAdmin && ` (${Number(data.porcentaje)}%)`}
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.meses.map((m) => (
                      <tr
                        key={m.mes}
                        className="border-b border-slate-100 last:border-0"
                      >
                        <td className="px-5 py-3 font-medium capitalize text-slate-800">
                          {etiquetaMes(m.mes)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums text-slate-600">
                          {m.desembolsos}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums text-slate-600">
                          {cop(m.capital)}
                        </td>
                        <td className="px-5 py-3 text-right font-semibold tabular-nums text-slate-900">
                          {cop(m.comision)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-slate-200">
                      <th
                        scope="row"
                        className="px-5 py-3 text-left text-sm font-semibold text-slate-900"
                      >
                        Total
                      </th>
                      <td className="px-5 py-3 text-right font-semibold tabular-nums text-slate-900">
                        {data.total_desembolsos}
                      </td>
                      <td className="px-5 py-3 text-right font-semibold tabular-nums text-slate-900">
                        {cop(data.total_capital)}
                      </td>
                      <td className="px-5 py-3 text-right font-bold tabular-nums text-slate-900">
                        {cop(data.total_comision)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </Tarjeta>

            <Tarjeta className="p-0">
              <h3 className="px-5 pb-2 pt-5 font-semibold text-slate-900">
                Detalle por desembolso
              </h3>
              {/* Tabla en escritorio */}
              <div className="hidden overflow-x-auto sm:block">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-y border-slate-200 bg-[var(--surface-tint)]">
                      <th scope="col" className={TH}>
                        Fecha
                      </th>
                      <th scope="col" className={TH}>
                        Desembolso
                      </th>
                      <th scope="col" className={TH}>
                        Cliente
                      </th>
                      {esAdmin && (
                        <th scope="col" className={TH}>
                          Asesor
                        </th>
                      )}
                      <th scope="col" className={TH_R}>
                        Capital
                      </th>
                      <th scope="col" className={TH_R}>
                        Base
                      </th>
                      <th scope="col" className={TH_R}>
                        Comisión
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.filas.map((f) => (
                      <tr
                        key={f.id_desembolso}
                        className="border-b border-slate-100 last:border-0 hover:bg-[var(--surface-tint)]/60"
                      >
                        <td className="px-5 py-3 tabular-nums text-slate-600">
                          {fechaCorta(f.fecha_desembolso)}
                        </td>
                        <td className="px-5 py-3">
                          <span className="font-medium text-slate-800">
                            {f.num_desembolso ?? `#${f.id_desembolso}`}
                          </span>
                          {f.num_solicitud != null && (
                            <span className="ml-1.5 text-xs text-slate-400">
                              Sol. #{f.num_solicitud}
                            </span>
                          )}
                        </td>
                        <td className="px-5 py-3 font-medium text-slate-800">
                          {f.nombre_cliente}
                        </td>
                        {esAdmin && (
                          <td className="px-5 py-3 text-slate-600">
                            {f.nombre_asesor ?? '—'}
                          </td>
                        )}
                        <td className="px-5 py-3 text-right tabular-nums text-slate-600">
                          {cop(f.capital)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums text-slate-500">
                          {cop(f.base)}
                        </td>
                        <td className="px-5 py-3 text-right font-semibold tabular-nums text-slate-900">
                          {cop(f.comision)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Lista en móvil */}
              <ul className="divide-y divide-slate-100 sm:hidden">
                {data.filas.map((f) => (
                  <li key={f.id_desembolso} className="px-5 py-4">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="min-w-0 truncate font-medium text-slate-800">
                        {f.nombre_cliente}
                      </p>
                      <p className="shrink-0 text-xs tabular-nums text-slate-500">
                        {fechaCorta(f.fecha_desembolso)}
                      </p>
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {f.num_desembolso ?? `#${f.id_desembolso}`}
                      {f.num_solicitud != null && ` · Sol. #${f.num_solicitud}`}
                      {esAdmin && f.nombre_asesor && ` · ${f.nombre_asesor}`}
                    </p>
                    <dl className="mt-2 flex items-baseline justify-between gap-3">
                      <dd className="text-xs tabular-nums text-slate-500">
                        Capital {cop(f.capital)} · base {cop(f.base)}
                      </dd>
                      <dd className="font-semibold tabular-nums text-slate-900">
                        {cop(f.comision)}
                      </dd>
                    </dl>
                  </li>
                ))}
              </ul>
            </Tarjeta>
          </>
        )}
      </div>
    </>
  )
}
