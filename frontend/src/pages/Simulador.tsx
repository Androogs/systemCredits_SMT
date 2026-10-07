import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Encabezado from '../widgets/app-shell/Encabezado'
import Tarjeta from '../shared/ui/Tarjeta'
import CampoEntrada from '../shared/ui/CampoEntrada'
import Selector from '../shared/ui/Selector'
import Boton from '../shared/ui/Boton'
import { currency } from '../shared/lib/formatters'
import { cuotaAnualidad, tablaAmortizacion } from '../shared/lib/finanzas'
import {
  listarProductos,
  type ProductoApi,
} from '../features/credit-origination/api/originacionApi'
import {
  Calculator,
  Wallet,
  Percent,
  CalendarDays,
  ArrowRight,
  AlertTriangle,
} from 'lucide-react'
import type { ChangeEvent } from 'react'

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
  valorVehiculo: 12_000_000,
  cuotaInicial: 2_000_000,
  tasaMensual: 1.5,
  plazoMeses: 36,
}

export default function Simulador() {
  const navigate = useNavigate()
  const [form, setForm] = useState(initial)
  const [producto, setProducto] = useState<ProductoApi | null>(null)
  const [catalogoError, setCatalogoError] = useState(false)

  useEffect(() => {
    listarProductos()
      .then((lista) => setProducto(lista[0] ?? null))
      .catch(() => setCatalogoError(true))
  }, [])

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

  const update =
    (key: keyof typeof initial) =>
    (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((prev) => ({ ...prev, [key]: Number(event.target.value) }))

  const resultado = useMemo(() => {
    const montoFinanciar = Math.max(0, form.valorVehiculo - form.cuotaInicial)
    const cuota = cuotaAnualidad(
      montoFinanciar,
      form.tasaMensual,
      form.plazoMeses,
    )
    const tabla = tablaAmortizacion(
      montoFinanciar,
      form.tasaMensual,
      form.plazoMeses,
    )
    const totalPagar = cuota * form.plazoMeses
    return {
      montoFinanciar,
      cuota,
      tabla,
      totalPagar,
      totalIntereses: Math.max(0, totalPagar - montoFinanciar),
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

  return (
    <>
      <Encabezado
        title="Simulador de crédito"
        subtitle="Cuota francesa: valor del vehículo, cuota inicial, tasa y plazo"
      />
      <div className="p-6 space-y-6 overflow-auto">
        <div className="grid lg:grid-cols-3 gap-6">
          <Tarjeta className="lg:col-span-1 h-fit">
            <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
              <Calculator size={18} /> Condiciones
            </h3>
            <div className="space-y-4">
              {producto && (
                <p className="text-xs text-slate-500 rounded-lg bg-slate-50 border border-slate-200 p-3">
                  {producto.nombre} · {producto.aliado}: tasa {rangos.tasaMin}%–
                  {rangos.tasaMax}% m.v., plazo {rangos.plazoMin}–
                  {rangos.plazoMax} meses, monto {currency(rangos.montoMin)}–
                  {currency(rangos.montoMax)}.
                </p>
              )}
              {catalogoError && !producto && (
                <p className="text-xs text-amber-700 rounded-lg bg-amber-50 border border-amber-200 p-3">
                  Catálogo no disponible; usando rangos de referencia del
                  producto propio.
                </p>
              )}
              <CampoEntrada
                label="Valor del vehículo (COP)"
                type="number"
                min={0}
                value={form.valorVehiculo}
                onChange={update('valorVehiculo')}
              />
              <CampoEntrada
                label="Cuota inicial (COP)"
                type="number"
                min={0}
                value={form.cuotaInicial}
                onChange={update('cuotaInicial')}
              />
              <CampoEntrada
                label={`Tasa mensual % (${rangos.tasaMin}–${rangos.tasaMax})`}
                type="number"
                min={rangos.tasaMin}
                max={rangos.tasaMax}
                step="0.01"
                value={form.tasaMensual}
                onChange={update('tasaMensual')}
              />
              <Selector
                label="Plazo"
                value={String(form.plazoMeses)}
                onChange={update('plazoMeses')}
                options={plazos.map((p) => ({
                  value: String(p),
                  label: `${p} meses`,
                }))}
              />
            </div>
          </Tarjeta>

          <div className="lg:col-span-2 space-y-6">
            {(alertaMonto ?? alertaTasa) && (
              <Tarjeta className="border-amber-200 bg-amber-50/40 text-sm text-amber-800 flex items-center gap-2">
                <AlertTriangle size={16} className="shrink-0" />
                {alertaMonto ?? alertaTasa}
              </Tarjeta>
            )}
            <div className="grid sm:grid-cols-3 gap-4">
              <Metrica
                icon={Wallet}
                label="Monto a financiar"
                value={currency(resultado.montoFinanciar)}
              />
              <Metrica
                icon={CalendarDays}
                label="Cuota mensual"
                value={currency(resultado.cuota)}
                destacado
              />
              <Metrica
                icon={Percent}
                label="Total intereses"
                value={currency(resultado.totalIntereses)}
              />
            </div>

            <Tarjeta>
              <h3 className="font-semibold text-slate-900 mb-4">
                Comparación por plazo
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                      <th className="py-2.5 pr-4">Plazo</th>
                      <th className="py-2.5 pr-4">Cuota mensual</th>
                      <th className="py-2.5 pr-4">Total a pagar</th>
                      <th className="py-2.5 pr-4">Intereses</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plazos.map((plazo) => {
                      const cuota = cuotaAnualidad(
                        resultado.montoFinanciar,
                        form.tasaMensual,
                        plazo,
                      )
                      const total = cuota * plazo
                      const activo = plazo === form.plazoMeses
                      return (
                        <tr
                          key={plazo}
                          className={`border-b border-slate-100 ${activo ? 'bg-brand-50 font-medium' : ''}`}
                        >
                          <td className="py-2.5 pr-4">{plazo} meses</td>
                          <td className="py-2.5 pr-4">{currency(cuota)}</td>
                          <td className="py-2.5 pr-4">{currency(total)}</td>
                          <td className="py-2.5 pr-4">
                            {currency(
                              Math.max(0, total - resultado.montoFinanciar),
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
        </div>

        <Tarjeta className="p-0">
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h3 className="font-semibold text-slate-900">
              Tabla de amortización
            </h3>
            <p className="text-xs text-slate-500">
              {form.plazoMeses} cuotas de {currency(resultado.cuota)}
            </p>
          </div>
          <div className="overflow-auto max-h-96">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
                  <th className="px-5 py-3">Mes</th>
                  <th className="px-5 py-3">Cuota</th>
                  <th className="px-5 py-3">Interés</th>
                  <th className="px-5 py-3">Abono a capital</th>
                  <th className="px-5 py-3">Saldo</th>
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

        <div className="flex justify-end">
          <Boton
            variante="primario"
            iconoFin={<ArrowRight size={16} aria-hidden="true" />}
            onClick={() => navigate('/nueva-solicitud')}
          >
            Usar en una solicitud
          </Boton>
        </div>
      </div>
    </>
  )
}

function Metrica({
  icon: Icon,
  label,
  value,
  destacado = false,
}: {
  icon: typeof Wallet
  label: string
  value: string
  destacado?: boolean
}) {
  return (
    <Tarjeta className={destacado ? 'border-brand-500/40 bg-brand-50/40' : ''}>
      <div className="flex items-center gap-3">
        <div
          className={`h-10 w-10 rounded-xl grid place-items-center ${
            destacado ? 'bg-brand-600 text-white' : 'bg-brand-50 text-brand-600'
          }`}
        >
          <Icon size={18} />
        </div>
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            {label}
          </p>
          <p className="text-lg font-bold text-slate-900 truncate">{value}</p>
        </div>
      </div>
    </Tarjeta>
  )
}
