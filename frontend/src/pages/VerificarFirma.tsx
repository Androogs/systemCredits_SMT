/**
 * Verificación pública de la firma electrónica (OTP): es el destino del
 * QR estampado en los documentos de legalización. Permite a un tercero
 * contrastar que el documento fue firmado en la plataforma: muestra solo
 * lo impreso en la pieza legal (firmante, documento, fecha y solicitud).
 */
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, FileSignature, ShieldX } from 'lucide-react'
import { verificarFirma } from '../features/credit-origination/api/originacionApi'
import SelloAliado from '../shared/ui/SelloAliado'
import { MARCA } from '../shared/lib/marca'

export default function VerificarFirma() {
  const { uuid = '' } = useParams()
  const consulta = useQuery({
    queryKey: ['verificar-firma', uuid],
    queryFn: () => verificarFirma(uuid),
    retry: false,
    enabled: Boolean(uuid),
  })
  const datos = consulta.data

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-xl">
        <div className="mb-6 flex items-center justify-between gap-3">
          <img
            src={MARCA.logoClaro}
            alt={MARCA.razonSocial}
            width="900"
            height="129"
            className="h-6 w-auto object-contain"
          />
          <span className="flex items-center gap-1.5 text-xs font-semibold text-brand-500">
            <FileSignature size={16} aria-hidden="true" />
            Firma electrónica
          </span>
        </div>

        {consulta.isPending && (
          <p className="py-10 text-center text-sm text-slate-500">
            Verificando firma…
          </p>
        )}

        {consulta.isError && (
          <div className="text-center">
            <ShieldX size={48} className="mx-auto text-red-500" />
            <h1 className="mt-4 text-lg font-semibold text-slate-900">
              Firma no verificada
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Este código no corresponde a una firma electrónica registrada. El
              documento pudo haber sido alterado o el enlace está incompleto.
            </p>
          </div>
        )}

        {datos && (
          <div>
            <div className="text-center">
              <BadgeCheck size={48} className="mx-auto text-emerald-500" />
              <h1 className="mt-4 text-lg font-semibold text-slate-900">
                Firma electrónica verificada
              </h1>
              <p className="mt-1 text-sm text-slate-500">
                El documento fue firmado digitalmente (OTP) en la plataforma.
              </p>
            </div>
            <dl className="mt-6 space-y-3 border-t border-slate-100 pt-6 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Firmante</dt>
                <dd className="text-right font-medium text-slate-900">
                  {datos.firmante}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Documento</dt>
                <dd className="font-medium text-slate-900">
                  {datos.documento_identidad}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Solicitud</dt>
                <dd className="font-medium text-slate-900">
                  N.º {datos.num_solicitud}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Fecha de firma</dt>
                <dd className="text-right font-medium text-slate-900">
                  {datos.fecha_hora_firma
                    ? new Date(datos.fecha_hora_firma).toLocaleString('es-CO', {
                        dateStyle: 'long',
                        timeStyle: 'short',
                      })
                    : '—'}
                </dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Documentos firmados</dt>
                <dd className="font-medium text-slate-900">
                  {datos.documentos}
                </dd>
              </div>
            </dl>
            <p className="mt-6 break-all text-center text-[11px] text-slate-400">
              {datos.uuid_firma}
            </p>
          </div>
        )}

        <div className="mt-8 flex justify-center border-t border-slate-100 pt-5">
          <SelloAliado leyenda="Los documentos del crédito son emitidos por nuestra financiera aliada." />
        </div>
      </div>
    </div>
  )
}
