import { useEffect, useMemo, useState } from 'react'
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
import {
  CREDICONTADO_PLAZO_MAX,
  CREDICONTADO_PLAZO_MIN,
  CREDICONTADO_PLAZOS_TABLA,
  CREDICONTADO_TASA_MV,
  plazoCredicontado,
  tramoCredicontado,
} from '../shared/lib/credicontado'
import { useCuentaAscendente } from '../shared/lib/useCuentaAscendente'
import {
  listarProductos,
  tasaMercado,
  type ProductoApi,
} from '../features/credit-origination/api/originacionApi'
import { PRIMA_SEGURO_VIDA_PCT } from '../features/credit-origination/model/resultado-evaluacion'
import type { SimulacionPrevia } from '../features/credit-origination/model/borrador'
import { Calculator, ArrowRight, AlertTriangle, RotateCcw } from 'lucide-react'

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

// Cargo fijo de originación que se financia con la moto. Implícito en
// la simulación: ajustar aquí si la política del producto lo cambia.
const GASTOS_ADMINISTRATIVOS = 200_000

interface FormSimulador {
  valorVehiculo: number | null
  cuotaInicial: number | null
  adicionales: number | null
  tasaMensual: number | null
  plazoMeses: number | null
}

// Los campos arrancan vacíos: los placeholders anuncian valores de
// ejemplo y la simulación usa la tasa operativa y el plazo máximo.
const initial: FormSimulador = {
  valorVehiculo: null,
  cuotaInicial: null,
  adicionales: null,
  tasaMensual: null,
  plazoMeses: null,
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

  // Modo Credicontado: el logo aplica sus condiciones fijas (tasa 0,
  // plazo 1–12 y cuota inicial por tabla). Es adhesivo: solo se sale
  // con el botón "Salir de Credicontado" — tasa y cuota inicial van
  // bloqueadas porque la tabla las impone, y un plazo fuera del 1–12
  // muestra la alerta sin abandonar la línea.
  const [modoCredicontado, setModoCredicontado] = useState(false)

  const actualizarValor = (key: keyof FormSimulador, n: number | null) => {
    setForm((prev) => ({ ...prev, [key]: n }))
  }

  const aplicarCredicontado = () => {
    setModoCredicontado(true)
    setForm((prev) => ({
      ...prev,
      tasaMensual: CREDICONTADO_TASA_MV,
      plazoMeses: plazoCredicontado(prev.plazoMeses ?? CREDICONTADO_PLAZO_MAX),
    }))
  }

  // Salir del modo Credicontado: tasa y plazo vuelven a los valores
  // por defecto del producto propio (campos vacíos → tasa tope y
  // plazo máximo); los montos digitados por el usuario se conservan.
  const salirCredicontado = () => {
    setModoCredicontado(false)
    setForm((prev) => ({ ...prev, tasaMensual: null, plazoMeses: null }))
  }

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

  // Campo vacío → se simula con la tasa tope y el plazo máximo del
  // producto (los placeholders los anuncian como ejemplo). En modo
  // Credicontado la tasa es 0 fija y el plazo vive en 4–12 meses.
  const tasaEfectiva = modoCredicontado
    ? (form.tasaMensual ?? CREDICONTADO_TASA_MV)
    : (form.tasaMensual ?? tasaMaxEfectiva)
  const plazoEfectivo = modoCredicontado
    ? plazoCredicontado(form.plazoMeses ?? CREDICONTADO_PLAZO_MAX)
    : (form.plazoMeses ?? rangos.plazoMax)

  // En modo Credicontado la cuota inicial no se digita: la impone la
  // tabla por tramo de plazo sobre el saldo bruto a financiar.
  const saldoBruto =
    (form.valorVehiculo ?? 0) + (form.adicionales ?? 0) + GASTOS_ADMINISTRATIVOS
  const cuotaInicialPara = (plazo: number) =>
    Math.round(saldoBruto * tramoCredicontado(plazo).cuotaInicial)
  const cuotaInicialEfectiva = modoCredicontado
    ? cuotaInicialPara(plazoEfectivo)
    : (form.cuotaInicial ?? 0)

  // La tabla de comparación ofrece el rango de la línea activa: en
  // Credicontado sus plazos comerciales (4, 6, 8 y 12); en el
  // producto propio los hitos anuales del catálogo.
  const plazosTabla = modoCredicontado ? CREDICONTADO_PLAZOS_TABLA : plazos

  const resultado = useMemo(() => {
    // Saldo a financiar = valor moto + adicionales + gastos
    // administrativos de originación − cuota inicial.
    const montoFinanciar = Math.max(
      0,
      (form.valorVehiculo ?? 0) +
        (form.adicionales ?? 0) +
        GASTOS_ADMINISTRATIVOS -
        cuotaInicialEfectiva,
    )
    const plazoSeguro = Math.max(1, plazoEfectivo)
    const cuotaFinanciacion = cuotaAnualidad(
      montoFinanciar,
      tasaEfectiva,
      plazoSeguro,
    )
    // Seguro de vida: prima mensual fija del 0,35 % sobre el saldo a
    // financiar (espeja seguro_producto.tasa_prima y el pagaré).
    const cuotaSeguros = (montoFinanciar * PRIMA_SEGURO_VIDA_PCT) / 100
    const cuota = cuotaFinanciacion + cuotaSeguros
    const cuotaDiaria = cuota / DIAS_MES
    const tasaEA = (Math.pow(1 + tasaEfectiva / 100, 12) - 1) * 100
    const tabla = tablaAmortizacion(montoFinanciar, tasaEfectiva, plazoSeguro)
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
  }, [form, tasaEfectiva, plazoEfectivo, cuotaInicialEfectiva])

  // La tasa digitada nunca supera el tope aprobado vigente (usura
  // operativa): si quedó por encima — p. ej. digitada antes de que
  // llegara la referencia oficial — se corrige sola.
  useEffect(() => {
    setForm((prev) =>
      prev.tasaMensual != null && prev.tasaMensual > tasaMaxEfectiva
        ? { ...prev, tasaMensual: tasaMaxEfectiva }
        : prev,
    )
  }, [tasaMaxEfectiva])

  // Las alertas validan lo digitado; con el formulario vacío no se
  // muestra ninguna advertencia.
  const hayMontos =
    form.valorVehiculo != null ||
    form.adicionales != null ||
    form.cuotaInicial != null

  const alertaMonto =
    hayMontos && resultado.montoFinanciar > rangos.montoMax
      ? `El monto a financiar supera el máximo del producto (${currency(rangos.montoMax)}).`
      : hayMontos &&
          resultado.montoFinanciar > 0 &&
          resultado.montoFinanciar < rangos.montoMin
        ? `El monto a financiar está por debajo del mínimo del producto (${currency(rangos.montoMin)}).`
        : null

  const alertaTasa = modoCredicontado
    ? null
    : form.tasaMensual != null &&
        (form.tasaMensual < rangos.tasaMin ||
          form.tasaMensual > tasaMaxEfectiva)
      ? `La tasa del producto está entre ${rangos.tasaMin}% y ${tasaMaxEfectiva}% m.v.${
          tasaMaxEfectiva < rangos.tasaMax
            ? ` — la usura vigente topa la tasa para este monto`
            : ''
        }`
      : null

  const alertaPlazo =
    form.plazoMeses == null
      ? null
      : modoCredicontado
        ? form.plazoMeses < CREDICONTADO_PLAZO_MIN ||
          form.plazoMeses > CREDICONTADO_PLAZO_MAX
          ? `El plazo Credicontado está entre ${CREDICONTADO_PLAZO_MIN} y ${CREDICONTADO_PLAZO_MAX} meses.`
          : null
        : form.plazoMeses < rangos.plazoMin || form.plazoMeses > rangos.plazoMax
          ? `El plazo del producto está entre ${rangos.plazoMin} y ${rangos.plazoMax} meses.`
          : null

  // Animación de conteo al cargar/cambiar las cifras del hero
  const cuotaAnim = useCuentaAscendente(resultado.cuota)
  const montoAnim = useCuentaAscendente(resultado.montoFinanciar)

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
              className="relative overflow-hidden rounded-2xl bg-[rgb(0_70_138)] p-5 text-white shadow-lg sm:p-6"
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
                  <p className="mt-1 text-5xl font-bold tabular-nums tracking-tight text-white [text-shadow:0_0_28px_rgb(255_255_255/45%),0_0_8px_rgb(255_255_255/30%)] sm:text-6xl">
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
                  {plazoEfectivo} meses
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
                      `${tasaEfectiva}% MV`,
                      `${resultado.tasaEA.toFixed(2)}% EA`,
                    ],
                    ['Plazo', `${plazoEfectivo} meses`],
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
                    {currency(form.valorVehiculo ?? 0)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2">
                  <dt className="text-cyan-100/70">
                    Adicionales (matrícula, SOAT, impuestos)
                  </dt>
                  <dd className="font-medium tabular-nums">
                    {currency(form.adicionales ?? 0)}
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
                  <dd className="font-medium tabular-nums text-white [text-shadow:0_0_28px_rgb(255_255_255/45%),0_0_8px_rgb(255_255_255/30%)]">
                    − {currency(form.cuotaInicial ?? 0)}
                  </dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 py-2.5">
                  <dt className="font-semibold text-white">
                    Saldo a financiar
                  </dt>
                  <dd className="font-bold tabular-nums text-white [text-shadow:0_0_28px_rgb(255_255_255/45%),0_0_8px_rgb(255_255_255/30%)]">
                    {currency(Math.round(montoAnim))}
                  </dd>
                </div>
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
                    {plazosTabla.map((plazo) => {
                      // En Credicontado la cuota inicial la fija el
                      // tramo del plazo comparado: cada fila tiene
                      // su propio saldo a financiar.
                      const montoFila = modoCredicontado
                        ? Math.max(0, saldoBruto - cuotaInicialPara(plazo))
                        : resultado.montoFinanciar
                      const segurosFila =
                        (montoFila * PRIMA_SEGURO_VIDA_PCT) / 100
                      const cuota =
                        cuotaAnualidad(montoFila, tasaEfectiva, plazo) +
                        segurosFila
                      const total = cuota * plazo
                      const activo = plazo === plazoEfectivo
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
                                total - montoFila - segurosFila * plazo,
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

          <div className="lg:order-1 lg:col-span-2 self-start">
            <Tarjeta>
              <h3 className="font-semibold text-slate-900 mb-4 flex items-center gap-2">
                <Calculator size={18} /> Condiciones
              </h3>
              <div className="space-y-4">
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
                  placeholder="Ej: 10.000.000"
                  value={form.valorVehiculo}
                  onValor={(n) => actualizarValor('valorVehiculo', n)}
                />
                <CampoNumerico
                  className="input-base"
                  label="Adicionales: matrícula, SOAT, impuestos (COP)"
                  formatoMiles
                  minimo={0}
                  maximo={500_000_000}
                  placeholder="Ej: 1.150.000"
                  value={form.adicionales}
                  onValor={(n) => actualizarValor('adicionales', n)}
                />
                <CampoNumerico
                  className="input-base"
                  label={
                    modoCredicontado
                      ? `Plazo meses Credicontado (${CREDICONTADO_PLAZO_MIN}–${CREDICONTADO_PLAZO_MAX})`
                      : `Plazo meses (${rangos.plazoMin}–${rangos.plazoMax})`
                  }
                  placeholder={
                    modoCredicontado ? 'Ej: 12' : `Ej: ${rangos.plazoMax}`
                  }
                  minimo={
                    modoCredicontado ? CREDICONTADO_PLAZO_MIN : rangos.plazoMin
                  }
                  maximo={
                    modoCredicontado ? CREDICONTADO_PLAZO_MAX : rangos.plazoMax
                  }
                  value={form.plazoMeses}
                  onValor={(n) => actualizarValor('plazoMeses', n)}
                  aria-invalid={!!alertaPlazo}
                />
                <CampoNumerico
                  className="input-base"
                  label={
                    modoCredicontado
                      ? `Cuota inicial Credicontado (${Math.round(
                          tramoCredicontado(plazoEfectivo).cuotaInicial * 100,
                        )}% del saldo)`
                      : 'Cuota inicial (COP)'
                  }
                  formatoMiles
                  minimo={0}
                  maximo={500_000_000}
                  placeholder="Ej: 1.000.000"
                  disabled={modoCredicontado}
                  value={
                    modoCredicontado ? cuotaInicialEfectiva : form.cuotaInicial
                  }
                  onValor={(n) => actualizarValor('cuotaInicial', n)}
                />
                <CampoNumerico
                  className="input-base"
                  label={
                    modoCredicontado
                      ? 'Tasa mensual Credicontado (0% — sin interés)'
                      : `Tasa mensual regular (${rangos.tasaMin}–${tasaMaxEfectiva}) %`
                  }
                  decimales
                  mostrarCero={modoCredicontado}
                  disabled={modoCredicontado}
                  minimo={modoCredicontado ? undefined : rangos.tasaMin}
                  maximo={modoCredicontado ? undefined : tasaMaxEfectiva}
                  placeholder={
                    modoCredicontado ? '0' : `Ej: ${tasaMaxEfectiva}`
                  }
                  value={form.tasaMensual}
                  onValor={(n) => actualizarValor('tasaMensual', n)}
                  aria-invalid={!!alertaTasa}
                />
              </div>
              <div className="pt-5">
                <Boton
                  variante="primario"
                  className="w-full justify-center"
                  iconoFin={<ArrowRight size={16} aria-hidden="true" />}
                  onClick={() =>
                    navigate('/nueva-solicitud', {
                      state: {
                        simulacion: {
                          valorMoto: form.valorVehiculo ?? 0,
                          plazoMeses: plazoEfectivo,
                          adicionales: form.adicionales ?? 0,
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
            <style>
              {`
                .btn-wobble {
                  animation: wobble 2s ease-in-out infinite;
                }
                .btn-wobble:hover,
                .btn-wobble:focus,
                .btn-wobble:focus-visible,
                .btn-wobble[aria-pressed='true'] {
                  animation: none;
                }
                @media (prefers-reduced-motion: reduce) {
                  .btn-wobble {
                    animation: none;
                  }
                }
                @keyframes wobble {
                  0%,
                  40%,
                  100% {
                    transform: translateX(0%);
                  }
                  6% {
                    transform: translateX(-25%) rotate(-5deg);
                  }
                  12% {
                    transform: translateX(20%) rotate(3deg);
                  }
                  18% {
                    transform: translateX(-15%) rotate(-3deg);
                  }
                  24% {
                    transform: translateX(10%) rotate(2deg);
                  }
                  30% {
                    transform: translateX(-5%) rotate(-1deg);
                  }
                }
              `}
            </style>
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <button
                type="button"
                aria-pressed={modoCredicontado}
                aria-label="Aplicar condiciones de la línea Credicontado"
                title="Aplicar condiciones Credicontado: tasa 0 %, plazo 1–12 meses y cuota inicial según tabla"
                className={`btn-wobble flex w-fit items-center justify-start rounded-full border px-2 py-0.5 shadow-md backdrop-blur-md transition-all duration-200 hover:bg-white/40 ${
                  modoCredicontado
                    ? 'border-brand-600 bg-white/50 ring-2 ring-brand-600/30'
                    : 'border-slate-400 bg-white/30'
                }`}
                onClick={aplicarCredicontado}
              >
                <img
                  src="/brand/credicontado.png"
                  alt="Credicontado"
                  className="h-6 w-auto max-w-full object-contain"
                />
              </button>
              {modoCredicontado && (
                <button
                  type="button"
                  aria-label="Salir de la simulación Credicontado y volver a los valores por defecto"
                  title="Volver a las condiciones por defecto del producto"
                  className="flex items-center gap-1 rounded-full border border-slate-400 bg-white/30 px-2 py-1 text-xs text-slate-700 shadow-md backdrop-blur-md transition-all duration-200 hover:bg-white/40"
                  onClick={salirCredicontado}
                >
                  <RotateCcw size={12} aria-hidden="true" />
                  Salir de Credicontado
                </button>
              )}
            </div>
          </div>
        </div>

        <Tarjeta className="p-0">
          <div className="flex items-center justify-between px-5 pt-5 pb-3">
            <h3 className="font-semibold text-slate-900">
              Tabla de amortización
            </h3>
            <p className="text-xs text-slate-500">
              {plazoEfectivo} cuotas de{' '}
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
