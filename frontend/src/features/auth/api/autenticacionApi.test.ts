import { afterEach, describe, expect, it, vi } from 'vitest'
import { env } from '../../../env'
import { ErrorAutenticacionApi, iniciarSesion } from './autenticacionApi'

const BASE = env.VITE_API_URL.replace(/\/$/, '')
const API = import.meta.env.DEV ? '' : BASE

function mockRespuesta(cuerpo: unknown, status = 200) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(cuerpo), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('API de autenticación', () => {
  it('envía las credenciales al backend y devuelve el usuario', async () => {
    const usuario = {
      correo: 'demo@underwriting.io',
      nombre: 'Usuario de demostración',
      rol: 'Administrador',
    }
    const fetchMock = mockRespuesta({ usuario })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      iniciarSesion('demo@underwriting.io', 'demo1234'),
    ).resolves.toEqual({ usuario })
    expect(fetchMock).toHaveBeenCalledWith(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        correo: 'demo@underwriting.io',
        contrasena: 'demo1234',
      }),
    })
  })

  it('propaga los errores de autenticación del backend', async () => {
    vi.stubGlobal(
      'fetch',
      mockRespuesta({ detail: 'Correo o contraseña incorrectos.' }, 401),
    )

    await expect(
      iniciarSesion('demo@underwriting.io', 'incorrecta'),
    ).rejects.toMatchObject({
      name: 'ErrorAutenticacionApi',
      status: 401,
      message: 'Correo o contraseña incorrectos.',
    } satisfies Partial<ErrorAutenticacionApi>)
  })
})
