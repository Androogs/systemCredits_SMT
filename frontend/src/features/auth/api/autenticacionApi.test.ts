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
  it('envía las credenciales al backend y devuelve token + usuario', async () => {
    const respuesta = {
      access_token: 'jwt.de.prueba',
      token_type: 'bearer',
      usuario: {
        correo: 'admin@sumoto.com.co',
        nombre: 'Administrador',
        rol: 'admin',
        roles: ['admin'],
        concesionario: null,
      },
    }
    const fetchMock = mockRespuesta(respuesta)
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      iniciarSesion('admin@sumoto.com.co', 'demo1234'),
    ).resolves.toEqual(respuesta)
    expect(fetchMock).toHaveBeenCalledWith(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        correo: 'admin@sumoto.com.co',
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
