/**
 * Binarios protegidos por JWT: el token vive en memoria/localStorage, así que
 * <img src>, <video src>, <a href> y fetch() pelado llegan a la API sin
 * Authorization y reciben 401. Estos helpers resuelven fetch + Bearer →
 * Blob → objectURL para previsualizar y descargar.
 */

import { useEffect, useState } from 'react'
import { fetchAutenticado } from './fetchAutenticado'
import { emitirToast } from './toastBus'

async function fetchBlobAutenticado(url: string): Promise<Blob> {
  // El helper rota el refresh ante 401 (o limpia sesión + redirect).
  const respuesta = await fetchAutenticado(url)
  if (!respuesta.ok) throw new Error(`HTTP ${respuesta.status}`)
  return respuesta.blob()
}

/** objectURL de una URL protegida para usar como src de <img>/<video>. */
export function useUrlObjetoAutenticado(url: string | null): string | null {
  const [objUrl, setObjUrl] = useState<string | null>(null)
  useEffect(() => {
    if (!url) {
      setObjUrl(null)
      return
    }
    let vivo = true
    let creado: string | null = null
    fetchBlobAutenticado(url)
      .then((blob) => {
        if (!vivo) return
        creado = URL.createObjectURL(blob)
        setObjUrl(creado)
      })
      .catch(() => {
        if (vivo) setObjUrl(null)
      })
    return () => {
      vivo = false
      if (creado) URL.revokeObjectURL(creado)
    }
  }, [url])
  return objUrl
}

/** Buffer del recurso para renderers en cliente (docx-preview). */
export function bufferAutenticado(url: string): Promise<ArrayBuffer> {
  return fetchBlobAutenticado(url).then((b) => b.arrayBuffer())
}

/** Descarga un recurso protegido forzando nombre de archivo. */
export async function descargarArchivoAutenticado(
  url: string,
  nombre?: string,
): Promise<void> {
  try {
    const blob = await fetchBlobAutenticado(url)
    const obj = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = obj
    a.download = nombre ?? ''
    a.click()
    setTimeout(() => URL.revokeObjectURL(obj), 10_000)
  } catch {
    emitirToast({ tipo: 'error', mensaje: 'No se pudo descargar el archivo.' })
  }
}
