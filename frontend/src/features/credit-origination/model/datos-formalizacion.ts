/** Estado del formulario de datos del cliente en la formalización y su
 * mapeo desde el detalle de la API (retomar una solicitud ya guardada). */

export type ValorSiNo = '' | 'si' | 'no'

export interface DatosForm {
  viaPrincipal: string
  numeroVia: string
  letraVia: string
  sector: string
  numeroCruce: string
  letraCruce: string
  numeroFinal: string
  otrasCaracteristicas: string
  barrio: string
  ciudad: string
  estrato: string
  tipoVivienda: string
  zonaRural: ValorSiNo
  estadoCivil: string
  personasACargo: string
  numHijos: string
  esCabezaFamilia: ValorSiNo
  bienesRaices: ValorSiNo
  cuentaVehiculo: ValorSiNo
  tieneMoto: ValorSiNo
  tieneCarro: ValorSiNo
  primeraMoto: ValorSiNo
  /** 'moto' → estoy_financiando = true; 'otro' → false. */
  queFinancia: 'moto' | 'otro'
  nombreEmpresa: string
  ciudadEmpresa: string
  fechaIngreso: string
  nivelEducativo: string
  profesion: string
  cargo: string
  actividadComercial: string
}

const siNoDesdeBool = (v: boolean | null | undefined): ValorSiNo =>
  v == null ? '' : v ? 'si' : 'no'

const textoDesde = (v: string | number | null | undefined): string =>
  v == null ? '' : String(v)

/** Construye el estado inicial del formulario desde el detalle de la API.
 * La dirección ya va compuesta y no se desarma: se muestra como
 * referencia al asesor. */
export function datosFormDesdeApi(
  contacto: Record<string, unknown> | null | undefined,
  laboral: Record<string, unknown> | null | undefined,
): Partial<DatosForm> {
  if (!contacto && !laboral) return {}
  const txt = (v: unknown) => textoDesde(v as string | number | null)
  const sn = (v: unknown) => siNoDesdeBool(v as boolean | null)
  return {
    barrio: txt(contacto?.barrio),
    ciudad: txt(contacto?.ciudad),
    estrato: txt(contacto?.estrato),
    tipoVivienda: txt(contacto?.tipo_vivienda),
    zonaRural: sn(contacto?.zona_rural),
    estadoCivil: txt(contacto?.estado_civil),
    personasACargo: txt(contacto?.personas_a_cargo),
    numHijos: txt(contacto?.num_hijos),
    esCabezaFamilia: sn(contacto?.es_cabeza_familia),
    bienesRaices: sn(contacto?.cuenta_bienes_raices),
    cuentaVehiculo: sn(contacto?.cuenta_vehiculo),
    tieneMoto: sn(contacto?.tiene_moto),
    tieneCarro: sn(contacto?.tiene_carro),
    primeraMoto: sn(contacto?.primera_moto),
    queFinancia: contacto?.estoy_financiando === false ? 'otro' : 'moto',
    nombreEmpresa: txt(laboral?.nombre_empresa),
    ciudadEmpresa: txt(laboral?.ciudad_empresa),
    fechaIngreso: txt(laboral?.fecha_ingreso),
    nivelEducativo: txt(laboral?.nivel_educativo),
    profesion: txt(laboral?.profesion),
    cargo: txt(laboral?.cargo),
    actividadComercial: txt(laboral?.actividad_comercial),
  }
}
