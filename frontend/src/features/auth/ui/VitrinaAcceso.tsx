/**
 * Panel de marca de las pantallas de acceso (login, recuperación y
 * restablecimiento de clave): mismo lado izquierdo para que las vistas
 * públicas de autenticación se vean como una sola familia.
 */

export default function VitrinaAcceso() {
  return (
    <section className="access-showcase" aria-label="Inversiones Pacífico">
      <div className="access-showcase-glow" aria-hidden="true" />
      <div className="access-brand">
        <img
          src="/brand/pacifico-blancos.png"
          alt="Inversiones Pacífico"
          width="580"
          height="274"
        />
      </div>

      <div className="access-showcase-content">
        <h1 className="access-title">Bienvenido</h1>
        <p className="access-description">
          Sigamos transformando vidas generando oportunidades de realización
          personal.
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
            fillOpacity=".06"
            stroke="white"
            strokeOpacity=".3"
            strokeWidth="2"
          />
          <rect
            x="120"
            y="39"
            width="46"
            height="7"
            rx="3.5"
            fill="#8DE3F7"
            fillOpacity=".9"
          />
          <path
            d="M120 62H250"
            stroke="white"
            strokeOpacity=".4"
            strokeLinecap="round"
            strokeWidth="3"
          />
          <rect
            x="120"
            y="79"
            width="84"
            height="67"
            rx="9"
            fill="#55C5E5"
            fillOpacity=".18"
          />
          <path
            d="M132 131V117M151 131V105M170 131V111M189 131V94"
            stroke="#8DE3F7"
            strokeLinecap="round"
            strokeWidth="7"
          />
          <path
            d="M220 91H294M220 109H278M220 127H287"
            stroke="white"
            strokeOpacity=".64"
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
            fill="#55C5E5"
            stroke="#D6F8FF"
            strokeWidth="3"
          />
          <circle
            cx="326"
            cy="58"
            r="27"
            stroke="white"
            strokeOpacity=".55"
            strokeWidth="1.5"
          />
          <text
            x="326"
            y="70"
            fill="#00345C"
            fontFamily="Inter, Arial, sans-serif"
            fontSize="35"
            fontWeight="700"
            textAnchor="middle"
          >
            $
          </text>
          <path
            d="m78 35 3 7 7 3-7 3-3 7-3-7-7-3 7-3 3-7Z"
            fill="#B8F0FF"
            fillOpacity=".8"
          />
        </svg>
      </div>

      <div className="access-showcase-footer">
        <span>INVERSIONES PACÍFICO</span>
        <span>Confianza que impulsa.</span>
      </div>
    </section>
  )
}
