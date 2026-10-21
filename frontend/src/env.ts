import { z } from 'zod'

// VITE_API_URL vacío = llamadas relativas a /api (mismo origen): en dev las
// reenvía el proxy de Vite (vite.config.ts → API_PROXY_TARGET); en
// producción, definir la URL absoluta de la API publicada.
const envSchema = z.object({
  VITE_API_URL: z.string().url().or(z.literal('')),
  VITE_DEMO: z.string().optional(),
})

export const env = envSchema.parse({
  VITE_API_URL: import.meta.env.VITE_API_URL ?? '',
  VITE_DEMO: import.meta.env.VITE_DEMO,
})

/* Superficies de demostración (selector de escenario, OTP impreso,
 * precargas, badge "Modo de demostración"): activas en dev y en builds
 * que definan VITE_DEMO=true — nunca en el build de producción. */
export const MODO_DEMO = import.meta.env.DEV || env.VITE_DEMO === 'true'
