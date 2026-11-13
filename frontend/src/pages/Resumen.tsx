import { useState, useEffect, useMemo, lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import Sparkline from '../shared/ui/Sparkline'
import Skeleton from '../shared/ui/Skeleton'
import { currency, number } from '../shared/lib/formatters'

import { useRol, useUsuario } from '../shared/lib/sesion'
import {
  estadoParaVista,
  ESTADOS_POSITIVOS_VISTA,
  numero,
  OCUPACION_LABELS,
  PERFIL_INGRESO_LABELS,
  TIPO_CONTRATO_LABELS,
  useSolicitudes,
} from '../entities/credit/model/solicitudesPanel'
import type {
  FiltrosSolicitudes,
  SolicitudResumenApi,
} from '../features/credit-origination/api/originacionApi'
import TablaSolicitudesPanel from '../widgets/dashboard/TablaSolicitudesPanel'
import BarraFiltrosDimensionales, {
  coincideMarcaSede,
  type DimensionesPanel,
} from '../widgets/dashboard/BarraFiltrosDimensionales'
import AccionesRapidas from '../widgets/dashboard/AccionesRapidas'
import {
  CircleCheck,
  Clock3,
  FileText,
  Plus,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  X,
  type LucideIcon,
} from 'lucide-react'
import type { FiltroPanel } from '../widgets/dashboard/GraficasResumen'
import EmbudoOriginacion, {
  PanelCausalesRechazo,
  PanelTopAsesores,
} from '../widgets/dashboard/EmbudoOriginacion'
import {
  PanelPerfilCliente,
  PanelRanking,
} from '../widgets/dashboard/PanelesResumen'
import {
  distribuir,
  marcaDe,
  promedio,
  MARCAS_CATALOGO,
  RANGOS_CONTINUIDAD,
  RANGOS_CUOTA,
  RANGOS_MONTO,
  RANGOS_PLAZO,
  SIN_MARCA,
} from '../widgets/dashboard/analiticaPortafolio'

const DonaEstados = lazy(() =>
  import('../widgets/dashboard/GraficasResumen').then((m) => ({
    default: m.DonaEstados,
  })),
)
const TendenciaSeisMeses = lazy(() =>
  import('../widgets/dashboard/GraficasResumen').then((m) => ({
    default: m.TendenciaSeisMeses,
  })),
)

const STATUS_COLORS = {
  APROBADO: '#10b981',
  EN_PROCESO: '#0052a1',
  FACTURADO: '#2f74c0',
  DESEMBOLSADO: '#176b46',
  FINALIZADO: '#64748b',
  RECHAZADO: '#ef4444',
  PENDIENTE: '#94a3b8',
} as const

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
  // "Aprobadas" del KPI cubre todo el pipeline positivo (en proceso,
  // aprobada, facturada, desembolsada), no solo el hito visual APROBADO.
  if (filtro.campo === 'estado')
    return filtro.valor === 'APROBADO'
      ? ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s))
      : estadoParaVista(s) === filtro.valor
  if (filtro.campo === 'ocupacion') return s.ocupacion === filtro.valor
  if (filtro.campo === 'etapa') {
    if (filtro.valor === 'evaluadas') return s.decision != null
    if (filtro.valor === 'formalizadas') return s.fecha_hora_firma != null
    return true
  }
  if (filtro.campo === 'dia') {
    const [anio, mes, dia] = filtro.valor.split('-').map(Number)
    const d = new Date(s.fecha_hora)
    return (
      d.getFullYear() === anio && d.getMonth() === mes && d.getDate() === dia
    )
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
}

export default function Resumen() {
  const rol = useRol()
  const usuario = useUsuario()
  const primerNombre = usuario?.nombre.trim().split(/\s+/)[0]
  const vistaBinaria = rol !== 'admin'
  // Filtros dimensionales (concesionario/asesor): viajan al servidor y
  // recalculan KPIs, gráficas, embudo y tabla a la vez. Los tiene el
  // admin (todo) y el aliado (sus sedes, para comisiones); el asesor
  // no — su alcance ya es solo lo que radicó él.
  // Filtros de sede/asesor: admin los cruza, el aliado reporta
  // comisiones por radicador y el concesionario filtra su propia sede.
  const conDimensiones =
    rol === 'admin' || rol === 'aliado' || rol === 'concesionario'
  const [dimensiones, setDimensiones] = useState<DimensionesPanel>({})
  const filtrosLista: FiltrosSolicitudes = conDimensiones
    ? { limite: 200, ...dimensiones }
    : { limite: 200, orden: 'prioridad' }
  const {
    datos: solicitudesTodas,
    cargando,
    error,
    recargar,
    actualizadoEn,
    sincronizando,
  } = useSolicitudes(filtrosLista, { refetchIntervalMs: REFRESCO_MS })
  // La marca/sede del panel es catálogo local: se filtra en cliente
  // sobre el nombre del concesionario (marca sin sede acumula todas
  // las sedes de esa marca en KPIs, gráficas y tabla).
  const solicitudes = dimensiones.marca
    ? solicitudesTodas.filter((s) =>
        coincideMarcaSede(
          s.nombre_concesionario,
          dimensiones.marca,
          dimensiones.sede,
        ),
      )
    : solicitudesTodas
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

  // El filtro de mes/día acota el embudo en el servidor (agregados
  // reales, no derivados de las 200 filas del listado).
  const rangoEmbudo =
    filtro?.campo === 'mes'
      ? (() => {
          const [anio, mes] = filtro.valor.split('-').map(Number)
          return {
            desde: new Date(anio, mes, 1).toISOString(),
            hasta: new Date(anio, mes + 1, 1).toISOString(),
          }
        })()
      : filtro?.campo === 'dia'
        ? (() => {
            const [anio, mes, dia] = filtro.valor.split('-').map(Number)
            return {
              desde: new Date(anio, mes, dia).toISOString(),
              hasta: new Date(anio, mes, dia + 1).toISOString(),
            }
          })()
        : null

  // Con filtro de mes/día activo, KPIs y gráficas recalculan sobre ese
  // periodo; la tendencia conserva todos los datos como selector.
  const base =
    filtro?.campo === 'mes' || filtro?.campo === 'dia'
      ? solicitudes.filter((s) => coincideFiltro(s, filtro))
      : solicitudes

  const total = base.length
  const approved = base.filter((s) =>
    ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)),
  ).length
  const rejected = base.filter((s) => estadoParaVista(s) === 'RECHAZADO').length
  const pendientes = base.filter(
    (s) => estadoParaVista(s) === 'PENDIENTE',
  ).length

  const cupos = base
    .filter((s) => ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)))
    .map((s) => numero(s.evaluacion?.cupo_sugerido))
    .filter((n): n is number => n != null)
  const capacidades = base
    .map((s) => numero(s.evaluacion?.capacidad_pago))
    .filter((n): n is number => n != null)
  const avgCapacidad = capacidades.length
    ? capacidades.reduce((a, b) => a + b, 0) / capacidades.length
    : 0
  const sumaCupos = cupos.reduce((a, b) => a + b, 0)

  // La dona resume la decisión: todo el pipeline positivo (en proceso,
  // aprobada, facturada, desembolsada, finalizada) es "Aprobadas".
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

  // Vista diaria de la tendencia: últimos 30 días contra los 30 días
  // previos — misma semántica de comparación que la vista mensual.
  const dayBuckets = [...Array(30)].map((_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (29 - i))
    const ant = new Date(d)
    ant.setDate(ant.getDate() - 30)
    const mismoDia = (fecha: string, ref: Date) => {
      const f = new Date(fecha)
      return (
        f.getFullYear() === ref.getFullYear() &&
        f.getMonth() === ref.getMonth() &&
        f.getDate() === ref.getDate()
      )
    }
    return {
      range: d.toLocaleDateString('es-CO', {
        day: 'numeric',
        month: 'short',
      }),
      clave: `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`,
      count: solicitudes.filter((s) => mismoDia(s.fecha_hora, d)).length,
      anterior: solicitudes.filter((s) => mismoDia(s.fecha_hora, ant)).length,
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
    }
  >()
  for (const s of solicitudes) {
    const d = new Date(s.fecha_hora)
    const k = `${d.getFullYear()}-${d.getMonth()}`
    const acc = porMes.get(k) ?? {
      total: 0,
      aprobadas: 0,
      pendientes: 0,
    }
    acc.total += 1
    const ev = estadoParaVista(s)
    if (ESTADOS_POSITIVOS_VISTA.has(ev)) acc.aprobadas += 1
    else if (ev === 'PENDIENTE') acc.pendientes += 1
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
        delDia.filter((s) => ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)))
          .length,
      )
      acum.pendientes.push(
        delDia.filter((s) => estadoParaVista(s) === 'PENDIENTE').length,
      )
    }
    return acum
  }, [base, diasSerie])

  const porOcupacion = Object.entries(OCUPACION_LABELS)
    .map(([tipo, label]) => {
      const grupo = base.filter((s) => s.ocupacion === tipo)
      const aprobadas = grupo.filter((s) =>
        ESTADOS_POSITIVOS_VISTA.has(estadoParaVista(s)),
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
  // marca del concesionario, perfiles del motor (score e ingreso,
  // solo administrador), tipo de contrato, continuidad laboral y los
  // rangos monetarios (monto, plazo deseado y cuota total pactada).
  // Las 7 marcas siempre aparecen (con 0 si no tienen solicitudes),
  // ordenadas por volumen; lo que no es de ninguna marca va al final.
  const conteoMarca = base.reduce<Record<string, number>>((acc, s) => {
    const marca = marcaDe(s.nombre_concesionario)
    acc[marca] = (acc[marca] ?? 0) + 1
    return acc
  }, {})
  const porMarca = [
    ...MARCAS_CATALOGO.map((label) => ({
      label,
      valor: conteoMarca[label] ?? 0,
    })).sort((a, b) => b.valor - a.valor || a.label.localeCompare(b.label)),
    ...(conteoMarca[SIN_MARCA]
      ? [{ label: SIN_MARCA, valor: conteoMarca[SIN_MARCA] }]
      : []),
  ]

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

  const conteoIngreso = base.reduce<Record<string, number>>((acc, s) => {
    const p = s.evaluacion?.perfil_ingreso
    if (p) acc[p] = (acc[p] ?? 0) + 1
    return acc
  }, {})
  const porIngreso = Object.keys(PERFIL_INGRESO_LABELS)
    .concat(
      Object.keys(conteoIngreso).filter((k) => !(k in PERFIL_INGRESO_LABELS)),
    )
    .map((k) => ({
      label: PERFIL_INGRESO_LABELS[k] ?? k,
      valor: conteoIngreso[k] ?? 0,
    }))
    .filter((i) => i.valor > 0)

  const conteoContrato = base.reduce<Record<string, number>>((acc, s) => {
    const k = s.tipo_contrato || 'sin_dato'
    acc[k] = (acc[k] ?? 0) + 1
    return acc
  }, {})
  const porTipoContrato = Object.keys(TIPO_CONTRATO_LABELS)
    .concat('sin_dato')
    .map((k) => ({
      label: k === 'sin_dato' ? 'Sin dato' : (TIPO_CONTRATO_LABELS[k] ?? k),
      valor: conteoContrato[k] ?? 0,
    }))
    .filter((i) => i.valor > 0)

  const porContinuidad = distribuir(
    base.map((s) => s.meses_continuidad ?? null),
    RANGOS_CONTINUIDAD,
    'Sin dato',
  )

  // Rangos monetarios: promedio sobre las solicitudes que tienen el
  // dato (cupo aprobado / oferta elegida); el share usa ese subtotal.
  // El monto usa solo aprobadas, igual que "Monto aprobado" de la banda.
  const montos = cupos
  const cuotas = base
    .map((s) => numero(s.cuota_total))
    .filter((n): n is number => n != null)
  const plazos = base
    .map((s) => s.plazo_deseado_meses)
    .filter((n): n is number => n != null)
  const promMonto = promedio(montos)
  const promCuota = promedio(cuotas)
  const promPlazo = promedio(plazos)
  const porMonto = distribuir(montos, RANGOS_MONTO)
  const porCuota = distribuir(cuotas, RANGOS_CUOTA)
  const porPlazoRangos = distribuir(
    base.map((s) => s.plazo_deseado_meses ?? null),
    RANGOS_PLAZO,
    'Sin plazo',
  )

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

  const solicitudesFiltradas =
    filtro == null
      ? solicitudes
      : solicitudes.filter((s) => coincideFiltro(s, filtro))

  return (
    <>
      <Encabezado
        title={`${saludoDelDia()}${primerNombre ? `, ${primerNombre}` : ''}`}
        subtitle={
          vistaBinaria
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
                  {solicitudesFiltradas.length === 1 ? '' : 'es'} en la tabla
                  {vistaBinaria ? '.' : '; las gráficas se atenúan.'}
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

        {conDimensiones && (
          <BarraFiltrosDimensionales
            dimensiones={dimensiones}
            onCambiar={setDimensiones}
          />
        )}

        {rol === 'asesor' && <AccionesRapidas />}

        <BandaKpis
          cargando={cargando}
          total={total}
          aprobadas={approved}
          pendientes={pendientes}
          montoAprobado={sumaCupos}
          capacidadPromedio={avgCapacidad}
          rechazadas={rejected}
          ticketPromedio={ticketPromedio}
          radicadasHoy={radicadasHoy}
          deltas={deltas}
          series={serieKpi}
          filtro={filtro}
          setFiltro={setFiltro}
        />

        {rol === 'asesor' ? (
          /* Vista del asesor: solo su propio rendimiento (el backend ya
             acota las métricas a lo que radicó él). Solo los paneles
             del boceto: sin comparativa con otros asesores, sin marca,
             sin score/causales y sin la tabla de solicitudes. */
          <>
            <Suspense
              fallback={
                <Tarjeta>
                  <Skeleton className="h-64 w-full rounded-xl" />
                </Tarjeta>
              }
            >
              <TendenciaSeisMeses
                cargando={cargando}
                monthBuckets={monthBuckets}
                dayBuckets={dayBuckets}
                filtro={filtro}
                alternarFiltro={alternarFiltro}
              />
            </Suspense>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Suspense
                fallback={
                  <Tarjeta>
                    <Skeleton className="h-56 w-full rounded-xl" />
                  </Tarjeta>
                }
              >
                <DonaEstados
                  cargando={cargando}
                  byStatus={byStatus}
                  total={total}
                  filtro={filtro}
                  alternarFiltro={alternarFiltro}
                />
              </Suspense>
              <EmbudoOriginacion
                vistaBinaria
                rango={rangoEmbudo}
                concesionarioId={dimensiones.id_concesionario}
                asesorId={dimensiones.id_asesor}
                filtro={filtro}
                onFiltrar={filtrarPorEtapa}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <PanelPerfilCliente
                grupos={porOcupacion}
                total={total}
                cargando={cargando}
                filtro={filtro}
                alternarFiltro={alternarFiltro}
              />
              <PanelRanking
                titulo="Tipo de contrato"
                cargando={cargando}
                items={porTipoContrato}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <PanelRanking
                titulo="Monto aprobado"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promMonto != null ? currency(Math.round(promMonto)) : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porMonto}
                total={montos.length}
                vacio="Aún no hay cupos evaluados."
              />
              <PanelRanking
                titulo="Plazo deseado (meses)"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promPlazo != null ? `${Math.round(promPlazo)} meses` : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porPlazoRangos}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
              <PanelRanking
                titulo="Cuota total mensual"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promCuota != null ? currency(Math.round(promCuota)) : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porCuota}
                total={cuotas.length}
                vacio="Aún no hay cuotas pactadas."
              />
            </div>
          </>
        ) : vistaBinaria ? (
          /* Vista operativa (aliado/concesionario): embudo de su
             alcance + tabla completa con pendientes primero. La
             analítica de gestión (dona, tendencia, ocupación,
             rankings) queda para el administrador. */
          <>
            <EmbudoOriginacion
              vistaBinaria={false}
              rango={rangoEmbudo}
              concesionarioId={dimensiones.id_concesionario}
              asesorId={dimensiones.id_asesor}
              filtro={filtro}
              onFiltrar={filtrarPorEtapa}
            />
            {/* El aliado liquida comisiones por radicador y el
              concesionario sigue a sus asesores: conservan el ranking. */}
            <PanelTopAsesores
              rango={rangoEmbudo}
              concesionarioId={dimensiones.id_concesionario}
              asesorId={dimensiones.id_asesor}
            />
          </>
        ) : (
          <>
            {/* Tendencia de radicadas: ancho completo sobre la retícula. */}
            <Suspense
              fallback={
                <Tarjeta>
                  <Skeleton className="h-64 w-full rounded-xl" />
                </Tarjeta>
              }
            >
              <TendenciaSeisMeses
                cargando={cargando}
                monthBuckets={monthBuckets}
                dayBuckets={dayBuckets}
                filtro={filtro}
                alternarFiltro={alternarFiltro}
              />
            </Suspense>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <Suspense
                fallback={
                  <Tarjeta>
                    <Skeleton className="h-56 w-full rounded-xl" />
                  </Tarjeta>
                }
              >
                <DonaEstados
                  cargando={cargando}
                  byStatus={byStatus}
                  total={total}
                  filtro={filtro}
                  alternarFiltro={alternarFiltro}
                />
              </Suspense>
              <EmbudoOriginacion
                vistaBinaria={vistaBinaria}
                rango={rangoEmbudo}
                concesionarioId={dimensiones.id_concesionario}
                asesorId={dimensiones.id_asesor}
                filtro={filtro}
                onFiltrar={filtrarPorEtapa}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <PanelRanking
                titulo="Distribución por marca"
                cargando={cargando}
                items={total > 0 ? porMarca : []}
                limite={porMarca.length}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
              <PanelTopAsesores
                rango={rangoEmbudo}
                concesionarioId={dimensiones.id_concesionario}
                asesorId={dimensiones.id_asesor}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <PanelPerfilCliente
                grupos={porOcupacion}
                total={total}
                cargando={cargando}
                filtro={filtro}
                alternarFiltro={alternarFiltro}
              />
              <PanelRanking
                titulo="Tipo de contrato"
                cargando={cargando}
                items={porTipoContrato}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
            </div>

            {/* El score es dato de administrador; junto al perfil de
              ingreso y la continuidad laboral completa el retrato del
              cliente que evalúa el motor. */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <PanelRanking
                titulo="Perfil de score"
                cargando={cargando}
                items={porScore}
                total={porScore.reduce((a, i) => a + i.valor, 0)}
                vacio="Aún no hay evaluaciones registradas."
              />
              <PanelRanking
                titulo="Perfil de ingreso"
                cargando={cargando}
                items={porIngreso}
                total={porIngreso.reduce((a, i) => a + i.valor, 0)}
                vacio="Aún no hay evaluaciones registradas."
              />
              <PanelRanking
                titulo="Continuidad laboral (meses)"
                cargando={cargando}
                items={porContinuidad}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <PanelRanking
                titulo="Monto aprobado"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promMonto != null ? currency(Math.round(promMonto)) : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porMonto}
                total={montos.length}
                vacio="Aún no hay cupos evaluados."
              />
              <PanelRanking
                titulo="Plazo deseado (meses)"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promPlazo != null ? `${Math.round(promPlazo)} meses` : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porPlazoRangos}
                total={total}
                vacio="Aún no hay solicitudes registradas."
              />
              <PanelRanking
                titulo="Cuota total mensual"
                resumen={
                  <ResumenPromedio
                    etiqueta="Promedio"
                    valor={
                      promCuota != null ? currency(Math.round(promCuota)) : '—'
                    }
                  />
                }
                cargando={cargando}
                items={porCuota}
                total={cuotas.length}
                vacio="Aún no hay cuotas pactadas."
              />
            </div>

            <PanelCausalesRechazo
              rango={rangoEmbudo}
              concesionarioId={dimensiones.id_concesionario}
              asesorId={dimensiones.id_asesor}
            />
          </>
        )}

        {/* La tabla no entra en la vista del asesor: su resumen es
            solo los indicadores del boceto. */}
        {rol !== 'asesor' && (
          <TablaSolicitudesPanel
            titulo={vistaBinaria ? 'Solicitudes' : 'Últimas solicitudes'}
            solicitudes={solicitudesFiltradas}
            cargando={cargando}
            mostrarScore={!vistaBinaria}
            mostrarAsesor={conDimensiones}
          />
        )}
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
  montoAprobado,
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
  montoAprobado: number
  capacidadPromedio: number
  rechazadas: number
  ticketPromedio: number
  radicadasHoy: number
  deltas: Record<string, number | null>
  series: {
    solicitudes: number[]
    aprobadas: number[]
    pendientes: number[]
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
      activo: filtro?.campo === 'estado' && filtro.valor === 'PENDIENTE',
    },
  ]
  return (
    <div className="card overflow-hidden" aria-busy={cargando}>
      <div className="grid grid-cols-1 sm:grid-cols-3">
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
                    className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600 ring-1 ring-brand-500/20"
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
                    color={c.activo ? '#0052a1' : '#94a3b8'}
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

/** Dato de contexto bajo el título de un panel de rangos (el promedio
    del monto, plazo o cuota sobre las solicitudes que lo tienen). */
function ResumenPromedio({
  etiqueta,
  valor,
}: {
  etiqueta: string
  valor: string
}) {
  return (
    <span className="text-xs text-slate-500">
      {etiqueta}{' '}
      <strong className="font-semibold text-slate-800">{valor}</strong>
    </span>
  )
}
