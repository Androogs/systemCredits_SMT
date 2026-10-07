/**
 * Pruebas de contrato del cliente HTTP del frontend contra la API
 * (D48): forma de la URL, serialización del cuerpo y propagación
 * del detalle de error que devuelve el backend.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { env } from '../../../env'
import {
  ApiError,
  listarSolicitudes,
  obtenerSolicitud,
  seleccionarOferta,
} from './originacionApi'

const BASE = env.VITE_API_URL.replace(/\/$/, '')

function mockRespuesta(cuerpo: unknown, status = 200) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(cuerpo), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('listarSolicitudes', () => {
  it('consulta la colección sin parámetros por defecto', async () => {
    const fetchMock = mockRespuesta([])
    vi.stubGlobal('fetch', fetchMock)

    const datos = await listarSolicitudes()

    expect(datos).toEqual([])
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/api/solicitudes`,
      expect.objectContaining({
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })

  it('serializa los filtros como query params y omite vacíos', async () => {
    const fetchMock = mockRespuesta([])
    vi.stubGlobal('fetch', fetchMock)

    await listarSolicitudes({
      estado: 'rechazada',
      decision: 'aprobado',
      busqueda: 'ficticio',
      limite: 100,
      offset: 0,
    })

    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toBe(
      `${BASE}/api/solicitudes?estado=rechazada&decision=aprobado&busqueda=ficticio&limite=100&offset=0`,
    )
  })
})

describe('obtenerSolicitud', () => {
  it('consulta el detalle por id', async () => {
    const detalle = { id_solicitud: 'abc', causales: [], ofertas: [] }
    const fetchMock = mockRespuesta(detalle)
    vi.stubGlobal('fetch', fetchMock)

    const datos = await obtenerSolicitud('abc')

    expect(datos.id_solicitud).toBe('abc')
    expect(fetchMock).toHaveBeenCalledWith(
      `${BASE}/api/solicitudes/abc`,
      expect.anything(),
    )
  })

  it('propaga ApiError 404 con el detalle del backend', async () => {
    vi.stubGlobal(
      'fetch',
      mockRespuesta({ detail: 'No existe la solicitud abc' }, 404),
    )

    const error = await obtenerSolicitud('abc').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(404)
    expect((error as ApiError).detalle).toBe('No existe la solicitud abc')
  })
})

describe('seleccionarOferta', () => {
  it('envía el id de oferta en el cuerpo del POST', async () => {
    const fetchMock = mockRespuesta({ id_oferta: 7, seleccionada: true })
    vi.stubGlobal('fetch', fetchMock)

    await seleccionarOferta('sol-1', 7)

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`${BASE}/api/solicitudes/sol-1/ofertas/seleccionar`)
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toEqual({ id_oferta: 7 })
  })
})
