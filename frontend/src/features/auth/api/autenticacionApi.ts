import { env } from '../../../env'

const API = import.meta.env.DEV ? '' : env.VITE_API_URL.replace(/\/$/, '')

export interface UsuarioAutenticado {
  correo: string
  nombre: string
  rol: string
}

interface RespuestaLogin {
  usuario: UsuarioAutenticado
}

export class ErrorAutenticacionApi extends Error {
  readonly status: number

  constructor(status: number, detalle: unknown) {
    super(
      typeof detalle === 'string'
        ? detalle
        : `No fue posible iniciar sesión (error ${status}).`,
    )
    this.name = 'ErrorAutenticacionApi'
    this.status = status
  }
}

export async function iniciarSesion(correo: string, contrasena: string) {
  const respuesta = await fetch(`${API}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ correo, contrasena }),
  })
  const cuerpo: unknown = await respuesta.json().catch(() => null)

  if (!respuesta.ok) {
    const detalle =
      cuerpo && typeof cuerpo === 'object' && 'detail' in cuerpo
        ? cuerpo.detail
        : `No fue posible iniciar sesión (error ${respuesta.status}).`
    throw new ErrorAutenticacionApi(respuesta.status, detalle)
  }

  if (
    !cuerpo ||
    typeof cuerpo !== 'object' ||
    !('usuario' in cuerpo) ||
    !cuerpo.usuario ||
    typeof cuerpo.usuario !== 'object' ||
    !('correo' in cuerpo.usuario) ||
    typeof cuerpo.usuario.correo !== 'string' ||
    !('nombre' in cuerpo.usuario) ||
    typeof cuerpo.usuario.nombre !== 'string' ||
    !('rol' in cuerpo.usuario) ||
    typeof cuerpo.usuario.rol !== 'string'
  ) {
    throw new Error(
      'La API devolvió una respuesta de inicio de sesión inválida.',
    )
  }

  return cuerpo as RespuestaLogin
}
