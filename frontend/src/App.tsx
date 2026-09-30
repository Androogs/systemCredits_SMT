import { BrowserRouter } from 'react-router-dom'
// @ts-expect-error El módulo se mantiene en JSX durante la migración gradual a TypeScript.
import AppRoutes from './app/routing/AppRoutes.jsx'

function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  )
}

export default App
