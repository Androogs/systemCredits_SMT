import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import CampoNumerico from '../shared/ui/CampoNumerico'
import Boton from '../shared/ui/Boton'
import { currency } from '../shared/lib/formatters'
import { cuotaAnualidad, tablaAmortizacion } from '../shared/lib/finanzas'
import { useCuentaAscendente } from '../shared/lib/useCuentaAscendente'
import {
  listarProductos,
  type ProductoApi,
} from '../features/credit-origination/api/originacionApi'
import {
  PRIMA_SEGURO_VIDA_PCT,
  TASA_MENSUAL_REFERENCIA,
} from '../features/credit-origination/model/resultado-evaluacion'
import type { SimulacionPrevia } from '../features/credit-origination/model/borrador'
import { Calculator, ArrowRight, AlertTriangle } from 'lucide-react'

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

const initial = {
  valorVehiculo: 10_000_000,
  cuotaInicial: 1_000_000,
  adicionales: 1_150_000,
  // Misma tasa con la que el motor evalúa capacidad de pago.
  tasaMensual: TASA_MENSUAL_REFERENCIA,
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
    // Saldo a financiar = valor moto + adicionales − cuota inicial.
    // El cargo administrativo es interno: no entra en la vista del asesor.
    const montoFinanciar = Math.max(
      0,
      form.valorVehiculo + form.adicionales - form.cuotaInicial,
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

  const alertaMonto =
    resultado.montoFinanciar > rangos.montoMax
      ? `El monto a financiar supera el máximo del producto (${currency(rangos.montoMax)}).`
      : resultado.montoFinanciar > 0 &&
          resultado.montoFinanciar < rangos.montoMin
        ? `El monto a financiar está por debajo del mínimo del producto (${currency(rangos.montoMin)}).`
        : null

  const alertaTasa =
    form.tasaMensual < rangos.tasaMin || form.tasaMensual > rangos.tasaMax
      ? `La tasa del producto está entre ${rangos.tasaMin}% y ${rangos.tasaMax}% m.v.`
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
        subtitle="Cuota francesa sobre el saldo a financiar: moto + adicionales − cuota inicial"
      />
      <div className="p-4 sm:p-6 space-y-6 overflow-auto">
        <div className="grid gap-5 lg:grid-cols-5">
          {/* Resultados primero en el DOM: en móvil la cuota es lo primero
              visible; en desktop quedan a la derecha */}
          <div className="space-y-5 lg:order-2 lg:col-span-3">
            {(alertaMonto || alertaTasa || alertaPlazo) && (
              <Tarjeta className="border-amber-200 bg-amber-50/40 text-sm text-amber-800 space-y-1.5">
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
              className="rounded-2xl bg-[#0d1b3e] p-5 text-white shadow-lg ring-1 ring-white/10"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-cyan-300">
                  Resultado de tu simulación
                </p>
                <span className="rounded-full bg-cyan-400/10 px-3 py-1 text-xs font-semibold text-cyan-200 ring-1 ring-cyan-400/30">
                  {form.plazoMeses} meses
                </span>
              </div>

              <div className="mt-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-1">
                <div>
                  <p className="text-xs text-slate-300">
                    Cuota mensual estimada
                  </p>
                  <p className="mt-0.5 text-4xl font-bold tracking-tight text-cyan-300">
                    {currency(Math.round(cuotaAnim))}
                  </p>
                </div>
                <p className="pb-1 text-xs text-slate-300">
                  Cuota diaria aprox.:{' '}
                  <strong className="text-white">
                    {currency(Math.round(resultado.cuotaDiaria))}
                  </strong>
                </p>
              </div>

              <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
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
                  <div
                    key={dt}
                    className="rounded-lg bg-white/5 px-3 py-2.5 ring-1 ring-white/10"
                  >
                    <dt className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                      {dt}
                    </dt>
                    <dd className="mt-0.5 text-sm font-semibold">{dd}</dd>
                    {extra && (
                      <dd className="text-[10px] text-slate-400">{extra}</dd>
                    )}
                  </div>
                ))}
              </dl>

              <dl className="mt-3 space-y-1.5 rounded-lg bg-white/5 px-3.5 py-3 text-[13px] ring-1 ring-white/10">
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-slate-300">Valor moto</dt>
                  <dd className="font-semibold">
                    {currency(form.valorVehiculo)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-slate-300">
                    Adicionales (matrícula, SOAT, impuestos)
                  </dt>
                  <dd className="font-semibold">
                    {currency(form.adicionales)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <dt className="text-slate-300">Cuota inicial</dt>
                  <dd className="font-semibold text-cyan-300">
                    − {currency(form.cuotaInicial)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 border-t border-white/10 pt-1.5">
                  <dt className="font-semibold text-white">
                    Saldo a financiar
                  </dt>
                  <dd className="font-bold text-cyan-300">
                    {currency(Math.round(montoAnim))}
                  </dd>
                </div>
              </dl>

              <div className="mt-3 grid grid-cols-3 gap-2">
                <div className="rounded-lg bg-white/5 px-3 py-2.5 ring-1 ring-white/10">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                    Total intereses
                  </p>
                  <p className="mt-0.5 text-sm font-semibold">
                    {currency(Math.round(interesesAnim))}
                  </p>
                </div>
                <div className="rounded-lg bg-white/5 px-3 py-2.5 ring-1 ring-white/10">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">
                    Total seguros
                  </p>
                  <p className="mt-0.5 text-sm font-semibold">
                    {currency(Math.round(resultado.totalSeguros))}
                  </p>
                </div>
                <div className="rounded-lg bg-cyan-400/10 px-3 py-2.5 ring-1 ring-cyan-400/30">
                  <p className="text-[10px] font-medium uppercase tracking-wide text-cyan-200">
                    Total a pagar
                  </p>
                  <p className="mt-0.5 text-sm font-bold">
                    {currency(Math.round(totalAnim))}
                  </p>
                </div>
              </div>

              <p className="mt-3 text-[10px] leading-relaxed text-slate-400">
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
                    <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                      <th scope="col" className="py-2.5 pr-4">
                        Plazo
                      </th>
                      <th scope="col" className="py-2.5 pr-4">
                        Cuota mensual
                      </th>
                      <th scope="col" className="py-2.5 pr-4">
                        Total a pagar
                      </th>
                      <th scope="col" className="py-2.5 pr-4">
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
                          <td className="py-2.5 pr-4">{currency(cuota)}</td>
                          <td className="py-2.5 pr-4">{currency(total)}</td>
                          <td className="py-2.5 pr-4">
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
                <p className="text-xs text-slate-500 rounded-lg bg-slate-50 border border-slate-200 p-3">
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
              <p className="text-xs text-slate-500 rounded-lg bg-slate-50 border border-slate-200 p-3">
                Seguro de vida: {PRIMA_SEGURO_VIDA_PCT}% m.v. sobre el saldo a
                financiar — {currency(Math.round(resultado.cuotaSeguros))}/mes.
              </p>
              <CampoNumerico
                className="input-base"
                label={`Tasa mensual % (${rangos.tasaMin}–${rangos.tasaMax})`}
                decimales
                minimo={rangos.tasaMin}
                maximo={rangos.tasaMax}
                value={form.tasaMensual}
                onValor={(n) => actualizarValor('tasaMensual', n)}
              />
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
              <thead className="sticky top-0 bg-white">
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th scope="col" className="px-5 py-3">
                    Mes
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Cuota
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Seguro
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Interés
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Abono a capital
                  </th>
                  <th scope="col" className="px-5 py-3">
                    Saldo
                  </th>
                </tr>
              </thead>
              <tbody>
                {resultado.tabla.map((fila) => (
                  <tr
                    key={fila.mes}
                    className="border-b border-slate-100 hover:bg-slate-50"
                  >
                    <td className="px-5 py-2.5">{fila.mes}</td>
                    <td className="px-5 py-2.5">{currency(fila.cuota)}</td>
                    <td className="px-5 py-2.5">
                      {currency(resultado.cuotaSeguros)}
                    </td>
                    <td className="px-5 py-2.5">{currency(fila.interes)}</td>
                    <td className="px-5 py-2.5">
                      {currency(fila.abonoCapital)}
                    </td>
                    <td className="px-5 py-2.5">{currency(fila.saldo)}</td>
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
