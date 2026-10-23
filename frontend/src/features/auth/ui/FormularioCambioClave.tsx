import { useState } from 'react'
import type { FormEvent } from 'react'
import { cambiarClave, ErrorAutenticacionApi } from '../api/autenticacionApi'
import { marcarClaveCambiada, useUsuario } from '../../../shared/lib/sesion'
import { emitirToast } from '../../../shared/lib/toastBus'
import Boton from '../../../shared/ui/Boton'
import CampoEntrada from '../../../shared/ui/CampoEntrada'

/** Cambio de clave propio, embebido en Ajustes > Cuenta. Obligatorio
 * cuando el admin entregó una clave temporal (`requiere_cambio_password`):
 * al guardarla, `marcarClaveCambiada` levanta el bloqueo del guard. */
export default function FormularioCambioClave() {
  const usuario = useUsuario()
  const obligatorio = Boolean(usuario?.requiere_cambio_password)

  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (nueva.length < 8) {
      setError('La nueva contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (nueva !== confirmar) {
      setError('La confirmación no coincide con la nueva contraseña.')
      return
    }
    setCargando(true)
    try {
      await cambiarClave(actual, nueva)
      marcarClaveCambiada()
      emitirToast({
        tipo: 'exito',
        mensaje: 'Contraseña actualizada correctamente.',
      })
      setActual('')
      setNueva('')
      setConfirmar('')
    } catch (cause) {
      setError(
        cause instanceof ErrorAutenticacionApi
          ? cause.message
          : 'No pudimos conectar con el servidor. Inténtalo de nuevo.',
      )
    } finally {
      setCargando(false)
    }
  }

  return (
    <div>
      {obligatorio && (
        <p className="mb-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
          Tu cuenta tiene una clave temporal. Por seguridad debes definir una
          contraseña propia antes de continuar usando el panel.
        </p>
      )}
      <form className="grid gap-4 md:grid-cols-3" onSubmit={submit}>
        <CampoEntrada
          label="Contraseña actual"
          type="password"
          value={actual}
          onChange={(e) => setActual(e.target.value)}
          autoComplete="current-password"
          maxLength={256}
          required
        />
        <CampoEntrada
          label="Nueva contraseña"
          type="password"
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
        />
        <CampoEntrada
          label="Confirmar nueva contraseña"
          type="password"
          value={confirmar}
          onChange={(e) => setConfirmar(e.target.value)}
          autoComplete="new-password"
          minLength={8}
          maxLength={128}
          required
        />
        {error && (
          <p className="text-sm text-red-600 md:col-span-3" role="alert">
            {error}
          </p>
        )}
        <div className="md:col-span-3">
          <Boton type="submit" cargando={cargando}>
            {cargando ? 'Guardando…' : 'Guardar nueva contraseña'}
          </Boton>
        </div>
      </form>
    </div>
  )
}
