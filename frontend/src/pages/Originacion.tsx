import DemoShell from '../features/credit-origination/ui/DemoShell/DemoShell'

/** Reutiliza el flujo de validaciÃ³n existente dentro del portal operativo. */
export default function Originacion() {
  return <DemoShell embedded onExit={() => undefined} />
}
