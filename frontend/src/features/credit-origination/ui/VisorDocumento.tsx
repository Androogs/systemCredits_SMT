import { useEffect, useRef, useState } from 'react'
import { renderAsync } from 'docx-preview'
import { Download, X } from 'lucide-react'
import {
  bufferAutenticado,
  descargarArchivoAutenticado,
} from '../../../shared/lib/archivoAutenticado'

interface VisorDocumentoProps {
  /** URL protegida del .docx a previsualizar. */
  url: string
  nombre: string
  onCerrar: () => void
}

/** Modal que renderiza un .docx en el navegador (docx-preview) sin
 * descargarlo. */
export default function VisorDocumento({
  url,
  nombre,
  onCerrar,
}: VisorDocumentoProps) {
  const contenedor = useRef<HTMLDivElement>(null)
  const [estado, setEstado] = useState<'cargando' | 'error' | 'listo'>(
    'cargando',
  )

  useEffect(() => {
    let vivo = true
    setEstado('cargando')
    bufferAutenticado(url)
      .then((buf) =>
        vivo && contenedor.current
          ? renderAsync(buf, contenedor.current, undefined, {
              inWrapper: true,
              breakPages: true,
            }).then(() => {
              if (vivo) setEstado('listo')
            })
          : null,
      )
      .catch(() => {
        if (vivo) setEstado('error')
      })
    return () => {
      vivo = false
    }
  }, [url])

  useEffect(() => {
    const cerrar = (e: KeyboardEvent) => e.key === 'Escape' && onCerrar()
    window.addEventListener('keydown', cerrar)
    return () => window.removeEventListener('keydown', cerrar)
  }, [onCerrar])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={`Vista previa de ${nombre}`}
      onClick={(e) => e.target === e.currentTarget && onCerrar()}
    >
      <div className="flex h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <header className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-3">
          <h3 className="truncate text-sm font-semibold text-slate-800">
            {nombre}
          </h3>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => descargarArchivoAutenticado(url, nombre)}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-50"
            >
              <Download size={14} /> Descargar
            </button>
            <button
              type="button"
              onClick={onCerrar}
              aria-label="Cerrar vista previa"
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto bg-slate-100 p-4">
          {estado === 'cargando' && (
            <p className="py-16 text-center text-sm text-slate-500">
              Cargando documento…
            </p>
          )}
          {estado === 'error' && (
            <p className="py-16 text-center text-sm text-slate-500">
              No se pudo previsualizar. Usa la opción de descarga.
            </p>
          )}
          <div
            ref={contenedor}
            className="visor-docx mx-auto max-w-3xl"
            style={{ zoom: 0.72 }}
          />
        </div>
      </div>
    </div>
  )
}
