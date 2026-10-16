import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '')
  // Destino del proxy /api en dev (independiente de VITE_API_URL, que puede
  // quedar vacío para llamadas relativas del mismo origen — p. ej. cuando el
  // celular entra por un túnel HTTPS hacia este dev server).
  // Debe coincidir con el puerto del backend (README: uvicorn en 8000;
  // frontend/.env → API_PROXY_TARGET=http://127.0.0.1:8000). El fallback
  // anterior apuntaba a 8001 y cualquier dev sin .env terminaba con
  // "Error HTTP 502" del proxy (ECONNREFUSED) + toast "Sin respuesta".
  const apiUrl = fileEnv.API_PROXY_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      // Dominios de túneles gratuitos para probar la captura desde el celular
      // (getUserMedia exige HTTPS).
      allowedHosts: [
        '.trycloudflare.com',
        '.loca.lt',
        '.ngrok-free.app',
        '.ngrok.io',
      ],
      proxy: {
        '/api': {
          target: apiUrl,
          changeOrigin: true,
        },
      },
    },
    test: {
      // Los specs de e2e/ son de Playwright (npm run test:e2e), no de Vitest.
      exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    },
  }
})
