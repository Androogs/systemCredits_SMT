/**
 * Co-marca SUMOTO + Inversiones Pacífico.
 *
 * SUMOTO S.A. es la marca principal: opera la plataforma y radica la
 * solicitud. Inversiones Pacífico es la financiera aliada que estudia y
 * aprueba el crédito; aparece SOLO como sello secundario de respaldo.
 *
 * Constantes de co-marca. SelloAliado.tsx es el único componente que pinta
 * la identidad de Pacífico.
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
  nombre: 'Inversiones Pacífico',
  rol: 'Financiera aliada',
  logoClaro: '/brand/pacifico-sello-azul.png',
  logoOscuro: '/brand/pacifico-sello-blanco.png',
} as const

/** Título de pestaña con la marca principal. */
export const tituloPagina = (seccion: string) => `${seccion} | ${MARCA.nombre}`
