import { BrowserRouter } from 'react-router-dom'
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from '@tanstack/react-query'
import RutasAplicacion from './app/routing/RutasAplicacion.tsx'
import Toasts from './shared/ui/Toasts.tsx'
import { emitirToast } from './shared/lib/toastBus.ts'
import { ApiError } from './features/credit-origination/api/originacionApi.ts'

/**
 * D83 — feedback visual ante fallos de red. Solo se notifican errores de
 * conexión/timeout (status 0) y 5xx: los 4xx (validación, duplicados, etc.)
 * ya los maneja cada formulario en sitio con sus propias alertas.
 *
 * Nota 502: tiene dos orígenes distintos y el título genérico anterior
 * ("Sin respuesta del servidor") confundía:
 *  - proxy de Vite sin backend detrás (ECONNREFUSED) → cuerpo HTML, sin JSON.
 *  - backend que SÍ respondió con DataCreditoError (Experian sin credenciales).
 */
function notificarErrorGlobal(error: unknown) {
  if (error instanceof ApiError && error.status > 0 && error.status < 500) {
    return
  }
  const mensaje =
    error instanceof Error
      ? error.message
      : 'Error inesperado de red. Reintenta.'
  let titulo = 'Sin respuesta del servidor'
  if (error instanceof ApiError) {
    if (error.status === 0) {
      titulo = 'Sin respuesta del servidor'
    } else if (
      error.status === 502 &&
      /proxy de desarrollo|backend no respondió|API_PROXY_TARGET/i.test(mensaje)
    ) {
      titulo = 'Backend no disponible (502 del proxy)'
    } else if (
      error.status === 502 &&
      /experian|datacr[eé]dito|HDC_|INCOME_|configuraci[oó]n/i.test(mensaje)
    ) {
      titulo = 'Error de Experian (502 del backend)'
    } else if (error.status >= 500) {
      titulo = `Error del servidor (${error.status})`
    }
  }
  emitirToast({
    tipo: 'error',
    titulo,
    mensaje,
  })
}

// El request() del API ya reintenta errores de red/5xx; React Query solo
// agrega caché, deduplicación y refetch al enfocar/invalidar.
const queryClient = new QueryClient({
  queryCache: new QueryCache({ onError: notificarErrorGlobal }),
  mutationCache: new MutationCache({ onError: notificarErrorGlobal }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RutasAplicacion />
        <Toasts />
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
