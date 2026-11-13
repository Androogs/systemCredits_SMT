import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Save,
  Upload,
} from 'lucide-react'
import Boton from '../../../shared/ui/Boton'
import CampoEntrada from '../../../shared/ui/CampoEntrada'
import CampoNumerico from '../../../shared/ui/CampoNumerico'
import {
  ApiError,
  guardarVentaContado,
  obtenerSolicitud,
  subirFactura,
  type FacturaRegistradaApi,
  type VentaContadoPayload,
} from '../api/originacionApi'
import type { IdentidadSolicitante } from '../model/mapeos-api'
import type { DatosSolicitud } from './CrearSolicitud'
import SeguimientoOriginacion from './SeguimientoOriginacion/SeguimientoOriginacion'
import './EvaluacionYResultado.css'
import './ResultadoCredito.css'
import './VentaContado.css'

interface VentaContadoProps {
  idSolicitud?: string
  identidad?: IdentidadSolicitante
  solicitud?: DatosSolicitud
  onBack?: () => void
  /** Cierra el proceso y vuelve al listado de solicitudes. */
  onFinalizar?: () => void
}

const formatoCOP = new Intl.NumberFormat('es-CO', {
  style: 'currency',
  currency: 'COP',
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
})

/** Hoja de negocio del formato de venta de contado: identificación,
 * vehículo y liquidación. Los importes se guardan como número|null y
 * los textos como cadena. */
interface FormVenta {
  asesorExterno: string
  facturarDoc: string
  facturarNombre: string
  segundoFacturado: boolean
  facturar2Doc: string
  facturar2Nombre: string
  marca: string
  referencia: string
  modelo: string
  color: string
  motor: string
  chasis: string
  vin: string
  ciudadMatricula: string
  valorMoto: number | null
  descuento: number | null
  matricula: number | null
  impuestos: number | null
  soat: number | null
  accesorios: number | null
  otrosGastos: number | null
  anticipo: number | null
  retoma: number | null
  observaciones: string
}

const FORM_INICIAL: FormVenta = {
  asesorExterno: '',
  facturarDoc: '',
  facturarNombre: '',
  segundoFacturado: false,
  facturar2Doc: '',
  facturar2Nombre: '',
  marca: '',
  referencia: '',
  modelo: '',
  color: '',
  motor: '',
  chasis: '',
  vin: '',
  ciudadMatricula: '',
  valorMoto: null,
  descuento: null,
  matricula: null,
  impuestos: null,
  soat: null,
  accesorios: null,
  otrosGastos: null,
  anticipo: null,
  retoma: null,
  observaciones: '',
}

/** Las decimales del API viajan como cadena; ''/null → null. */
const aNumero = (v: string | null | undefined): number | null => {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/** Paso 5 para ventas de contado: no hay consulta a centrales de riesgo
 * ni ofertas — se diligencia la hoja de negocio (que además alimenta el
 * paquete de documentos físicos de la entrega), se factura de inmediato
 * y se cierra la venta. */
export default function VentaContado({
  idSolicitud,
  identidad,
  solicitud,
  onBack,
  onFinalizar,
}: VentaContadoProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const prefilled = useRef(false)
  const [subiendo, setSubiendo] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [guardada, setGuardada] = useState(false)
  const [factura, setFactura] = useState<FacturaRegistradaApi | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [form, setForm] = useState<FormVenta>(FORM_INICIAL)

  const nombreSolicitante = identidad
    ? `${identidad.nombres} ${identidad.apellidos}`.trim()
    : 'Solicitante de demostración'

  const detalle = useQuery({
    queryKey: ['solicitud', idSolicitud],
    queryFn: () => obtenerSolicitud(idSolicitud as string),
    enabled: Boolean(idSolicitud),
  })

  // Pre-llena la hoja de negocio con lo ya persistido (vehículo,
  // liquidación, facturar a) la primera vez que llega el detalle.
  useEffect(() => {
    const d = detalle.data
    if (!d || prefilled.current) return
    prefilled.current = true
    const v = d.vehiculo
    setForm((f) => ({
      ...f,
      asesorExterno: d.asesor_externo ?? '',
      facturarDoc: d.facturar_a_documento ?? identidad?.numeroDocumento ?? '',
      facturarNombre:
        d.facturar_a_nombre ??
        (identidad ? `${identidad.nombres} ${identidad.apellidos}`.trim() : ''),
      segundoFacturado: Boolean(
        d.facturar_a2_documento || d.facturar_a2_nombre,
      ),
      facturar2Doc: d.facturar_a2_documento ?? '',
      facturar2Nombre: d.facturar_a2_nombre ?? '',
      marca: v?.marca ?? '',
      referencia: v?.referencia ?? '',
      modelo: v?.modelo ?? '',
      color: v?.color ?? '',
      motor: v?.numero_motor ?? '',
      chasis: v?.numero_chasis ?? '',
      vin: v?.vin ?? '',
      ciudadMatricula: v?.ciudad_matricula ?? '',
      valorMoto: aNumero(v?.valor_moto_iva),
      descuento: aNumero(v?.descuento_pesos),
      matricula: aNumero(v?.matricula),
      impuestos: aNumero(v?.impuestos),
      soat: aNumero(v?.soat),
      accesorios: aNumero(v?.accesorios),
      otrosGastos: aNumero(v?.otros_gastos),
      anticipo: aNumero(v?.anticipo),
      retoma: aNumero(v?.retoma_valor),
      observaciones: d.observaciones_venta ?? '',
    }))
  }, [detalle.data, identidad])

  const set = <K extends keyof FormVenta>(campo: K, valor: FormVenta[K]) => {
    setGuardada(false)
    setForm((f) => ({ ...f, [campo]: valor }))
  }

  const n = (v: number | null) => v ?? 0
  const vrTotal =
    n(form.valorMoto) -
    n(form.descuento) +
    n(form.matricula) +
    n(form.impuestos) +
    n(form.soat) +
    n(form.accesorios) +
    n(form.otrosGastos)
  const saldoPagar = vrTotal - n(form.anticipo) - n(form.retoma)

  const erroresForm = (): string | null => {
    if (!form.marca.trim()) return 'La marca de la motocicleta es obligatoria.'
    if (!form.referencia.trim())
      return 'La motocicleta (referencia) es obligatoria.'
    if (form.valorMoto == null || form.valorMoto <= 0)
      return 'El valor de la moto (VR. MOTO) debe ser mayor a cero.'
    if (!form.facturarDoc.trim() || !form.facturarNombre.trim())
      return 'Diligencia a quién se expide la factura (documento y nombre).'
    return null
  }

  const guardar = () => {
    if (!idSolicitud) return
    const errorForm = erroresForm()
    if (errorForm) {
      setError(errorForm)
      return
    }
    setGuardando(true)
    setError(null)
    const payload: VentaContadoPayload = {
      asesor_externo: form.asesorExterno.trim() || null,
      facturar_a_documento: form.facturarDoc.trim() || null,
      facturar_a_nombre: form.facturarNombre.trim() || null,
      facturar_a2_documento: form.segundoFacturado
        ? form.facturar2Doc.trim() || null
        : null,
      facturar_a2_nombre: form.segundoFacturado
        ? form.facturar2Nombre.trim() || null
        : null,
      observaciones: form.observaciones.trim() || null,
      vehiculo: {
        producto_a_financiar: 'Motocicleta',
        marca: form.marca.trim() || null,
        referencia: form.referencia.trim() || null,
        modelo: form.modelo.trim() || null,
        color: form.color.trim() || null,
        valor_moto_iva: form.valorMoto,
        descuento: form.descuento,
        accesorios: form.accesorios,
        matricula: form.matricula,
        soat: form.soat,
        impuestos: form.impuestos,
      },
      numero_motor: form.motor.trim() || null,
      numero_chasis: form.chasis.trim() || null,
      vin: form.vin.trim() || null,
      ciudad_matricula: form.ciudadMatricula.trim() || null,
      anticipo: form.anticipo,
      retoma: form.retoma,
      otros_gastos: form.otrosGastos,
    }
    guardarVentaContado(idSolicitud, payload)
      .then(() => {
        setGuardada(true)
        void detalle.refetch()
      })
      .catch((err: unknown) => {
        const detalleErr =
          err instanceof ApiError && err.detalle
            ? ` (${typeof err.detalle === 'string' ? err.detalle : JSON.stringify(err.detalle)})`
            : ''
        setError(`No se pudo guardar la venta${detalleErr}.`)
      })
      .finally(() => setGuardando(false))
  }

  const subir = (archivo: File) => {
    if (!idSolicitud) return
    setSubiendo(true)
    setError(null)
    subirFactura(idSolicitud, archivo)
      .then(setFactura)
      .catch((err: unknown) => {
        const detalle =
          err instanceof ApiError && err.detalle
            ? ` (${typeof err.detalle === 'string' ? err.detalle : JSON.stringify(err.detalle)})`
            : ''
        setError(
          `No se pudo registrar la factura${detalle}. Revisa el archivo e intenta de nuevo.`,
        )
      })
      .finally(() => setSubiendo(false))
  }

  const elegirArchivo = (e: React.ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0]
    e.target.value = '' // permite re-elegir el mismo archivo
    if (archivo) subir(archivo)
  }

  const verif = factura?.verificacion ?? null
  const datosFactura = verif?.datos ?? null
  const advertencias = verif?.advertencias ?? []
  const ocupado = subiendo || guardando

  return (
    <div className="evaluacion-resultado venta-contado">
      <header className="evaluacion-resultado__header">
        <div className="evaluacion-resultado__header-copy">
          <p className="evaluacion-resultado__eyebrow">
            Originación Individual · Paso 5
          </p>
          <h1>Venta de contado</h1>
          <p className="evaluacion-resultado__subtitle">
            El cliente paga sin financiación: no se consulta el buró de crédito
            y la venta se factura de inmediato.
          </p>
        </div>
      </header>

      <SeguimientoOriginacion pasoActual={5} />

      <section className="evaluacion-resultado__origen">
        <div className="evaluacion-resultado__solicitante">
          <span aria-hidden="true">
            {nombreSolicitante
              .split(' ')
              .slice(0, 2)
              .map((p) => p.charAt(0))
              .join('')}
          </span>
          <div>
            <strong>{nombreSolicitante}</strong>
            <small>
              {identidad
                ? `${identidad.tipoDocumento} ${identidad.numeroDocumento}`
                : 'Modo demostración'}
            </small>
          </div>
        </div>

        {idSolicitud && (
          <>
            {/* 1. Identificación */}
            <section className="datos-cliente__seccion">
              <header>
                <h3>Identificación</h3>
                <small>Quién vende y a quién se expide la factura</small>
              </header>
              <dl className="evaluacion-resultado__resumen">
                <div>
                  <dt>Fecha</dt>
                  <dd>
                    {new Date().toLocaleDateString('es-CO', {
                      day: '2-digit',
                      month: 'short',
                      year: 'numeric',
                    })}
                  </dd>
                </div>
                <div>
                  <dt>Asesor</dt>
                  <dd>{detalle.data?.nombre_asesor || '—'}</dd>
                </div>
                <div>
                  <dt>Cliente</dt>
                  <dd>{nombreSolicitante}</dd>
                </div>
                <div>
                  <dt>Forma de pago</dt>
                  <dd>{solicitud?.lineaCredito ?? 'Contado'}</dd>
                </div>
              </dl>
              <div className="venta-contado__grid venta-contado__grid--2">
                <CampoEntrada
                  label="Asesor externo"
                  value={form.asesorExterno}
                  onChange={(e) => set('asesorExterno', e.target.value)}
                  placeholder="Opcional"
                />
                <CampoEntrada
                  label="Facturar a (1) — Documento"
                  value={form.facturarDoc}
                  onChange={(e) => set('facturarDoc', e.target.value)}
                  placeholder="NIT / C.C."
                />
                <CampoEntrada
                  label="Facturar a (1) — Nombre"
                  value={form.facturarNombre}
                  onChange={(e) => set('facturarNombre', e.target.value)}
                  placeholder="Razón social o persona"
                />
                <div className="datos-cliente__sino venta-contado__span2">
                  <span className="datos-cliente__sino-label" id="vc-facturar2">
                    Facturar también a un segundo tercero
                  </span>
                  <div
                    className="datos-cliente__sino-ops"
                    role="group"
                    aria-labelledby="vc-facturar2"
                  >
                    {(['No', 'Sí'] as const).map((opcion) => {
                      const activo = form.segundoFacturado === (opcion === 'Sí')
                      return (
                        <button
                          key={opcion}
                          type="button"
                          className={`datos-cliente__sino-op${
                            activo ? ' datos-cliente__sino-op--activo' : ''
                          }`}
                          onClick={() =>
                            set('segundoFacturado', opcion === 'Sí')
                          }
                        >
                          {opcion}
                        </button>
                      )
                    })}
                  </div>
                </div>
                {form.segundoFacturado && (
                  <>
                    <CampoEntrada
                      label="Facturar a (2) — Documento"
                      value={form.facturar2Doc}
                      onChange={(e) => set('facturar2Doc', e.target.value)}
                    />
                    <CampoEntrada
                      label="Facturar a (2) — Nombre"
                      value={form.facturar2Nombre}
                      onChange={(e) => set('facturar2Nombre', e.target.value)}
                    />
                  </>
                )}
              </div>
            </section>

            {/* 2. Vehículo */}
            <section className="datos-cliente__seccion">
              <header>
                <h3>Vehículo</h3>
                <small>
                  La moto que se entrega; motor y chasis alimentan el acta de
                  entrega
                </small>
              </header>
              <div className="venta-contado__grid">
                <CampoEntrada
                  label="Marca"
                  value={form.marca}
                  onChange={(e) => set('marca', e.target.value)}
                  placeholder="SUZUKI"
                  required
                />
                <CampoEntrada
                  label="Motocicleta (referencia)"
                  value={form.referencia}
                  onChange={(e) => set('referencia', e.target.value)}
                  placeholder="DR-160X"
                  required
                />
                <CampoEntrada
                  label="Año modelo"
                  value={form.modelo}
                  onChange={(e) => set('modelo', e.target.value)}
                  placeholder="2026"
                />
                <CampoEntrada
                  label="Color"
                  value={form.color}
                  onChange={(e) => set('color', e.target.value)}
                />
                <CampoEntrada
                  label="Ciudad de matrícula"
                  value={form.ciudadMatricula}
                  onChange={(e) => set('ciudadMatricula', e.target.value)}
                  placeholder="PALMIRA"
                />
                <CampoEntrada
                  label="N° motor"
                  value={form.motor}
                  onChange={(e) => set('motor', e.target.value)}
                />
                <CampoEntrada
                  label="N° chasis"
                  value={form.chasis}
                  onChange={(e) => set('chasis', e.target.value)}
                />
                <CampoEntrada
                  label="VIN"
                  value={form.vin}
                  onChange={(e) => set('vin', e.target.value)}
                />
              </div>
            </section>

            {/* 3. Liquidación */}
            <section className="datos-cliente__seccion">
              <header>
                <h3>Liquidación</h3>
                <small>Valor de la moto y gastos de la venta</small>
              </header>
              <div className="venta-contado__grid">
                <CampoNumerico
                  label="VR. MOTO (con IVA)"
                  value={form.valorMoto}
                  onValor={(v) => set('valorMoto', v)}
                  formatoMiles
                  required
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Descuento"
                  value={form.descuento}
                  onValor={(v) => set('descuento', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Matrícula"
                  value={form.matricula}
                  onValor={(v) => set('matricula', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Impuestos"
                  value={form.impuestos}
                  onValor={(v) => set('impuestos', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="SOAT"
                  value={form.soat}
                  onValor={(v) => set('soat', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Accesorios"
                  value={form.accesorios}
                  onValor={(v) => set('accesorios', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Otros gastos"
                  value={form.otrosGastos}
                  onValor={(v) => set('otrosGastos', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Anticipo"
                  value={form.anticipo}
                  onValor={(v) => set('anticipo', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
                <CampoNumerico
                  label="Retoma moto"
                  value={form.retoma}
                  onValor={(v) => set('retoma', v)}
                  formatoMiles
                  className="input-base"
                  contenedorClassName="venta-contado__money"
                />
              </div>
              <div className="venta-contado__totales">
                <div className="venta-contado__total">
                  <small>VR. Total</small>
                  <strong>{formatoCOP.format(vrTotal)}</strong>
                </div>
                <div className="venta-contado__total venta-contado__total--saldo">
                  <small>Saldo a pagar</small>
                  <strong>{formatoCOP.format(saldoPagar)}</strong>
                </div>
              </div>
              <div>
                <label className="label-base" htmlFor="vc-observaciones">
                  Observaciones
                </label>
                <textarea
                  id="vc-observaciones"
                  className="input-base"
                  rows={2}
                  value={form.observaciones}
                  onChange={(e) => set('observaciones', e.target.value)}
                  placeholder="INCLUYE SOAT, IMPUESTO Y MATRÍCULA…"
                />
              </div>
            </section>
          </>
        )}

        {guardada && (
          <div className="evaluacion-resultado__ok" role="status">
            <CheckCircle2 size={18} aria-hidden="true" />
            <p>
              Venta guardada — el paquete de documentos de la entrega
              (autorizaciones, transferencia de dominio y acta de entrega) quedó
              regenerado con estos datos.
            </p>
          </div>
        )}

        <h2>Facturación inmediata</h2>

        {factura == null ? (
          <>
            <p className="evaluacion-resultado__nota">
              Sube la factura emitida por el concesionario para cerrar la venta.
              El documento se lee y se verifica contra{' '}
              <strong>{form.facturarNombre.trim() || 'el cliente'}</strong>{' '}
              antes de aceptarse (PDF o imagen: JPEG, PNG, WEBP).
            </p>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={elegirArchivo}
            />
            {error && (
              <div className="evaluacion-resultado__error" role="alert">
                <AlertTriangle size={18} aria-hidden="true" />
                <p>{error}</p>
              </div>
            )}
            <div className="evaluacion-resultado__acciones">
              <Boton
                type="button"
                variante="secundario"
                iconoInicio={<ArrowLeft size={14} aria-hidden="true" />}
                onClick={onBack}
                disabled={ocupado}
              >
                Volver al perfil económico
              </Boton>
              {idSolicitud ? (
                <>
                  <Boton
                    type="button"
                    variante="secundario"
                    cargando={guardando}
                    iconoInicio={
                      !guardando ? (
                        <Save size={15} aria-hidden="true" />
                      ) : undefined
                    }
                    onClick={guardar}
                    disabled={ocupado}
                  >
                    {guardando ? 'Guardando…' : 'Guardar venta'}
                  </Boton>
                  <Boton
                    type="button"
                    cargando={subiendo}
                    iconoInicio={
                      !subiendo ? (
                        <Upload size={15} aria-hidden="true" />
                      ) : undefined
                    }
                    onClick={() => inputRef.current?.click()}
                    disabled={ocupado}
                  >
                    {subiendo ? 'Subiendo y verificando…' : 'Subir factura'}
                  </Boton>
                </>
              ) : (
                <Boton type="button" onClick={onFinalizar}>
                  Finalizar
                </Boton>
              )}
            </div>
          </>
        ) : (
          <>
            <div className="evaluacion-resultado__ok" role="status">
              <CheckCircle2 size={18} aria-hidden="true" />
              <p>
                Factura registrada — la venta de contado quedó cerrada y la
                solicitud pasó a <strong>Facturada</strong>.
              </p>
            </div>

            <dl className="evaluacion-resultado__resumen">
              <div>
                <dt>Archivo</dt>
                <dd>{factura.nombre}</dd>
              </div>
              <div>
                <dt>Factura N°</dt>
                <dd>{datosFactura?.numero_factura ?? '—'}</dd>
              </div>
              <div>
                <dt>Comprador</dt>
                <dd>{datosFactura?.nombre_comprador ?? '—'}</dd>
              </div>
              <div>
                <dt>Total factura</dt>
                <dd>
                  {datosFactura?.total != null
                    ? formatoCOP.format(Number(datosFactura.total))
                    : '—'}
                </dd>
              </div>
            </dl>

            {advertencias.length > 0 && (
              <ul className="evaluacion-resultado__advertencias">
                {advertencias.map((a, i) => (
                  <li key={i}>
                    <AlertTriangle size={14} aria-hidden="true" /> {a}
                  </li>
                ))}
              </ul>
            )}

            <div className="evaluacion-resultado__acciones">
              <Boton
                type="button"
                variante="secundario"
                iconoInicio={<Save size={14} aria-hidden="true" />}
                onClick={guardar}
                disabled={ocupado}
                cargando={guardando}
              >
                Guardar venta
              </Boton>
              <Boton
                type="button"
                variante="secundario"
                iconoInicio={<FileText size={14} aria-hidden="true" />}
                onClick={() => inputRef.current?.click()}
                disabled={ocupado}
              >
                Reemplazar factura
              </Boton>
              <input
                ref={inputRef}
                type="file"
                accept="application/pdf,image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={elegirArchivo}
              />
              <Boton type="button" onClick={onFinalizar}>
                Finalizar
              </Boton>
            </div>
          </>
        )}
      </section>
    </div>
  )
}
