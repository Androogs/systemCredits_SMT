import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import CampoNumerico from '../shared/ui/CampoNumerico'
import Boton from '../shared/ui/Boton'
import { currency } from '../shared/lib/formatters'
import {
  cuotaAnualidad,
  tablaAmortizacion,
  tasaProductoMv,
} from '../shared/lib/finanzas'
import { useCuentaAscendente } from '../shared/lib/useCuentaAscendente'
import {
  listarProductos,
  tasaMercado,
  type ProductoApi,
} from '../features/credit-origination/api/originacionApi'
import {
  GASTOS_ADMINISTRATIVOS,
  PRIMA_SEGURO_VIDA_PCT,
  TASA_MENSUAL_REFERENCIA,
} from '../features/credit-origination/model/resultado-evaluacion'
import type { SimulacionPrevia } from '../features/credit-origination/model/borrador'
import { Calculator, ArrowRight, AlertTriangle, Landmark } from 'lucide-react'

// Rangos de referencia si el catálogo no está disponible (coinciden
// con el producto propio sembrado en la BD).
const RANGOS_FALLBACK = {
  tasaMin: 1.5,
  tasaMax: 2.2,
  plazoMin: 12,
  plazoMax: 48,
  montoMin: 500_000,
  montoMax: 20_000_000,
}

function plazosDel(min: number, max: number): number[] {
  const lista: number[] = []
  for (let p = min; p <= max; p += 12) lista.push(p)
  return lista
}

// Tasa comercial del producto: la usura de consumo y ordinario vigente
// (28,59% EA → (1+TEA)^(1/12)−1 = 2,1176% m.v. exacto) truncada a 4
// decimales, para quedar siempre un pelo por debajo del límite legal.
// Si la consulta SFC responde, la tasa operativa se recalcula en vivo.
const TASA_PRODUCTO = TASA_MENSUAL_REFERENCIA

const initial = {
  valorVehiculo: 10_000_000,
  cuotaInicial: 1_000_000,
  adicionales: 1_150_000,
  tasaMensual: TASA_PRODUCTO,
  plazoMeses: 48,
}

const DIAS_MES = 30

export default function Simulador() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initial)
  const consultaCatalogo = useQuery({
    queryKey: ['productos'],
    queryFn: listarProductos,
    staleTime: 5 * 60_000,
  })
  const producto: ProductoApi | null = consultaCatalogo.data?.[0] ?? null
  const catalogoError = consultaCatalogo.isError

  // Tasas oficiales SFC (datos.gov.co): referencia de usura y tope
  // legal del campo. El dataset es mensual; la lectura se cachea 6h
  // en el backend.
  const consultaTasa = useQuery({
    queryKey: ['tasa-mercado'],
    queryFn: tasaMercado,
    staleTime: 6 * 60 * 60_000,
    retry: 1,
  })

  const rangos = useMemo(
    () => ({
      tasaMin:
        producto?.tasa_min != null
          ? Number(producto.tasa_min)
          : RANGOS_FALLBACK.tasaMin,
      tasaMax:
        producto?.tasa_max != null
          ? Number(producto.tasa_max)
          : RANGOS_FALLBACK.tasaMax,
      plazoMin: producto?.plazo_min_meses ?? RANGOS_FALLBACK.plazoMin,
      plazoMax: producto?.plazo_max_meses ?? RANGOS_FALLBACK.plazoMax,
      montoMin:
        producto?.monto_min != null
          ? Number(producto.monto_min)
          : RANGOS_FALLBACK.montoMin,
      montoMax:
        producto?.monto_max != null
          ? Number(producto.monto_max)
          : RANGOS_FALLBACK.montoMax,
    }),
    [producto],
  )
  const plazos = useMemo(
    () => plazosDel(rangos.plazoMin, rangos.plazoMax),
    [rangos.plazoMin, rangos.plazoMax],
  )

  const actualizarValor = (key: keyof typeof initial, n: number | null) =>
    setForm((prev) => ({ ...prev, [key]: n ?? 0 }))

  const resultado = useMemo(() => {
    // Saldo a financiar = valor moto + adicionales + gastos
    // administrativos de originación − cuota inicial.
    const montoFinanciar = Math.max(
      0,
      form.valorVehiculo +
        form.adicionales +
        GASTOS_ADMINISTRATIVOS -
        form.cuotaInicial,
    )
    const plazoSeguro = Math.max(1, form.plazoMeses)
    const cuotaFinanciacion = cuotaAnualidad(
      montoFinanciar,
      form.tasaMensual,
      plazoSeguro,
    )
    // Seguro de vida: prima mensual fija del 0,35 % sobre el saldo a
    // financiar (espeja seguro_producto.tasa_prima y el pagaré).
    const cuotaSeguros = (montoFinanciar * PRIMA_SEGURO_VIDA_PCT) / 100
    const cuota = cuotaFinanciacion + cuotaSeguros
    const cuotaDiaria = cuota / DIAS_MES
    const tasaEA = (Math.pow(1 + form.tasaMensual / 100, 12) - 1) * 100
    const tabla = tablaAmortizacion(
      montoFinanciar,
      form.tasaMensual,
      plazoSeguro,
    )
    const totalIntereses = Math.max(
      0,
      cuotaFinanciacion * plazoSeguro - montoFinanciar,
    )
    const totalSeguros = cuotaSeguros * plazoSeguro
    const totalPagar = cuota * plazoSeguro
    return {
      montoFinanciar,
      cuotaFinanciacion,
      cuotaSeguros,
      cuota,
      cuotaDiaria,
      tasaEA,
      tabla,
      totalPagar,
      totalIntereses,
      totalSeguros,
    }
  }, [form])

  // Tasa operativa: la del producto — usura de consumo y ordinario en
  // m.v. menos un punto base (2,1175% cuando la usura es 28,59% EA) —
  // para quedar estrictamente bajo el límite que valida la evaluación.
  const tasaOperativa = useMemo(
    () => tasaProductoMv(consultaTasa.data?.ordinario.usura_ea),
    [consultaTasa.data],
  )

  // Tope editable: nunca sobre la tasa del producto; el rango comercial
  // puede acotar más por debajo.
  const tasaMaxEfectiva =
    tasaOperativa != null
      ? Math.min(rangos.tasaMax, tasaOperativa)
      : rangos.tasaMax

  // Precarga la tasa operativa apenas llega la referencia oficial;
  // respeta la edición manual del asesor.
  const tasaEditadaRef = useRef(false)
  useEffect(() => {
    if (tasaOperativa != null && !tasaEditadaRef.current) {
      setForm((prev) => ({ ...prev, tasaMensual: tasaOperativa }))
    }
  }, [tasaOperativa])

  const alertaMonto =
    resultado.montoFinanciar > rangos.montoMax
      ? `El monto a financiar supera el máximo del producto (${currency(rangos.montoMax)}).`
      : resultado.montoFinanciar > 0 &&
          resultado.montoFinanciar < rangos.montoMin
        ? `El monto a financiar está por debajo del mínimo del producto (${currency(rangos.montoMin)}).`
        : null

  const alertaTasa =
    form.tasaMensual < rangos.tasaMin || form.tasaMensual > tasaMaxEfectiva
      ? `La tasa del producto está entre ${rangos.tasaMin}% y ${tasaMaxEfectiva}% m.v.${
          tasaMaxEfectiva < rangos.tasaMax
            ? ` — la usura vigente topa la tasa para este monto`
            : ''
        }`
      : null

  const alertaPlazo =
    form.plazoMeses < rangos.plazoMin || form.plazoMeses > rangos.plazoMax
      ? `El plazo del producto está entre ${rangos.plazoMin} y ${rangos.plazoMax} meses.`
      : null

  // Animación de conteo al cargar/cambiar las cifras del hero
  const cuotaAnim = useCuentaAscendente(resultado.cuota)
  const montoAnim = useCuentaAscendente(resultado.montoFinanciar)
  const totalAnim = useCuentaAscendente(resultado.totalPagar)
  const interesesAnim = useCuentaAscendente(resultado.totalIntereses)

  return (
    <>
      <Encabezado
        title="Simulador de crédito"
        subtitle="Cuota francesa sobre el saldo a financiar: moto + adicionales + gastos administrativos − cuota inicial"
      />
      <div className="p-4 sm:p-6 space-y-6 overflow-auto">
        <div className="grid gap-5 lg:grid-cols-5">
          {/* Resultados primero en el DOM: en móvil la cuota es lo primero
              visible; en desktop quedan a la derecha */}
          <div className="space-y-5 lg:order-2 lg:col-span-3">
            {(alertaMonto || alertaTasa || alertaPlazo) && (
              <Tarjeta
                role="alert"
                className="border-amber-200 bg-amber-50/40 text-sm text-amber-800 space-y-1.5"
              >
                {[alertaMonto, alertaTasa, alertaPlazo]
                  .filter(Boolean)
                  .map((alerta) => (
                    <p key={alerta} className="flex items-center gap-2">
                      <AlertTriangle size={16} className="shrink-0" />
                      {alerta}
                    </p>
                  ))}
              </Tarjeta>
            )}

            <section
              aria-label="Resultado de la simulación"
              className="relative overflow-hidden rounded-2xl bg-[var(--navy-panel)] p-5 text-white shadow-lg sm:p-6"
            >
              {/* Acento de marca: un solo brillo cyan en la esquina */}
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-[radial-gradient(closest-side,rgb(var(--brand-rgb)/30%),transparent)]"
              />

              <div className="relative flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-medium text-cyan-100/75">
                    Cuota mensual estimada
                  </h2>
                  <p className="mt-1 text-5xl font-bold tabular-nums tracking-tight text-[var(--brand-light)] sm:text-6xl">
                    {currency(Math.round(cuotaAnim))}
                  </p>
                  <p className="mt-2.5 inline-flex items-baseline gap-1.5 rounded-full bg-[rgb(var(--brand-rgb)/25%)] px-3.5 py-1 text-sm font-semibold tabular-nums text-white ring-1 ring-[rgb(var(--brand-rgb)/40%)]">
                    ≈ {currency(Math.round(resultado.cuotaDiaria))}
                    <span className="text-xs font-normal text-cyan-100/75">
                      por día
                    </span>
                  </p>
                </div>
                <span className="rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-semibold text-cyan-100 ring-1 ring-white/15">
                  {form.plazoMeses} meses
                </span>
              </div>

              <dl className="relative mt-6 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-white/10 pt-5 sm:grid-cols-4 sm:divide-x sm:divide-white/10">
                {(
                  [
                    [
                      'Cuota financiación',
                      currency(Math.round(resultado.cuotaFinanciacion)),
                    ],
                    [
                      'Seguro de vida',
                      currency(Math.round(resultado.cuotaSeguros)),
                      `${PRIMA_SEGURO_VIDA_PCT}% m.v. del saldo`,
                    ],
                    [
                      'Tasa mensual',
                      `${form.tasaMensual}% MV`,
                      `${resultado.tasaEA.toFixed(2)}% EA`,
                    ],
                    ['Plazo', `${form.plazoMeses} meses`],
                  ] as const
                ).map(([dt, dd, extra]) => (
                  <div key={dt} className="sm:px-4 sm:first:pl-0 sm:last:pr-0">
                    <dt className="text-xs text-cyan-100/70">{dt}</dt>
                    <dd className="mt-0.5 text-base font-semibold tabular-nums">
                      {dd}
                    </dd>
                    {extra && (
                      <dd className="mt-0.5 text-xs text-cyan-100/55">
                        {extra}
                      </dd>
                    )}
                  </div>
                ))}
              </dl>

              <dl className="relative mt-6 divide-y divide-white/10 border-y border-white/10 text-sm">
                <div className="flex items-baseline justify-between gap-3 py-2">
                  <dt className="text-cyan-100/70">Valor moto</dt>
                  <dd className="font-medium tabular-nums">
                    {currency(form.valorVehiculo)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2">
                  <dt className="text-cyan-100/70">
                    Adicionales (matrícula, SOAT, impuestos)
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {currency(form.adicionales)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2">
                  <dt className="text-cyan-100/70">Gastos administrativos</dt>
                  <dd className="font-medium tabular-nums">
                    {currency(GASTOS_ADMINISTRATIVOS)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2">
                  <dt className="text-cyan-100/70">Cuota inicial</dt>
                  <dd className="font-medium tabular-nums text-[var(--brand-light)]">
                    − {currency(form.cuotaInicial)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2.5">
                  <dt className="font-semibold text-white">
                    Saldo a financiar
                  </dt>
                  <dd className="font-bold tabular-nums text-[var(--brand-light)]">
                    {currency(Math.round(montoAnim))}
                  </dd>
                </div>
              </dl>

              <dl className="relative mt-5 grid grid-cols-3 gap-x-4">
                {(
                  [
                    [
                      'Total intereses',
                      currency(Math.round(interesesAnim)),
                      false,
                    ],
                    [
                      'Total seguros',
                      currency(Math.round(resultado.totalSeguros)),
                      false,
                    ],
                    ['Total a pagar', currency(Math.round(totalAnim)), true],
                  ] as const
                ).map(([dt, dd, destacado]) => (
                  <div key={dt}>
                    <dt className="text-xs text-cyan-100/70">{dt}</dt>
                    <dd
                      className={`mt-0.5 text-base tabular-nums ${
                        destacado
                          ? 'font-bold text-[var(--brand-light)]'
                          : 'font-semibold'
                      }`}
                    >
                      {dd}
                    </dd>
                  </div>
                ))}
              </dl>

              <p className="relative mt-4 text-xs leading-relaxed text-cyan-100/55">
                * Estimación sujeta a estudio de crédito, verificación de datos
                y condiciones vigentes.
              </p>
            </section>

            <Tarjeta>
              <h3 className="font-semibold text-slate-900 mb-1">
                Comparación por plazo
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Haz clic en un plazo para usarlo en la simulación.
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-slate-500 border-b border-slate-200">
                      <th scope="col" className="py-2.5 pr-4">
                        Plazo
                      </th>
                      <th scope="col" className="py-2.5 pr-4 text-right">
                        Cuota mensual
                      </th>
                      <th scope="col" className="py-2.5 pr-4 text-right">
                        Total a pagar
                      </th>
                      <th scope="col" className="py-2.5 pr-4 text-right">
                        Intereses
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {plazos.map((plazo) => {
                      const cuota =
                        cuotaAnualidad(
                          resultado.montoFinanciar,
                          form.tasaMensual,
                          plazo,
                        ) + resultado.cuotaSeguros
                      const total = cuota * plazo
                      const activo = plazo === form.plazoMeses
                      return (
                        <tr
                          key={plazo}
                          onClick={() => actualizarValor('plazoMeses', plazo)}
                          className={`cursor-pointer border-b border-slate-100 transition ${
                            activo
                              ? 'bg-brand-50 font-medium'
                              : 'hover:bg-slate-50'
                          }`}
                        >
                          <td className="py-2.5 pr-4">
                            <button
                              type="button"
                              aria-pressed={activo}
                              onClick={() =>
                                actualizarValor('plazoMeses', plazo)
                              }
                              className="flex items-center gap-2 text-left"
                            >
                              <span
                                className={`inline-block h-3.5 w-3.5 rounded-full border-2 transition ${
                                  activo
                                    ? 'border-brand-600 bg-brand-600'
                                    : 'border-slate-300'
                                }`}
                                aria-hidden="true"
                              />
                              {plazo} meses
                            </button>
                          </td>
                          <td className="py-2.5 pr-4 text-right tabular-nums">
                            {currency(cuota)}
                          </td>
                          <td className="py-2.5 pr-4 text-right tabular-nums">
                            {currency(total)}
                          </td>
                          <td className="py-2.5 pr-4 text-right tabular-nums text-slate-600">
                            {currency(
                              Math.max(
                                0,
                                total -
                                  resultado.montoFinanciar -
                                  resultado.cuotaSeguros * plazo,
                              ),
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </Tarjeta>
          </div>

          <Tarjeta className="flex flex-col lg:order-1 lg:col-span-2">
            <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Calculator size={18} /> Condiciones
            </h3>
            <div className="flex-1 space-y-4">
              {producto && (
                <p className="text-xs text-[var(--brand-ink)] rounded-lg bg-[var(--surface-tint)] border border-brand-100 p-3">
                  {producto.nombre} · {producto.aliado}: tasa {rangos.tasaMin}%–
                  {rangos.tasaMax}% m.v., plazo {rangos.plazoMin}–
                  {rangos.plazoMax} meses, monto {currency(rangos.montoMin)}–
                  {currency(rangos.montoMax)}.
                </p>
              )}
              {catalogoError && !producto && (
                <p
                  role="status"
                  className="text-xs text-amber-700 rounded-lg bg-amber-50 border border-amber-200 p-3"
                >
                  Catálogo no disponible; usando rangos de referencia del
                  producto propio.
                </p>
              )}
              <CampoNumerico
                className="input-base"
                label="Valor de la moto (COP)"
                formatoMiles
                minimo={0}
                maximo={500_000_000}
                value={form.valorVehiculo}
                onValor={(n) => actualizarValor('valorVehiculo', n)}
              />
              <CampoNumerico
                className="input-base"
                label="Adicionales: matrícula, SOAT, impuestos (COP)"
                formatoMiles
                minimo={0}
                maximo={500_000_000}
                value={form.adicionales}
                onValor={(n) => actualizarValor('adicionales', n)}
              />
              <CampoNumerico
                className="input-base"
                label="Cuota inicial (COP)"
                formatoMiles
                minimo={0}
                maximo={500_000_000}
                value={form.cuotaInicial}
                onValor={(n) => actualizarValor('cuotaInicial', n)}
              />
              {/* El seguro de vida no es editable: prima fija del 0,35 %
                  m.v. sobre el saldo a financiar (política del producto). */}
              <p className="text-xs text-[var(--brand-ink)] rounded-lg bg-[var(--surface-tint)] border border-brand-100 p-3 tabular-nums">
                Seguro de vida: {PRIMA_SEGURO_VIDA_PCT}% m.v. sobre el saldo a
                financiar — {currency(Math.round(resultado.cuotaSeguros))}/mes.
              </p>
              <CampoNumerico
                className="input-base"
                label={`Tasa mensual % (${rangos.tasaMin}–${tasaMaxEfectiva})`}
                decimales
                minimo={rangos.tasaMin}
                maximo={tasaMaxEfectiva}
                value={form.tasaMensual}
                onValor={(n) => {
                  tasaEditadaRef.current = true
                  actualizarValor('tasaMensual', n)
                }}
                aria-invalid={!!alertaTasa}
              />
              {consultaTasa.data ? (
                <p className="flex items-start gap-1.5 text-xs text-slate-500">
                  <Landmark
                    size={14}
                    className="mt-px shrink-0 text-[var(--brand-deep)]"
                    aria-hidden="true"
                  />
                  <span>
                    Usura consumo y ordinario (SFC):{' '}
                    {consultaTasa.data.ordinario.usura_ea}% EA ≈{' '}
                    {consultaTasa.data.ordinario.usura_mv.toFixed(6)}% m.v. — el
                    producto opera por debajo · Res. SFC{' '}
                    {consultaTasa.data.ordinario.resolucion} · vigente hasta{' '}
                    {consultaTasa.data.ordinario.vigencia_hasta}
                  </span>
                </p>
              ) : consultaTasa.isError ? (
                <p className="text-xs text-slate-400">
                  Referencia oficial no disponible — usando la tasa del
                  producto.
                </p>
              ) : null}
              <CampoNumerico
                className="input-base"
                label={`Plazo meses (${rangos.plazoMin}–${rangos.plazoMax})`}
                value={form.plazoMeses}
                onValor={(n) => actualizarValor('plazoMeses', n)}
                aria-invalid={!!alertaPlazo}
              />
            </div>
            <div className="mt-auto pt-5">
              <Boton
                variante="primario"
                className="w-full justify-center"
                iconoFin={<ArrowRight size={16} aria-hidden="true" />}
                onClick={() =>
                  navigate('/nueva-solicitud', {
                    state: {
                      simulacion: {
                        valorMoto: form.valorVehiculo,
                        plazoMeses: form.plazoMeses,
                        adicionales: form.adicionales,
                        montoFinanciar: Math.round(resultado.montoFinanciar),
                        cuotaMensual: Math.round(resultado.cuota),
                      } satisfies SimulacionPrevia,
                    },
                  })
                }
              >
                Usar en una solicitud
              </Boton>
            </div>
          </Tarjeta>
        </div>

        <Tarjeta className="p-0">
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h3 className="font-semibold text-slate-900">
              Tabla de amortización
            </h3>
            <p className="text-xs text-slate-500">
              {form.plazoMeses} cuotas de{' '}
              {currency(Math.round(resultado.cuotaFinanciacion))} + seguro
              mensual de {currency(resultado.cuotaSeguros)}
            </p>
          </div>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-white/95 backdrop-blur-sm">
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500 shadow-[0_1px_0_0_theme(colors.slate.200)]">
                  <th scope="col" className="px-5 py-3">
                    Mes
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Cuota
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Seguro
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Interés
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Abono a capital
                  </th>
                  <th scope="col" className="px-5 py-3 text-right">
                    Saldo
                  </th>
                </tr>
              </thead>
              <tbody>
                {resultado.tabla.map((fila) => (
                  <tr
                    key={fila.mes}
                    className="border-b border-slate-100 hover:bg-[var(--surface-tint)]"
                  >
                    <td className="px-5 py-2.5 tabular-nums text-slate-500">
                      {fila.mes}
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums">
                      {currency(fila.cuota)}
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-slate-600">
                      {currency(resultado.cuotaSeguros)}
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums text-slate-600">
                      {currency(fila.interes)}
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums">
                      {currency(fila.abonoCapital)}
                    </td>
                    <td className="px-5 py-2.5 text-right tabular-nums font-medium">
                      {currency(fila.saldo)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Tarjeta>
      </div>
    </>
  )
}
