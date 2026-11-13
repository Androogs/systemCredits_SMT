/**
 * Bandeja de operaciones: paso facturada → desembolsada.
 *
 * Tarjeta A — facturadas listas para desembolsar: exporta las
 * garantías al RNGM (archivo plano .txt de RUNTPRO) y marca el
 * desembolso en bloque una vez radicado el cargue. El giro (cuenta +
 * referencia) llega por webhook de tesorería o desde el detalle.
 *
 * Tarjeta B — aprobadas pendientes de factura: contexto de la cola
 * (el asesor aún no ha cargado la factura del vehículo).
 *
 * Roles: admin y contabilidad (guard de ruta + 403 del backend).
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  AlertTriangle,
  Banknote,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  FileUp,
  Loader2,
} from 'lucide-react'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import { FilasSkeleton } from '../shared/ui/Skeleton'
import InsigniaEstado from '../entities/credit/ui/InsigniaEstado'
import { currency, dateShort } from '../shared/lib/formatters'
import { emitirToast } from '../shared/lib/toastBus'
import {
  estadoParaVista,
  etiquetaSolicitud,
  numero,
} from '../entities/credit/model/solicitudesPanel'
import {
  ApiError,
  type SolicitudResumenApi,
} from '../features/credit-origination/api/originacionApi'
import {
  advertenciasGarantiasRunt,
  cargarGarantiasRuntExcel,
  contarSolicitudes,
  descargarGarantiasRunt,
  desembolsoMasivo,
  listarBandeja,
} from '../features/desembolsos/api/desembolsosApi'

const POR_PAGINA_FACTURADAS = 25
const POR_PAGINA_PENDIENTES = 10

function mensajeError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status === 0
      ? 'No fue posible contactar el servidor. Verifica tu conexión.'
      : error.message
  }
  return error instanceof Error ? error.message : 'Error inesperado'
}

interface PaginacionProps {
  pagina: number
  totalPaginas: number
  desde: number
  visibles: number
  total: number
  onCambiar: (pagina: number) => void
}

function Paginacion({
  pagina,
  totalPaginas,
  desde,
  visibles,
  total,
  onCambiar,
}: PaginacionProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-3 text-sm text-slate-600">
      <p aria-live="polite">
        Mostrando {visibles > 0 ? desde + 1 : 0}–{desde + visibles} de {total}
      </p>
      <div className="flex items-center gap-1">
        <button
          type="button"
          className="btn-ghost !px-2 !py-1.5"
          aria-label="Página anterior"
          disabled={pagina <= 1}
          onClick={() => onCambiar(pagina - 1)}
        >
          <ChevronLeft size={16} />
        </button>
        <span className="min-w-16 text-center text-xs">
          {pagina} / {totalPaginas}
        </span>
        <button
          type="button"
          className="btn-ghost !px-2 !py-1.5"
          aria-label="Página siguiente"
          disabled={pagina >= totalPaginas}
          onClick={() => onCambiar(pagina + 1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

export default function Desembolsos() {
  const queryClient = useQueryClient()
  const [paginaA, setPaginaA] = useState(1)
  const [paginaB, setPaginaB] = useState(1)
  // La selección es un Set de ids que persiste al cambiar de página.
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set())
  // Filas que fallaron en el último masivo: icono de alerta + tooltip.
  const [errores, setErrores] = useState<Map<string, string>>(new Map())
  const [confirmando, setConfirmando] = useState(false)
  const [incluirExportadas, setIncluirExportadas] = useState(false)
  // Cargue manual desde el registro Excel externo (garantías de
  // otras sedes radicadas fuera de la plataforma).
  const [archivoExcel, setArchivoExcel] = useState<File | null>(null)
  const [hojaExcel, setHojaExcel] = useState('2026')
  const [desdeExcel, setDesdeExcel] = useState('')
  const checkboxPaginaRef = useRef<HTMLInputElement>(null)

  // ---------- Datos: paginación server-side (lista + conteo separado) ----------
  const facturadas = useQuery({
    queryKey: ['desembolsos', 'facturadas', paginaA],
    queryFn: () =>
      listarBandeja(
        'facturada',
        POR_PAGINA_FACTURADAS,
        (paginaA - 1) * POR_PAGINA_FACTURADAS,
      ),
    placeholderData: keepPreviousData,
  })
  const conteoFacturadas = useQuery({
    queryKey: ['desembolsos', 'conteo', 'facturada'],
    queryFn: () => contarSolicitudes('facturada'),
    placeholderData: keepPreviousData,
  })
  const pendientes = useQuery({
    queryKey: ['desembolsos', 'aprobada', paginaB],
    queryFn: () =>
      listarBandeja(
        'aprobada',
        POR_PAGINA_PENDIENTES,
        (paginaB - 1) * POR_PAGINA_PENDIENTES,
      ),
    placeholderData: keepPreviousData,
  })
  const conteoPendientes = useQuery({
    queryKey: ['desembolsos', 'conteo', 'aprobada'],
    queryFn: () => contarSolicitudes('aprobada'),
    placeholderData: keepPreviousData,
  })

  const filasA = useMemo(() => facturadas.data ?? [], [facturadas.data])
  const totalA = conteoFacturadas.data?.total ?? 0
  const totalPaginasA = Math.max(1, Math.ceil(totalA / POR_PAGINA_FACTURADAS))
  const filasB = pendientes.data ?? []
  const totalB = conteoPendientes.data?.total ?? 0
  const totalPaginasB = Math.max(1, Math.ceil(totalB / POR_PAGINA_PENDIENTES))

  // Si la página queda vacía tras un masivo, retroceder a la última
  // con filas (sin pedir otra vez la página que ya no existe).
  useEffect(() => {
    if (
      !facturadas.isPending &&
      !facturadas.isPlaceholderData &&
      filasA.length === 0 &&
      paginaA > 1
    ) {
      setPaginaA((p) => Math.max(1, Math.min(p - 1, totalPaginasA)))
    }
  }, [
    facturadas.isPending,
    facturadas.isPlaceholderData,
    filasA.length,
    paginaA,
    totalPaginasA,
  ])

  // ---------- Selección ----------
  const idsPagina = useMemo(() => filasA.map((s) => s.id_solicitud), [filasA])
  const seleccionPagina = idsPagina.filter((id) => seleccion.has(id))
  const todaPagina =
    idsPagina.length > 0 && seleccionPagina.length === idsPagina.length
  const parcialPagina = seleccionPagina.length > 0 && !todaPagina
  useEffect(() => {
    if (checkboxPaginaRef.current) {
      checkboxPaginaRef.current.indeterminate = parcialPagina
    }
  }, [parcialPagina])

  const alternarPagina = useCallback(() => {
    setSeleccion((prev) => {
      const next = new Set(prev)
      if (todaPagina) idsPagina.forEach((id) => next.delete(id))
      else idsPagina.forEach((id) => next.add(id))
      return next
    })
  }, [idsPagina, todaPagina])

  const alternarFila = useCallback((id: string) => {
    setSeleccion((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const seleccionarTodas = useCallback(async () => {
    // Todas las facturadas de la bandeja (no solo la página): el límite
    // del endpoint (200) coincide con el tope del payload del masivo.
    try {
      const todas = await queryClient.fetchQuery({
        queryKey: ['desembolsos', 'facturadas', 'todas'],
        queryFn: () => listarBandeja('facturada', 200, 0),
      })
      setSeleccion((prev) => {
        const next = new Set(prev)
        todas.forEach((s) => next.add(s.id_solicitud))
        return next
      })
      if (totalA > todas.length) {
        emitirToast({
          tipo: 'info',
          mensaje: `Se seleccionaron ${todas.length} de ${totalA} facturadas (el lote admite hasta 200).`,
        })
      }
    } catch (e) {
      emitirToast({ tipo: 'error', mensaje: mensajeError(e) })
    }
  }, [queryClient, totalA])

  // ---------- Desembolso masivo ----------
  const masivo = useMutation({
    mutationFn: (ids: string[]) => desembolsoMasivo(ids),
    onSuccess: (respuesta) => {
      const fallidas = new Map<string, string>()
      const ok = new Set<string>()
      for (const r of respuesta.resultados) {
        if (r.ok) ok.add(r.id_solicitud)
        else fallidas.set(r.id_solicitud, r.error ?? 'Error desconocido')
      }
      setErrores(fallidas)
      setSeleccion((prev) => {
        const next = new Set(prev)
        ok.forEach((id) => next.delete(id))
        return next
      })
      if (respuesta.fallidas === 0) {
        emitirToast({
          tipo: 'exito',
          mensaje: `${respuesta.procesadas} solicitudes marcadas como desembolsadas.`,
        })
      } else {
        emitirToast({
          tipo: 'info',
          mensaje: `Desembolso parcial: ${respuesta.procesadas} procesadas, ${respuesta.fallidas} fallidas. Revisa las filas marcadas.`,
        })
      }
      queryClient.invalidateQueries({ queryKey: ['desembolsos'] })
      queryClient.invalidateQueries({ queryKey: ['solicitudes'] })
    },
    onError: (e) => {
      emitirToast({ tipo: 'error', mensaje: mensajeError(e) })
    },
    onSettled: () => setConfirmando(false),
  })

  // ---------- Export RUNTPRO (archivo plano RNGM) ----------
  const exportRunt = useMutation({
    mutationFn: (incluir: boolean) => descargarGarantiasRunt(incluir),
    onSuccess: async (r) => {
      emitirToast({
        tipo: 'exito',
        mensaje: `Archivo ${r.nombreArchivo} descargado: ${r.garantias} garantías${r.advertencias > 0 ? `, ${r.advertencias} advertencias (se descargó advertencias_rngm.csv)` : ''}.`,
      })
      if (r.advertencias > 0) {
        // Segunda descarga: el checklist de campos por revisar antes
        // de radicar el .txt en RUNTPRO (vista previa del lote).
        try {
          const previa = await advertenciasGarantiasRunt(true)
          const filas = [
            'N° SOLICITUD,CLIENTE,CÉDULA,ADVERTENCIA',
            ...previa.advertencias.map((a) =>
              [a.num_solicitud ?? '', a.cliente, a.cedula, a.mensaje]
                .map((v) => `"${String(v).replace(/"/g, '""')}"`)
                .join(','),
            ),
          ]
          const blob = new Blob([filas.join('\r\n')], {
            type: 'text/csv;charset=utf-8',
          })
          const obj = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = obj
          a.download = 'advertencias_rngm.csv'
          a.click()
          setTimeout(() => URL.revokeObjectURL(obj), 10_000)
        } catch {
          // La lista también queda en /api/cargas/garantias-runtpro/advertencias.
        }
      }
      // Las filas exportadas siguen siendo facturadas, pero un segundo
      // clic ya no las repite: refresca el conteo de pendientes.
      queryClient.invalidateQueries({ queryKey: ['desembolsos'] })
    },
    onError: (e) => {
      // 404 = sin pendientes: informativo, no error de red.
      emitirToast({
        tipo: e instanceof ApiError && e.status === 404 ? 'info' : 'error',
        mensaje: mensajeError(e),
      })
    },
  })

  // ---------- Cargue manual desde el registro Excel externo ----------
  const cargueExcel = useMutation({
    mutationFn: (formato: 'txt' | 'excel') =>
      cargarGarantiasRuntExcel(archivoExcel as File, {
        hoja: hojaExcel.trim() || undefined,
        desde: desdeExcel ? Number(desdeExcel) : undefined,
        formato,
      }),
    onSuccess: (r, formato) => {
      emitirToast({
        tipo: 'exito',
        mensaje:
          formato === 'txt'
            ? `Plano ${r.nombreArchivo} descargado: ${r.garantias} garantías` +
              (r.advertencias > 0
                ? `, ${r.advertencias} advertencias — revisa la hoja de revisión.`
                : '.')
            : `Hoja de revisión ${r.nombreArchivo} descargada.`,
      })
    },
    onError: (e) => {
      emitirToast({
        tipo: e instanceof ApiError && e.status === 404 ? 'info' : 'error',
        mensaje: mensajeError(e),
      })
    },
  })

  const errorA = facturadas.error ?? conteoFacturadas.error
  const errorB = pendientes.error ?? conteoPendientes.error

  return (
    <>
      <Encabezado
        title="Desembolsos"
        subtitle="Facturadas listas para girar y cargue de garantías al RNGM (RUNTPRO)"
      />
      <div className="p-6 space-y-4 overflow-auto">
        {/* ---------- A) Facturadas listas para desembolsar ---------- */}
        <Tarjeta className="p-0 ring-1 ring-emerald-300 border-emerald-200">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-emerald-200 bg-emerald-50/50 px-5 py-3 rounded-t-[inherit]">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Facturadas listas para desembolsar
              </h2>
              <p className="text-xs text-slate-500">
                {totalA} en la bandeja · selecciona y marca el giro tras radicar
                el cargue en RUNTPRO
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="btn-ghost inline-flex items-center gap-2"
                disabled={exportRunt.isPending}
                onClick={() => exportRunt.mutate(incluirExportadas)}
                title="Descarga el archivo plano .txt RNGM para el cargue masivo en RUNTPRO"
              >
                {exportRunt.isPending ? (
                  <Loader2
                    size={15}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <FileSpreadsheet size={15} aria-hidden="true" />
                )}
                Garantías RUNT Pro
              </button>
              <label className="inline-flex items-center gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  checked={incluirExportadas}
                  onChange={(e) => setIncluirExportadas(e.target.checked)}
                />
                Incluir ya exportadas
              </label>
            </div>
          </div>

          {seleccion.size > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-brand-50/40 px-5 py-2.5">
              <p className="text-sm text-slate-700" role="status">
                <strong>{seleccion.size}</strong> seleccionadas
                <button
                  type="button"
                  className="ml-3 text-xs text-brand-700 underline underline-offset-2"
                  onClick={() => setSeleccion(new Set())}
                >
                  Limpiar
                </button>
              </p>
              <div className="flex items-center gap-2">
                {!confirmando ? (
                  <>
                    <button
                      type="button"
                      className="btn-ghost text-xs"
                      onClick={seleccionarTodas}
                    >
                      Seleccionar todas
                    </button>
                    <button
                      type="button"
                      className="btn-primary inline-flex items-center gap-2"
                      onClick={() => setConfirmando(true)}
                    >
                      <Banknote size={15} aria-hidden="true" />
                      Marcar desembolsadas
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="btn-ghost text-xs"
                      disabled={masivo.isPending}
                      onClick={() => setConfirmando(false)}
                    >
                      Volver
                    </button>
                    <button
                      type="button"
                      className="btn-primary inline-flex items-center gap-2"
                      disabled={masivo.isPending}
                      onClick={() => masivo.mutate([...seleccion])}
                    >
                      {masivo.isPending ? (
                        <Loader2
                          size={15}
                          className="animate-spin"
                          aria-hidden="true"
                        />
                      ) : (
                        <CheckCheck size={15} aria-hidden="true" />
                      )}
                      Confirmar desembolso masivo ({seleccion.size})
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {errorA && (
            <p role="alert" className="px-5 py-6 text-sm text-red-700">
              No se pudieron cargar las facturadas: {mensajeError(errorA)}
            </p>
          )}

          {!errorA && (
            <div
              className="overflow-x-auto"
              role="region"
              aria-label="Solicitudes facturadas pendientes de desembolso"
              tabIndex={0}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                    <th scope="col" className="px-4 py-3 w-10">
                      <input
                        ref={checkboxPaginaRef}
                        type="checkbox"
                        aria-label="Seleccionar página"
                        checked={todaPagina}
                        onChange={alternarPagina}
                      />
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Solicitud
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Cliente
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Sede
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Radicada
                    </th>
                    <th scope="col" className="px-5 py-3 text-right">
                      Monto
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Estado
                    </th>
                  </tr>
                </thead>
                <tbody aria-busy={facturadas.isPending}>
                  {filasA.map((s) => {
                    const errorFila = errores.get(s.id_solicitud)
                    const monto = numero(s.monto_aprobado)
                    return (
                      <tr
                        key={s.id_solicitud}
                        className={`border-b border-slate-100 hover:bg-slate-50 ${
                          seleccion.has(s.id_solicitud) ? 'bg-brand-50/30' : ''
                        }`}
                      >
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5">
                            <input
                              type="checkbox"
                              aria-label={`Seleccionar ${etiquetaSolicitud(s)}`}
                              checked={seleccion.has(s.id_solicitud)}
                              onChange={() => alternarFila(s.id_solicitud)}
                            />
                            {errorFila && (
                              <AlertTriangle
                                size={14}
                                className="text-amber-600"
                                aria-label={`Error en el último desembolso: ${errorFila}`}
                              />
                            )}
                          </span>
                        </td>
                        <td className="px-5 py-3 font-medium">
                          <Link
                            to={`/solicitudes/${s.id_solicitud}`}
                            className="text-brand-600 hover:underline"
                          >
                            {etiquetaSolicitud(s)}
                          </Link>
                        </td>
                        <td className="px-5 py-3">
                          <div className="whitespace-nowrap">
                            {s.nombre_cliente}
                          </div>
                          <div className="text-xs text-slate-500">
                            {s.num_cedula}
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                          {s.nombre_concesionario ?? '—'}
                        </td>
                        <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                          {dateShort(s.fecha_hora)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {monto != null ? currency(monto) : '—'}
                        </td>
                        <td className="px-5 py-3">
                          <InsigniaEstado status={estadoParaVista(s)} />
                        </td>
                      </tr>
                    )
                  })}
                  {!facturadas.isPending && filasA.length === 0 && (
                    <tr>
                      <td
                        colSpan={7}
                        className="px-5 py-10 text-center text-slate-500"
                      >
                        No hay solicitudes facturadas pendientes de desembolso
                      </td>
                    </tr>
                  )}
                  {facturadas.isPending && (
                    <FilasSkeleton filas={6} columnas={7} />
                  )}
                </tbody>
              </table>
            </div>
          )}
          {!errorA && totalA > 0 && (
            <Paginacion
              pagina={paginaA}
              totalPaginas={totalPaginasA}
              desde={(paginaA - 1) * POR_PAGINA_FACTURADAS}
              visibles={filasA.length}
              total={totalA}
              onCambiar={setPaginaA}
            />
          )}
        </Tarjeta>

        {/* ---------- Cargue manual desde registro Excel ---------- */}
        <Tarjeta className="p-0 ring-1 ring-brand-200 border-brand-100">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-brand-100 bg-brand-50/50 px-5 py-3 rounded-t-[inherit]">
            <div>
              <h2 className="text-sm font-semibold text-slate-900">
                Cargue desde registro Excel
              </h2>
              <p className="text-xs text-slate-500">
                Garantías radicadas por fuera de la plataforma: toma las filas
                con estado PENDIENTE de la hoja y genera el plano RNGM a nombre
                de SUMOTO S.A (NIT 800.235.505-9)
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn-primary inline-flex items-center gap-2"
                disabled={!archivoExcel || cargueExcel.isPending}
                onClick={() => cargueExcel.mutate('txt')}
                title="Descarga el archivo plano .txt RNGM para radicar en RUNTPRO"
              >
                {cargueExcel.isPending ? (
                  <Loader2
                    size={15}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <FileUp size={15} aria-hidden="true" />
                )}
                Generar plano .txt
              </button>
              <button
                type="button"
                className="btn-ghost inline-flex items-center gap-2"
                disabled={!archivoExcel || cargueExcel.isPending}
                onClick={() => cargueExcel.mutate('excel')}
                title="Descarga la hoja de revisión (Garantías + Advertencias)"
              >
                <FileSpreadsheet size={15} aria-hidden="true" />
                Revisión
              </button>
            </div>
          </div>
          <div className="flex flex-wrap items-end gap-4 px-5 py-4">
            <label className="flex min-w-64 flex-1 flex-col gap-1 text-xs text-slate-600">
              Archivo de registro (.xlsx)
              <input
                type="file"
                accept=".xlsx,.xlsm,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                className="block w-full text-sm text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-brand-700 hover:file:bg-brand-100"
                onChange={(e) => setArchivoExcel(e.target.files?.[0] ?? null)}
              />
            </label>
            <label className="flex w-24 flex-col gap-1 text-xs text-slate-600">
              Hoja
              <input
                type="text"
                value={hojaExcel}
                onChange={(e) => setHojaExcel(e.target.value)}
                className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                placeholder="2026"
              />
            </label>
            <label className="flex w-28 flex-col gap-1 text-xs text-slate-600">
              Desde fila
              <input
                type="number"
                min={1}
                value={desdeExcel}
                onChange={(e) => setDesdeExcel(e.target.value)}
                className="rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm"
                placeholder="1"
              />
            </label>
          </div>
        </Tarjeta>

        {/* ---------- B) Aprobadas pendientes de factura (contexto) ---------- */}
        <Tarjeta className="p-0">
          <div className="border-b border-slate-200 px-5 py-3">
            <h2 className="text-sm font-semibold text-slate-900">
              Aprobadas pendientes de factura
            </h2>
            <p className="text-xs text-slate-500">
              {totalB} esperando que el asesor cargue la factura del vehículo
              (solo contexto — no son seleccionables)
            </p>
          </div>
          {errorB && (
            <p role="alert" className="px-5 py-6 text-sm text-red-700">
              No se pudieron cargar las aprobadas: {mensajeError(errorB)}
            </p>
          )}
          {!errorB && (
            <div
              className="overflow-x-auto"
              role="region"
              aria-label="Solicitudes aprobadas sin factura"
              tabIndex={0}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                    <th scope="col" className="px-5 py-3">
                      Solicitud
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Cliente
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Sede
                    </th>
                    <th scope="col" className="px-5 py-3">
                      Radicada
                    </th>
                    <th scope="col" className="px-5 py-3 text-right">
                      Monto
                    </th>
                  </tr>
                </thead>
                <tbody aria-busy={pendientes.isPending}>
                  {filasB.map((s: SolicitudResumenApi) => {
                    const monto = numero(s.monto_aprobado)
                    return (
                      <tr
                        key={s.id_solicitud}
                        className="border-b border-slate-100 hover:bg-slate-50"
                      >
                        <td className="px-5 py-3 font-medium">
                          <Link
                            to={`/solicitudes/${s.id_solicitud}`}
                            className="text-brand-600 hover:underline"
                          >
                            {etiquetaSolicitud(s)}
                          </Link>
                        </td>
                        <td className="px-5 py-3">
                          <div className="whitespace-nowrap">
                            {s.nombre_cliente}
                          </div>
                          <div className="text-xs text-slate-500">
                            {s.num_cedula}
                          </div>
                        </td>
                        <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                          {s.nombre_concesionario ?? '—'}
                        </td>
                        <td className="px-5 py-3 text-slate-600 whitespace-nowrap">
                          {dateShort(s.fecha_hora)}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {monto != null ? currency(monto) : '—'}
                        </td>
                      </tr>
                    )
                  })}
                  {!pendientes.isPending && filasB.length === 0 && (
                    <tr>
                      <td
                        colSpan={5}
                        className="px-5 py-10 text-center text-slate-500"
                      >
                        No hay solicitudes aprobadas sin factura
                      </td>
                    </tr>
                  )}
                  {pendientes.isPending && (
                    <FilasSkeleton filas={4} columnas={5} />
                  )}
                </tbody>
              </table>
            </div>
          )}
          {!errorB && totalB > 0 && (
            <Paginacion
              pagina={paginaB}
              totalPaginas={totalPaginasB}
              desde={(paginaB - 1) * POR_PAGINA_PENDIENTES}
              visibles={filasB.length}
              total={totalB}
              onCambiar={setPaginaB}
            />
          )}
        </Tarjeta>
      </div>
    </>
  )
}
