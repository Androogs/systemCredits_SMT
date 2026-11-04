/**
 * Co-marca SUMOTO + Inversiones Pacífico.
 *
 * SUMOTO S.A. es la marca principal: opera la plataforma y radica la
 * solicitud. Inversiones Pacífico es la financiera aliada que estudia y
 * aprueba el crédito; aparece SOLO como sello secundario de respaldo.
 *
 * Este es el único componente que pinta la identidad de Pacífico. Si cambia
 * el aliado o su logo, se ajusta aquí y en shared/lib/marca.ts.
 */

import { ALIADO } from '../lib/marca'

type Formato = 'sello' | 'powered' | 'texto'
type Tono = 'claro' | 'oscuro'

interface SelloAliadoProps {
  /**
   * sello: tarjeta con rótulo «Financiera aliada» + logo (login, resultado).
   * powered: línea compacta «Respaldo financiero de» + logo (pies, barra).
   * texto: solo texto, para frases dentro de contenido.
   */
  formato?: Formato
  /** claro = sobre fondo blanco; oscuro = sobre fondo azul marino. */
  tono?: Tono
  className?: string
  /** Texto opcional que acompaña al sello (formato «sello»). */
  leyenda?: string
}

export default function SelloAliado({
  formato = 'sello',
  tono = 'claro',
  className = '',
  leyenda,
}: SelloAliadoProps) {
  const oscuro = tono === 'oscuro'
  const logo = oscuro ? ALIADO.logoOscuro : ALIADO.logoClaro
  const textoSuave = oscuro ? 'text-white/60' : 'text-slate-500'

  if (formato === 'texto') {
    return (
      <span className={`${textoSuave} ${className}`}>
        {ALIADO.rol}:{' '}
        <strong className={oscuro ? 'text-white/85' : 'text-slate-700'}>
          {ALIADO.nombre}
        </strong>
      </span>
    )
  }

  if (formato === 'powered') {
    return (
      <div
        className={`flex items-center gap-2 ${textoSuave} ${className}`}
        aria-label={`${ALIADO.rol}: ${ALIADO.nombre}`}
      >
        <span className="text-[10px] font-medium uppercase tracking-[0.12em] whitespace-nowrap translate-y-0.5">
          {ALIADO.rol}
        </span>
        <img
          src={logo}
          alt={ALIADO.nombre}
          width="520"
          height="148"
          className="h-6 w-auto object-contain"
        />
      </div>
    )
  }

  return (
    <div
      className={`inline-flex flex-col items-center gap-1.5 rounded-xl border px-4 py-2.5 ${
        oscuro ? 'border-white/15 bg-white/5' : 'border-slate-200 bg-white'
      } ${className}`}
    >
      <span
        className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${textoSuave}`}
      >
        {ALIADO.rol}
      </span>
      <img
        src={logo}
        alt={ALIADO.nombre}
        width="520"
        height="148"
        className="h-8 w-auto object-contain"
      />
      {leyenda && (
        <span className={`max-w-[18rem] text-center text-[11px] ${textoSuave}`}>
          {leyenda}
        </span>
      )}
    </div>
  )
}
