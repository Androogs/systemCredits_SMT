import { MARCA } from '../../../shared/lib/marca'

/**
 * Panel de marca de las pantallas de acceso (login, recuperación y
 * restablecimiento de clave): mismo lado izquierdo para que las vistas
 * públicas de autenticación se vean como una sola familia.
 */

export default function VitrinaAcceso() {
  return (
    <section className="access-showcase" aria-label={MARCA.razonSocial}>
      <div className="access-showcase-glow" aria-hidden="true" />
      <div className="access-brand">
        <img
          src={MARCA.logoOscuro}
          alt={MARCA.razonSocial}
          width="900"
          height="129"
        />
      </div>

      <div className="access-showcase-content">
        <h1 className="access-title">Bienvenido</h1>
        <p className="access-description">
          Vive el poder de avanzar con Sumoto.
          <br />
          Respaldado por verdaderos expertos.
        </p>
      </div>

      <div className="access-finance-art" aria-hidden="true">
        <svg
          viewBox="0 0 440 190"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            x="100"
            y="20"
            width="228"
            height="148"
            rx="16"
            fill="white"
            fillOpacity=".1"
            stroke="white"
            strokeOpacity=".55"
            strokeWidth="2"
          />
          <rect x="120" y="39" width="46" height="7" rx="3.5" fill="#C5DAF5" />
          <path
            d="M120 62H250"
            stroke="white"
            strokeOpacity=".5"
            strokeLinecap="round"
            strokeWidth="3"
          />
          <rect
            x="120"
            y="79"
            width="84"
            height="67"
            rx="9"
            fill="#19255b"
            fillOpacity=".28"
          />
          <path
            d="M132 131V117M151 131V105M170 131V111M189 131V94"
            stroke="#C5DAF5"
            strokeLinecap="round"
            strokeWidth="7"
          />
          <path
            d="M220 91H294M220 109H278M220 127H287"
            stroke="white"
            strokeOpacity=".8"
            strokeLinecap="round"
            strokeWidth="5"
          />
          <path
            d="M220 91H260"
            stroke="white"
            strokeLinecap="round"
            strokeWidth="5"
          />
          <circle
            cx="326"
            cy="58"
            r="35"
            fill="#ffffff"
            stroke="#C5DAF5"
            strokeWidth="3"
          />
          <circle
            cx="326"
            cy="58"
            r="27"
            stroke="#0052a1"
            strokeOpacity=".45"
            strokeWidth="1.5"
          />
          <text
            x="326"
            y="70"
            fill="#0052a1"
            fontFamily="Roboto, Arial, sans-serif"
            fontSize="35"
            fontWeight="700"
            textAnchor="middle"
          >
            $
          </text>
          <path
            d="m78 35 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z"
            fill="#ffffff"
            fillOpacity=".9"
          />
        </svg>
      </div>

      <div className="access-showcase-footer">
        <span>Desarrollado por GaRi Software</span>
      </div>
    </section>
  )
}
