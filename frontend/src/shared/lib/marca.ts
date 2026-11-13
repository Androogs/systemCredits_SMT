/**
 * Marca única: SUMOTO S.A.
 *
 * SUMOTO S.A. opera la plataforma, radica la solicitud y es también la
 * financiera que estudia y aprueba el crédito.
 */

export const MARCA = {
  nombre: 'SUMOTO',
  razonSocial: 'SUMOTO S.A.',
  plataforma: 'Plataforma de consulta de crédito',
  logoClaro: '/brand/sumoto-bicolor.png', // sobre fondo blanco
  logoOscuro: '/brand/sumoto-blanco.png', // sobre fondo azul marino
  isotipoClaro: '/brand/sm-bicolor.png',
  isotipoOscuro: '/brand/sm-blanco.png',
} as const

export const ALIADO = {
  nombre: 'SUMOTO S.A',
  rol: 'Financiera aliada',
  logoClaro: '/brand/sm-bicolor.png',
  logoOscuro: '/brand/sm-blanco.png',
} as const

/** Título de pestaña con la marca principal. */
export const tituloPagina = (seccion: string) => `${seccion} | ${MARCA.nombre}`
