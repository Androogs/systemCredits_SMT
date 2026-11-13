/**
 * Catálogo de concesionarios aliados y marcas de motos financiables.
 *
 * La marca se sugiere automáticamente según el concesionario donde
 * opera el asesor de la cuenta ('Bajaj Tuluá' → 'Bajaj'); el asesor
 * puede cambiarla si el cliente elige otra referencia.
 */

/** Marcas aliadas que operan como concesionarios (una fila por marca en
 *  la tabla `concesionario` por cada sede: '<MARCA> <SEDE>'). SUMOTO S.A
 *  es la empresa que opera la plataforma, no un concesionario. */
export const CONCESIONARIOS: string[] = [
  'AKT',
  'Auteco',
  'Bajaj',
  'Fratelli',
  'Hero',
  'Honda',
  'Suzuki',
]

/** Catálogo comercial vigente: sedes disponibles por marca (usado en
 *  los filtros del panel y en Ajustes → Concesionarios). */
export const SEDES_POR_MARCA: Record<string, string[]> = {
  AKT: [
    'Principal',
    'Centro',
    'Cali',
    'Buga',
    'Yumbo',
    'Candelaria',
    'Pradera',
  ],
  Auteco: ['Cali'],
  Bajaj: ['Palmira', 'Pradera', 'Florida'],
  Fratelli: [],
  Hero: ['Palmira', 'Cali', 'Florida'],
  Honda: [],
  Suzuki: [
    'Principal',
    'Centro',
    'El Cerrito',
    'Candelaria',
    'Florida',
    'Pradera',
  ],
}

/** Concesionarios derivados del catálogo: nombre "<Marca> <Sede>" como
 *  los registra el backend; marcas sin sede quedan con su nombre. */
export const CONCESIONARIOS_CATALOGO: string[] = Object.entries(
  SEDES_POR_MARCA,
).flatMap(([marca, sedes]) =>
  sedes.length ? sedes.map((sede) => `${marca} ${sede}`) : [marca],
)

export const MARCAS_VEHICULO: string[] = [
  'AKT',
  'Auteco',
  'Bajaj',
  'Fratelli',
  'Hero',
  'Honda',
  'Suzuki',
  'Otra',
]

/** Marcas distribuidas por Auteco: se despliegan como submenú de
 * 'Auteco' en el selector de marca de la formalización. */
export const SUBMARCAS_AUTECO: string[] = [
  'Ceronte',
  'Kymco',
  'TVS',
  'Victory',
  'Zontes',
]

/** Referencias comerciales frecuentes por marca (sugerencias del asesor;
 * el campo sigue aceptando texto libre para modelos no listados). */
export const REFERENCIAS_VEHICULO: Record<string, string[]> = {
  Suzuki: [
    'GN 125',
    'GIXXER 150',
    'GIXXER 250',
    'VIVA R 110',
    'VIVA FI 115',
    'AX4',
    'DR 150',
    'BEST 125',
    'NKD 125',
  ],
  Hero: [
    'Splendor+ 100',
    'Eco 100',
    'Eco 150',
    'Hunk 150',
    'Hunk 160R',
    'Ignitor 125',
    'Xpulse 200',
    'Dash 110',
  ],
  Bajaj: [
    'Boxer CT 100',
    'Boxer 150',
    'Pulsar NS 125',
    'Pulsar NS 160 FI',
    'Pulsar NS 200',
    'Pulsar N 250',
    'Discover 125',
    'Platino 110',
    'Dominar 400',
  ],
  Honda: [
    'CB 125F',
    'CBF 160',
    'CB 190R',
    'XR 150L',
    'XR 190L',
    'Navi 110',
    'PCX 160',
  ],
  AKT: ['NKD 125', 'CR4 125', 'CR5 180', 'Dynamic Pro 150', 'Jet 125'],
}
