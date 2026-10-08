import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import RutasAplicacion from './app/routing/RutasAplicacion.tsx'

// El request() del API ya reintenta errores de red/5xx; React Query solo
// agrega caché, deduplicación y refetch al enfocar/invalidar.
const queryClient = new QueryClient({
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
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
