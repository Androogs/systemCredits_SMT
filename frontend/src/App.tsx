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
 */
function notificarErrorGlobal(error: unknown) {
  if (error instanceof ApiError && error.status > 0 && error.status < 500) {
    return
  }
  emitirToast({
    tipo: 'error',
    titulo: 'Sin respuesta del servidor',
    mensaje:
      error instanceof Error
        ? error.message
        : 'Error inesperado de red. Reintenta.',
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
