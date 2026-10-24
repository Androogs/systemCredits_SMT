/**
 * Catálogo de concesionarios aliados y marcas de motos financiables.
 *
 * La marca se sugiere automáticamente según el concesionario donde
 * opera el asesor de la cuenta ('Bajaj Tuluá' → 'Bajaj'); el asesor
 * puede cambiarla si el cliente elige otra referencia.
 */

export const CONCESIONARIOS: string[] = [
  'Bajaj Tuluá',
  'Hero Cali',
  'Suzuki Palmira',
]

export const MARCAS_VEHICULO: string[] = [
  'AKT',
  'Auteco',
  'Bajaj',
  'Fratelli',
  'Hero',
  'Honda',
  'Suzuki',
  'Yamaha',
  'Otra',
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
  Yamaha: [
    'SZ-RR 150',
    'FZ 150',
    'FZ 250',
    'N-Max 155',
    'Crypton 115',
    'Libero 125',
    'MT-03',
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
  KTM: ['Duke 200', 'Duke 250', 'Duke 390', 'RC 200', 'Adventure 250'],
  TVS: [
    'Sport 100',
    'Raider 125',
    'Apache RTR 160',
    'Apache RTR 200',
    'NTorq 125',
  ],
  AKT: ['NKD 125', 'CR4 125', 'CR5 180', 'Dynamic Pro 150', 'Jet 125'],
  Victory: ['MRX 150', 'Switch 150', 'Venom 18', 'Life 125'],
  'Royal Enfield': ['Hunter 350', 'Classic 350', 'Meteor 350', 'Himalayan 411'],
}
