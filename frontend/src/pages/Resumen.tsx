import { useState, useEffect, useMemo, lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Sparkline from '../shared/ui/Sparkline'
import Skeleton, { FilasSkeleton } from '../shared/ui/Skeleton'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, number, dateShort } from '../shared/lib/formatters'
import { useCuentaAscendente } from '../shared/lib/useCuentaAscendente'
import { useRol } from '../shared/lib/sesion'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
  OCUPACION_LABELS,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import type { SolicitudResumenApi } from '../features/credit-origination/api/originacionApi'
import {
  CircleCheck,
  Clock3,
  FileText,
  HandCoins,
  Plus,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  X,
  type LucideIcon,
} from 'lucide-react'
import type { FiltroPanel } from '../widgets/dashboard/GraficasResumen'
import EmbudoOriginacion from '../widgets/dashboard/EmbudoOriginacion'

const GraficasResumen = lazy(
  () => import('../widgets/dashboard/GraficasResumen'),
)

const STATUS_COLORS = {
  APROBADO: '#10b981',
  RECHAZADO: '#ef4444',
  PENDIENTE: '#94a3b8',
}

const REFRESCO_MS = 30_000

/** Saludo según la hora local (estilo portal del asesor). */
function saludoDelDia(): string {
  const h = new Date().getHours()
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

/** `mes` acota todo el panel (KPIs, gráficas, embudo y tabla);
    `estado`, `ocupacion` y `etapa` filtran la tabla y atenúan lo demás. */
function coincideFiltro(s: SolicitudResumenApi, filtro: FiltroPanel): boolean {
  if (filtro.campo === 'estado') return estadoParaVista(s) === filtro.valor
  if (filtro.campo === 'ocupacion') return s.ocupacion === filtro.valor
  if (filtro.campo === 'etapa') {
    if (filtro.valor === 'evaluadas') return s.decision != null
    if (filtro.valor === 'formalizadas') return s.fecha_hora_firma != null
    if (filtro.valor === 'desembolsadas') return s.estado === 'desembolsada'
    return true
  }
  const d = new Date(s.fecha_hora)
  return `${d.getFullYear()}-${d.getMonth()}` === filtro.valor
}

/** Etapa del embudo → filtro del panel. `radicadas` limpia el filtro;
    `aprobadas` reutiliza el filtro de estado para que la dona atenúe. */
const FILTRO_POR_ETAPA: Record<string, FiltroPanel | null> = {
  radicadas: null,
  evaluadas: { campo: 'etapa', valor: 'evaluadas', etiqueta: 'Evaluadas' },
  aprobadas: { campo: 'estado', valor: 'APROBADO', etiqueta: 'Aprobadas' },
  formalizadas: {
    campo: 'etapa',
    valor: 'formalizadas',
    etiqueta: 'Formalizadas',
  },
  desembolsadas: {
    campo: 'etapa',
    valor: 'desembolsadas',
    etiqueta: 'Desembolsadas',
  },
}

export default function Resumen() {
  const {
    datos: solicitudes,
    cargando,
    error,
    recargar,
    actualizadoEn,
    sincronizando,
  } = useSolicitudes({ limite: 200 }, { refetchIntervalMs: REFRESCO_MS })
  const rol = useRol()
  const esAsesor = rol === 'asesor'
  const [filtro, setFiltro] = useState<FiltroPanel | null>(null)
  const alternarFiltro = (f: FiltroPanel) =>
    setFiltro((actual) =>
      actual && actual.campo === f.campo && actual.valor === f.valor ? null : f,
    )
  const filtrarPorEtapa = (clave: string) => {
    const f = FILTRO_POR_ETAPA[clave]
    if (f === undefined) return
    if (f === null) {
      setFiltro(null)
      return
    }
    alternarFiltro(f)
  }

  // El filtro de mes acota el embudo en el servidor (agregados reales,
  // no derivados de las 200 filas del listado).
  const rangoEmbudo =
    filtro?.campo === 'mes'
      ? (() => {
          const [anio, mes] = filtro.valor.split('-').map(Number)
          return {
            desde: new Date(anio, mes, 1).toISOString(),
            hasta: new Date(anio, mes + 1, 1).toISOString(),
          }
        })()
      : null

  // Con filtro de mes activo, KPIs y gráficas recalculan sobre ese mes;
  // el gráfico "Últimos 6 meses" conserva todos los datos como selector.
  const base =
    filtro?.campo === 'mes'
      ? solicitudes.filter((s) => coincideFiltro(s, filtro))
      : solicitudes

  const total = base.length
  const approved = base.filter((s) => estadoParaVista(s) === 'APROBADO').length
  const rejected = base.filter((s) => estadoParaVista(s) === 'RECHAZADO').length
  const pendientes = base.filter(
    (s) => estadoParaVista(s) === 'PENDIENTE',
  ).length
  const colocadas = base.filter((s) => s.estado === 'desembolsada')

  const cupos = base
    .filter((s) => estadoParaVista(s) === 'APROBADO')
    .map((s) => numero(s.evaluacion?.cupo_sugerido))
    .filter((n): n is number => n != null)
  const capacidades = base
    .map((s) => numero(s.evaluacion?.capacidad_pago))
    .filter((n): n is number => n != null)
  const avgCapacidad = capacidades.length
    ? capacidades.reduce((a, b) => a + b, 0) / capacidades.length
    : 0
  const sumaCupos = cupos.reduce((a, b) => a + b, 0)
  const cupoColocado = colocadas.reduce(
    (acc, s) => acc + (numero(s.evaluacion?.cupo_sugerido) ?? 0),
    0,
  )

  const byStatus = [
    {
      estado: 'APROBADO',
      name: 'Aprobadas',
      value: approved,
      color: STATUS_COLORS.APROBADO,
    },
    {
      estado: 'RECHAZADO',
      name: 'Rechazadas',
      value: rejected,
      color: STATUS_COLORS.RECHAZADO,
    },
    {
      estado: 'PENDIENTE',
      name: 'Pendientes de evaluación',
      value: pendientes,
      color: STATUS_COLORS.PENDIENTE,
    },
  ]

  const last6Months = [...Array(6)].map((_, i) => {
    const d = new Date()
    d.setMonth(d.getMonth() - (5 - i))
    return {
      month: d.getMonth(),
      year: d.getFullYear(),
      label: d.toLocaleString('es-CO', { month: 'short' }),
    }
  })

  const monthBuckets = last6Months.map(({ month, year, label }) => {
    const enMes = (fecha: string, m: number, y: number) => {
      const date = new Date(fecha)
      return date.getMonth() === m && date.getFullYear() === y
    }
    // El periodo de comparación: el mismo mes seis meses atrás, así la
    // línea gris cubre exactamente la ventana previa a la mostrada.
    const prev = new Date(year, month - 6, 1)
    return {
      range: label,
      clave: `${year}-${month}`,
      count: solicitudes.filter((s) => enMes(s.fecha_hora, month, year)).length,
      anterior: solicitudes.filter((s) =>
        enMes(s.fecha_hora, prev.getMonth(), prev.getFullYear()),
      ).length,
    }
  })

  // Conteos por mes para el badge "vs mes anterior" de la banda KPI.
  // La comparación solo se muestra con filtro de mes activo: el periodo
  // seleccionado contra su mes previo (misma semántica que Looker).
  const porMes = new Map<
    string,
    {
      total: number
      aprobadas: number
      pendientes: number
      desembolsadas: number
    }
  >()
  for (const s of solicitudes) {
    const d = new Date(s.fecha_hora)
    const k = `${d.getFullYear()}-${d.getMonth()}`
    const acc = porMes.get(k) ?? {
      total: 0,
      aprobadas: 0,
      pendientes: 0,
      desembolsadas: 0,
    }
    acc.total += 1
    const ev = estadoParaVista(s)
    if (ev === 'APROBADO') acc.aprobadas += 1
    else if (ev === 'PENDIENTE') acc.pendientes += 1
    if (s.estado === 'desembolsada') acc.desembolsadas += 1
    porMes.set(k, acc)
  }
  const deltas: Record<string, number | null> = {}
  if (filtro?.campo === 'mes') {
    const [ry, rm] = filtro.valor.split('-').map(Number)
    const ant = new Date(ry, rm - 1, 1)
    const prev = porMes.get(`${ant.getFullYear()}-${ant.getMonth()}`)
    const delta = (a: number, b?: number) => (b ? (a - b) / b : null)
    deltas.solicitudes = delta(total, prev?.total)
    deltas.aprobadas = delta(approved, prev?.aprobadas)
    deltas.pendientes = delta(pendientes, prev?.pendientes)
    deltas.desembolsadas = delta(colocadas.length, prev?.desembolsadas)
  }

  // Series diarias por KPI sobre el scope vigente: los días del mes
  // filtrado o los últimos 30 días. Misma población que los totales
  // de la banda para que la tendencia y el número cuenten lo mismo.
  const diasSerie = useMemo(() => {
    if (filtro?.campo === 'mes') {
      const [ry, rm] = filtro.valor.split('-').map(Number)
      const n = new Date(ry, rm + 1, 0).getDate()
      return [...Array(n)].map((_, i) => new Date(ry, rm, i + 1))
    }
    return [...Array(30)].map((_, i) => {
      const d = new Date()
      d.setDate(d.getDate() - (29 - i))
      return d
    })
  }, [filtro])

  const serieKpi = useMemo(() => {
    const acum = {
      solicitudes: [] as number[],
      aprobadas: [] as number[],
      pendientes: [] as number[],
      desembolsadas: [] as number[],
    }
    for (const dia of diasSerie) {
      const delDia = base.filter((s) => {
        const f = new Date(s.fecha_hora)
        return (
          f.getFullYear() === dia.getFullYear() &&
          f.getMonth() === dia.getMonth() &&
          f.getDate() === dia.getDate()
        )
      })
      acum.solicitudes.push(delDia.length)
      acum.aprobadas.push(
        delDia.filter((s) => estadoParaVista(s) === 'APROBADO').length,
      )
      acum.pendientes.push(
        delDia.filter((s) => estadoParaVista(s) === 'PENDIENTE').length,
      )
      acum.desembolsadas.push(
        delDia.filter((s) => s.estado === 'desembolsada').length,
      )
    }
    return acum
  }, [base, diasSerie])

  const porOcupacion = Object.entries(OCUPACION_LABELS)
    .map(([tipo, label]) => {
      const grupo = base.filter((s) => s.ocupacion === tipo)
      const aprobadas = grupo.filter(
        (s) => estadoParaVista(s) === 'APROBADO',
      ).length
      const rechazadas = grupo.filter(
        (s) => estadoParaVista(s) === 'RECHAZADO',
      ).length
      return {
        tipo,
        label,
        total: grupo.length,
        aprobadas,
        rechazadas,
        otras: grupo.length - aprobadas - rechazadas,
      }
    })
    .filter((g) => g.total > 0)

  // Listas rankeadas tipo "Sources/Pages" del patrón de referencia:
  // distribución por plazo pedido y por perfil de score (este último
  // solo para administrador — los scores no se exponen al asesor).
  const porPlazo = Object.entries(
    base.reduce<Record<string, number>>((acc, s) => {
      const p = s.plazo_deseado_meses
      const clave = p == null ? 'Sin plazo' : `${p} meses`
      acc[clave] = (acc[clave] ?? 0) + 1
      return acc
    }, {}),
  )
    .map(([label, valor]) => ({ label, valor }))
    .sort((a, b) => b.valor - a.valor || a.label.localeCompare(b.label))

  const porScore = Object.entries(
    base.reduce<Record<string, number>>((acc, s) => {
      const p = s.evaluacion?.perfil_score
      if (!p) return acc
      acc[p] = (acc[p] ?? 0) + 1
      return acc
    }, {}),
  )
    .map(([perfil, valor]) => ({
      label: `Perfil ${perfil}`,
      valor,
    }))
    .sort((a, b) => a.label.localeCompare(b.label))

  const porDestino = Object.entries(
    base.reduce<Record<string, number>>((acc, s) => {
      const d = s.destino_credito?.trim() || 'Sin destino'
      acc[d] = (acc[d] ?? 0) + 1
      return acc
    }, {}),
  )
    .map(([label, valor]) => ({ label, valor }))
    .sort((a, b) => b.valor - a.valor)

  const hoy = new Date()
  const radicadasHoy = base.filter((s) => {
    const f = new Date(s.fecha_hora)
    return (
      f.getFullYear() === hoy.getFullYear() &&
      f.getMonth() === hoy.getMonth() &&
      f.getDate() === hoy.getDate()
    )
  }).length
  const ticketPromedio = cupos.length ? sumaCupos / cupos.length : 0

  // Animación 0 → valor real en KPIs y centro de la dona
  const totalAnimado = useCuentaAscendente(total)

  const solicitudesFiltradas =
    filtro == null
      ? solicitudes
      : solicitudes.filter((s) => coincideFiltro(s, filtro))

  return (
    <>
      <Encabezado
        title={saludoDelDia()}
        subtitle={
          esAsesor
            ? 'Prioridades comerciales y solicitudes asignadas'
            : 'Resumen general de solicitudes y decisiones'
        }
        actions={
          <>
            <IndicadorFrescura
              actualizadoEn={actualizadoEn}
              sincronizando={sincronizando}
              recargar={recargar}
            />
            <Link to="/solicitudes" className="btn-primary">
              <Plus size={16} /> Solicitudes
            </Link>
          </>
        }
      />
      <div className="p-6 space-y-6 overflow-auto">
        {error && (
          <Tarjeta className="border-red-200 bg-red-50/40 text-sm text-red-800">
            <p role="alert">No se pudo cargar el resumen: {error}</p>
          </Tarjeta>
        )}
        {filtro && (
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-brand-200 bg-brand-50/60 px-4 py-2.5 text-sm text-brand-800">
            <span className="min-w-0 flex-1">
              {filtro.campo === 'mes' ? (
                <>
                  Mostrando <strong>{filtro.etiqueta.toLowerCase()}</strong> —
                  KPIs, gráficas, embudo y tabla recalculan sobre este mes.
                </>
              ) : (
                <>
                  Filtro activo: <strong>{filtro.etiqueta}</strong> —{' '}
                  {solicitudesFiltradas.length} solicitud
                  {solicitudesFiltradas.length === 1 ? '' : 'es'} en la tabla;
                  las gráficas se atenúan.
                </>
              )}
            </span>
            <button
              type="button"
              onClick={() => setFiltro(null)}
              className="inline-flex items-center gap-1 rounded-full bg-white/80 px-2.5 py-0.5 text-xs font-semibold text-brand-700 ring-1 ring-brand-500/30 hover:bg-white"
            >
              <X size={12} /> Quitar filtro
            </button>
          </div>
        )}

        <BandaKpis
          cargando={cargando}
          total={total}
          aprobadas={approved}
          pendientes={pendientes}
          colocadas={colocadas.length}
          montoAprobado={sumaCupos}
          cupoColocado={cupoColocado}
          capacidadPromedio={avgCapacidad}
          rechazadas={rejected}
          ticketPromedio={ticketPromedio}
          radicadasHoy={radicadasHoy}
          deltas={deltas}
          series={serieKpi}
          filtro={filtro}
          setFiltro={setFiltro}
        />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Suspense
            fallback={
              <>
                {[1, 2].map((i) => (
                  <Tarjeta key={i}>
                    <Skeleton className="h-56 w-full rounded-xl" />
                  </Tarjeta>
                ))}
                <Tarjeta className="lg:col-span-2">
                  <Skeleton className="h-64 w-full rounded-xl" />
                </Tarjeta>
              </>
            }
          >
            <GraficasResumen
              cargando={cargando}
              byStatus={byStatus}
              monthBuckets={monthBuckets}
              totalAnimado={totalAnimado}
              filtro={filtro}
              alternarFiltro={alternarFiltro}
            />
          </Suspense>

          <Tarjeta>
            <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
              <h3 className="font-semibold text-slate-900">
                Aprobación por ocupación
              </h3>
              <div className="flex gap-3 text-xs text-slate-600">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  Aprobadas
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                  Rechazadas
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                  Otras
                </span>
              </div>
            </div>
            <div
              className="space-y-3"
              aria-busy={cargando}
              role="img"
              aria-label={`Aprobación por ocupación: ${porOcupacion.map((g) => `${g.label}: ${g.aprobadas} aprobadas de ${g.total}`).join(', ')}`}
            >
              {cargando ? (
                <div className="space-y-3" aria-hidden="true">
                  {[100, 85, 70].map((w) => (
                    <div
                      key={w}
                      className="h-9 animate-pulse rounded-lg bg-slate-200"
                      style={{ width: `${w}%` }}
                    />
                  ))}
                </div>
              ) : porOcupacion.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">
                  Aún no hay solicitudes registradas.
                </p>
              ) : (
                porOcupacion.map((g) => {
                  const tasa = Math.round((g.aprobadas / g.total) * 100)
                  const activo =
                    filtro?.campo === 'ocupacion' && filtro.valor === g.tipo
                  return (
                    <button
                      key={g.tipo}
                      type="button"
                      onClick={() =>
                        alternarFiltro({
                          campo: 'ocupacion',
                          valor: g.tipo,
                          etiqueta: g.label,
                        })
                      }
                      aria-pressed={activo}
                      className={`relative flex w-full items-center gap-x-3 rounded-lg px-3 pb-3 pt-2 text-sm transition hover:bg-slate-50 ${
                        activo
                          ? 'bg-brand-500/[.07] ring-1 ring-inset ring-brand-500/25'
                          : ''
                      } ${
                        filtro?.campo === 'ocupacion' && !activo
                          ? 'opacity-40'
                          : ''
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate text-left text-slate-700">
                        {g.label}
                      </span>
                      <span className="hidden shrink-0 text-xs text-slate-400 tabular-nums sm:inline">
                        {g.aprobadas} apr · {g.rechazadas} rec
                      </span>
                      <span className="w-20 shrink-0 text-right tabular-nums">
                        <span className="font-semibold text-slate-900">
                          {g.total}
                        </span>
                        <span className="text-xs text-slate-500">
                          {' '}
                          · {tasa}%
                        </span>
                      </span>
                      {/* Composición como track delgado al borde inferior:
                          aprobadas / rechazadas / otras en su proporción. */}
                      <span
                        aria-hidden="true"
                        className="absolute inset-x-3 bottom-1 flex h-[3px] overflow-hidden rounded-full bg-slate-100"
                      >
                        <span
                          className="bg-emerald-500"
                          style={{
                            width: `${(g.aprobadas / g.total) * 100}%`,
                          }}
                        />
                        <span
                          className="bg-red-400"
                          style={{
                            width: `${(g.rechazadas / g.total) * 100}%`,
                          }}
                        />
                      </span>
                    </button>
                  )
                })
              )}
            </div>
          </Tarjeta>

          <div className="lg:col-span-2">
            <EmbudoOriginacion
              esAsesor={esAsesor}
              rango={rangoEmbudo}
              filtro={filtro}
              onFiltrar={filtrarPorEtapa}
            />
          </div>

          <PanelRanking
            titulo="Plazo preferido"
            cargando={cargando}
            items={porPlazo}
            total={total}
            vacio="Aún no hay solicitudes registradas."
          />
          {/* El score es dato de administrador; el asesor ve el destino
              del crédito, igual de útil para operación en vitrina. */}
          {esAsesor ? (
            <PanelRanking
              titulo="Destino del crédito"
              cargando={cargando}
              items={porDestino}
              total={total}
              vacio="Aún no hay solicitudes registradas."
            />
          ) : (
            <PanelRanking
              titulo="Perfil de score"
              cargando={cargando}
              items={porScore}
              total={porScore.reduce((a, i) => a + i.valor, 0)}
              vacio="Aún no hay evaluaciones registradas."
            />
          )}
        </div>

        <Tarjeta>
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <h3 className="font-semibold text-slate-900">
              Últimas solicitudes
              {filtro && (
                <span className="ml-2 text-xs font-normal text-slate-500">
                  {solicitudesFiltradas.length} resultado
                  {solicitudesFiltradas.length === 1 ? '' : 's'}
                </span>
              )}
            </h3>
            <Link
              to="/solicitudes"
              className="text-sm font-medium text-brand-600 hover:text-brand-700"
            >
              Ver todas →
            </Link>
          </div>
          <div
            className="overflow-x-auto"
            role="region"
            aria-label="Tabla de últimas solicitudes"
            tabIndex={0}
          >
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th scope="col" className="py-3 pr-4">
                    N°
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Solicitante
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Fecha
                  </th>
                  <th scope="col" className="hidden py-3 pr-4 sm:table-cell">
                    Ocupación
                  </th>
                  {!esAsesor && (
                    <th scope="col" className="py-3 pr-4 text-right">
                      Score
                    </th>
                  )}
                  <th scope="col" className="py-3 pr-4 text-right">
                    Cupo sugerido
                  </th>
                  <th scope="col" className="py-3 pr-4">
                    Estado
                  </th>
                </tr>
              </thead>
              <tbody aria-busy={cargando}>
                {solicitudesFiltradas.slice(0, filtro ? 15 : 6).map((s) => {
                  const cupo = numero(s.evaluacion?.cupo_sugerido)
                  return (
                    <tr
                      key={s.id_solicitud}
                      className="border-b border-slate-100 hover:bg-slate-50"
                    >
                      <td className="py-3 pr-4 font-medium">
                        <Link
                          to={`/solicitudes/${s.id_solicitud}`}
                          className="text-brand-600 hover:underline"
                        >
                          {etiquetaSolicitud(s)}
                        </Link>
                      </td>
                      <td className="py-3 pr-4 whitespace-nowrap">
                        {s.nombre_cliente}
                      </td>
                      <td className="py-3 pr-4 text-slate-600">
                        {dateShort(s.fecha_hora)}
                      </td>
                      <td className="hidden py-3 pr-4 sm:table-cell">
                        {s.ocupacion
                          ? (OCUPACION_LABELS[s.ocupacion] ?? s.ocupacion)
                          : '—'}
                      </td>
                      {!esAsesor && (
                        <td className="py-3 pr-4 text-right tabular-nums">
                          {s.evaluacion?.score != null
                            ? Number(s.evaluacion.score)
                            : '—'}
                        </td>
                      )}
                      <td className="py-3 pr-4 text-right tabular-nums">
                        {cupo != null && estadoParaVista(s) === 'APROBADO'
                          ? currency(cupo)
                          : '—'}
                      </td>
                      <td className="py-3 pr-4">
                        <InsigniaEstado status={estadoParaVista(s)} />
                      </td>
                    </tr>
                  )
                })}
                {!cargando && solicitudesFiltradas.length === 0 && !error && (
                  <tr>
                    <td
                      colSpan={esAsesor ? 6 : 7}
                      className="py-10 text-center text-slate-500"
                    >
                      {filtro
                        ? 'Ninguna solicitud coincide con el filtro.'
                        : 'Aún no hay solicitudes registradas.'}
                    </td>
                  </tr>
                )}
                {cargando && (
                  <FilasSkeleton filas={4} columnas={esAsesor ? 6 : 7} />
                )}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      </div>
    </>
  )
}

/** Badge de comparación periodo vs mes previo (estilo scorecard de
    Looker). Solo se renderiza con filtro de mes activo: el panel
    compara el mes seleccionado contra su predecesor. */
function BadgeDelta({ delta }: { delta: number | null }) {
  if (delta == null) return null
  const sube = delta > 0
  const plano = Math.abs(delta) < 0.005
  const pct = `${sube ? '+' : ''}${Math.round(delta * 100)}%`
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded-full px-1.5 py-px text-[10px] font-semibold tabular-nums ${
        plano
          ? 'bg-slate-100 text-slate-500'
          : sube
            ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200'
            : 'bg-red-50 text-red-700 ring-1 ring-red-200'
      }`}
      title="Cambio vs mes anterior"
    >
      {!plano &&
        (sube ? (
          <TrendingUp size={10} aria-hidden="true" />
        ) : (
          <TrendingDown size={10} aria-hidden="true" />
        ))}
      {pct}
      <span className="sr-only">vs mes anterior</span>
    </span>
  )
}

/** Pulso de frescura de los datos: punto verde + "hace N s" que
    re-renderiza cada 5 s, y click = refresco manual. El spinner solo
    gira durante una sincronización en curso. */
function IndicadorFrescura({
  actualizadoEn,
  sincronizando,
  recargar,
}: {
  actualizadoEn: number | null
  sincronizando: boolean
  recargar: () => void
}) {
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 5000)
    return () => clearInterval(t)
  }, [])
  const segundos =
    actualizadoEn != null
      ? Math.max(0, Math.round((ahora - actualizadoEn) / 1000))
      : null
  const texto =
    segundos == null
      ? 'Sin datos'
      : segundos < 10
        ? 'Datos al día'
        : segundos < 60
          ? `hace ${segundos} s`
          : `hace ${Math.floor(segundos / 60)} min`
  return (
    <button
      type="button"
      onClick={recargar}
      title="Actualizar ahora"
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-500 transition hover:border-slate-300 hover:text-slate-700"
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          sincronizando ? 'bg-brand-500' : 'bg-emerald-500'
        } ${sincronizando ? '' : 'motion-safe:animate-pulse'}`}
        aria-hidden="true"
      />
      {sincronizando ? 'Actualizando…' : texto}
      <RefreshCw
        size={12}
        aria-hidden="true"
        className={sincronizando ? 'motion-safe:animate-spin' : ''}
      />
    </button>
  )
}

/** Banda única de indicadores: cuatro celdas navegables (cada una es
    un filtro) y una franja secundaria de estadísticas monetarias.
    Reemplaza la retícula de ocho tarjetas: mismo dato, menos ruido. */
function BandaKpis({
  cargando,
  total,
  aprobadas,
  pendientes,
  colocadas,
  montoAprobado,
  cupoColocado,
  capacidadPromedio,
  rechazadas,
  ticketPromedio,
  radicadasHoy,
  deltas,
  series,
  filtro,
  setFiltro,
}: {
  cargando: boolean
  total: number
  aprobadas: number
  pendientes: number
  colocadas: number
  montoAprobado: number
  cupoColocado: number
  capacidadPromedio: number
  rechazadas: number
  ticketPromedio: number
  radicadasHoy: number
  deltas: Record<string, number | null>
  series: {
    solicitudes: number[]
    aprobadas: number[]
    pendientes: number[]
    desembolsadas: number[]
  }
  filtro: FiltroPanel | null
  setFiltro: (f: FiltroPanel | null) => void
}) {
  const tasaRechazo = total ? (rechazadas / total) * 100 : 0
  const celdas: {
    label: string
    valor: number
    detalle: string
    filtroCelda: FiltroPanel | null
    delta: number | null
    serie: number[]
    icono: LucideIcon
    chip: string
    activo: boolean
  }[] = [
    {
      label: 'Solicitudes',
      valor: total,
      detalle: 'Radicadas en el panel',
      filtroCelda: null,
      serie: series.solicitudes,
      delta: deltas.solicitudes ?? null,
      icono: FileText,
      chip: 'bg-brand-50 text-brand-600 ring-brand-500/20',
      activo: filtro == null,
    },
    {
      label: 'Aprobadas',
      valor: aprobadas,
      detalle: `Conversión ${total ? Math.round((aprobadas / total) * 100) : 0}%`,
      filtroCelda: {
        campo: 'estado',
        valor: 'APROBADO',
        etiqueta: 'Aprobadas',
      },
      delta: deltas.aprobadas ?? null,
      serie: series.aprobadas,
      icono: CircleCheck,
      chip: 'bg-emerald-50 text-emerald-600 ring-emerald-500/20',
      activo: filtro?.campo === 'estado' && filtro.valor === 'APROBADO',
    },
    {
      label: 'Pendientes',
      valor: pendientes,
      detalle: 'Requieren gestión',
      filtroCelda: {
        campo: 'estado',
        valor: 'PENDIENTE',
        etiqueta: 'Pendientes',
      },
      delta: deltas.pendientes ?? null,
      serie: series.pendientes,
      icono: Clock3,
      chip: 'bg-amber-50 text-amber-600 ring-amber-500/20',
      activo: filtro?.campo === 'estado' && filtro.valor === 'PENDIENTE',
    },
    {
      label: 'Desembolsadas',
      valor: colocadas,
      detalle: 'Desembolso confirmado',
      filtroCelda: {
        campo: 'etapa',
        valor: 'desembolsadas',
        etiqueta: 'Desembolsadas',
      },
      delta: deltas.desembolsadas ?? null,
      serie: series.desembolsadas,
      icono: HandCoins,
      chip: 'bg-slate-100 text-[#176b46] ring-slate-400/30',
      activo: filtro?.campo === 'etapa' && filtro.valor === 'desembolsadas',
    },
  ]
  return (
    <div className="card overflow-hidden" aria-busy={cargando}>
      <div className="grid grid-cols-2 lg:grid-cols-4">
        {celdas.map((c) => {
          const Icono = c.icono
          return (
            <button
              key={c.label}
              type="button"
              aria-pressed={c.activo}
              onClick={() => setFiltro(c.activo ? null : c.filtroCelda)}
              title={
                c.filtroCelda == null
                  ? 'Ver todas las solicitudes'
                  : `Filtrar: ${c.label}`
              }
              className="border-slate-100 p-1.5 text-left transition focus-visible:outline-2 focus-visible:outline-brand-500 max-lg:[&:nth-child(odd)]:border-r max-lg:[&:nth-child(n+3)]:border-t lg:[&:nth-child(n+2)]:border-l"
            >
              {/* Selección como relleno flotante interior (patrón
                  dashboard-design): tinte suave + ring inset, sin tocar
                  las divisiones de la banda. */}
              <span
                className={`block h-full rounded-lg px-3 py-3 transition sm:px-3.5 ${
                  c.activo
                    ? 'bg-brand-500/[.07] ring-1 ring-inset ring-brand-500/25'
                    : 'hover:bg-slate-50'
                }`}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    {c.label}
                  </span>
                  <span
                    className={`grid h-7 w-7 shrink-0 place-items-center rounded-lg ring-1 ${c.chip}`}
                    aria-hidden="true"
                  >
                    <Icono size={14} />
                  </span>
                </span>
                {cargando ? (
                  <span className="mt-1.5 block h-8 w-16 animate-pulse rounded bg-slate-200" />
                ) : (
                  <span className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-2xl font-bold tracking-tight tabular-nums text-slate-900 sm:text-3xl">
                      {number(c.valor)}
                    </span>
                    <BadgeDelta delta={c.delta} />
                  </span>
                )}
                <span className="mt-0.5 block truncate text-xs text-slate-500">
                  {c.detalle}
                </span>
                {cargando ? (
                  <span className="mt-2 block h-7 w-full animate-pulse rounded bg-slate-100" />
                ) : (
                  <Sparkline
                    serie={c.serie}
                    color={c.activo ? '#099dd7' : '#94a3b8'}
                    className="mt-2 block h-7 w-full"
                  />
                )}
              </span>
            </button>
          )
        })}
      </div>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 border-t border-slate-100 px-5 py-3 text-xs text-slate-500">
        {cargando ? (
          <span className="h-4 w-72 animate-pulse rounded bg-slate-200" />
        ) : (
          <>
            <span>
              Monto aprobado{' '}
              <strong className="font-semibold text-slate-800">
                {currency(Math.round(montoAprobado))}
              </strong>
            </span>
            <span>
              Colocado{' '}
              <strong className="font-semibold text-slate-800">
                {currency(Math.round(cupoColocado))}
              </strong>
            </span>
            <span>
              Capacidad de pago prom.{' '}
              <strong className="font-semibold text-slate-800">
                {currency(Math.round(capacidadPromedio))}
              </strong>
            </span>
            <span>
              Ticket prom. aprobado{' '}
              <strong className="font-semibold text-slate-800">
                {currency(Math.round(ticketPromedio))}
              </strong>
            </span>
            <span>
              Radicadas hoy{' '}
              <strong className="font-semibold text-slate-800 tabular-nums">
                {radicadasHoy}
              </strong>
            </span>
            <button
              type="button"
              onClick={() =>
                setFiltro(
                  filtro?.campo === 'estado' && filtro.valor === 'RECHAZADO'
                    ? null
                    : {
                        campo: 'estado',
                        valor: 'RECHAZADO',
                        etiqueta: 'Rechazadas',
                      },
                )
              }
              aria-pressed={
                filtro?.campo === 'estado' && filtro.valor === 'RECHAZADO'
              }
              title="Filtrar rechazadas"
              className={`rounded px-1 -mx-1 transition hover:bg-slate-100 ${
                filtro?.campo === 'estado' && filtro.valor === 'RECHAZADO'
                  ? 'bg-red-50 text-red-700'
                  : ''
              }`}
            >
              Rechazadas{' '}
              <strong className="font-semibold">
                {number(rechazadas)} ({tasaRechazo.toFixed(1)}%)
              </strong>
            </button>
          </>
        )}
      </div>
    </div>
  )
}

/** Panel de lista rankeada (patrón "Sources/Pages" de la referencia):
    etiqueta + valor + share a la derecha y una pista delgada de 3px
    en el borde inferior de cada fila — magnitud sin bloques de color. */
function PanelRanking({
  titulo,
  items,
  total,
  cargando,
  vacio,
}: {
  titulo: string
  items: { label: string; valor: number }[]
  total: number
  cargando: boolean
  vacio: string
}) {
  const max = Math.max(1, ...items.map((i) => i.valor))
  return (
    <Tarjeta>
      <h3 className="font-semibold text-slate-900 mb-1">{titulo}</h3>
      <div
        role="img"
        aria-label={`${titulo}: ${items.map((i) => `${i.label}: ${i.valor}`).join(', ')}`}
      >
        {cargando ? (
          <div className="space-y-3 pt-2" aria-hidden="true">
            {[100, 85, 70].map((w) => (
              <div
                key={w}
                className="h-8 animate-pulse rounded-lg bg-slate-200"
                style={{ width: `${w}%` }}
              />
            ))}
          </div>
        ) : items.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">{vacio}</p>
        ) : (
          items.slice(0, 7).map((i) => {
            const pct = total ? Math.round((i.valor / total) * 100) : 0
            return (
              <div
                key={i.label}
                className="relative flex items-baseline gap-x-3 px-3 pb-3 pt-2 text-sm"
              >
                <span className="min-w-0 flex-1 truncate text-slate-700">
                  {i.label}
                </span>
                <span className="tabular-nums font-semibold text-slate-900">
                  {number(i.valor)}
                </span>
                <span className="tabular-nums w-9 text-right text-xs text-slate-400">
                  {pct}%
                </span>
                <span
                  className="absolute inset-x-3 bottom-0 h-[3px] overflow-hidden rounded-full bg-slate-100"
                  aria-hidden="true"
                >
                  <span
                    className="block h-full rounded-full bg-brand-400"
                    style={{ width: `${(i.valor / max) * 100}%` }}
                  />
                </span>
              </div>
            )
          })
        )}
      </div>
    </Tarjeta>
  )
}
