{
  /* <span>demo@underwriting.io</span>
  <span>demo1234</span>*/
}

import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { FormEvent } from 'react'
import {
  ErrorAutenticacionApi,
  iniciarSesion,
} from '../features/auth/api/autenticacionApi'
import { guardarRol, guardarNombre, type RolSesion } from '../shared/lib/sesion'
import './IniciarSesion.css'

const USUARIO_DEMO = 'demo@underwriting.io'
const CONTRASENA_DEMO = 'demo1234'

export default function IniciarSesion() {
  const navigate = useNavigate()
  const [email, setEmail] = useState(USUARIO_DEMO)
  const [password, setPassword] = useState(CONTRASENA_DEMO)
  const [showPassword, setShowPassword] = useState(false)
  const [rol, setRol] = useState<RolSesion>('asesor')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    document.title = 'Iniciar sesión | Inversiones Pacífico'
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      const respuesta = await iniciarSesion(email.trim(), password)
      localStorage.setItem('uw_auth', '1')
      guardarRol(rol)
      guardarNombre(respuesta.usuario.nombre)
      navigate('/dashboard')
    } catch (cause) {
      setError(
        cause instanceof ErrorAutenticacionApi
          ? cause.message
          : 'No pudimos conectar con el servidor. Verifica que la API esté disponible e inténtalo de nuevo.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="access-shell">
      <main className="access-card">
        <div className="access-mobile-brand">
          <img
            src="/brand/pacifico-blancos.png"
            alt="Inversiones Pacífico"
            width="580"
            height="274"
          />
        </div>

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
                stroke="#8DE3F7"
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

        <section className="access-form-panel" aria-labelledby="login-heading">
          <div className="access-form-content">
            <div className="access-security">
              <span className="access-security-icon">
                <ShieldCheck size={17} aria-hidden="true" />
              </span>
              <span>Acceso seguro | Tus datos están protegidos</span>
            </div>

            <header className="access-form-header">
              <p className="access-welcome">¡Qué bueno tenerte de vuelta!</p>
              <h2 id="login-heading" className="access-form-title">
                Inicia sesión
              </h2>
              <p className="access-form-subtitle">
                Ingresa tus credenciales para continuar en tu espacio de
                trabajo.
              </p>
            </header>

            <form className="access-form" onSubmit={submit}>
              <div className="access-field">
                <label htmlFor="login-username">Correo electrónico</label>
                <div className="access-input-wrap">
                  <Mail size={18} aria-hidden="true" />
                  <input
                    id="login-username"
                    type="email"
                    value={email}
                    onChange={(event) => {
                      setEmail(event.target.value)
                      setError('')
                      setMessage('')
                    }}
                    placeholder="nombre@empresa.com"
                    autoComplete="username"
                    maxLength={254}
                    required
                  />
                </div>
              </div>

              <div className="access-field">
                <div className="access-label-row">
                  <label htmlFor="login-password">Contraseña</label>
                  <button
                    type="button"
                    className="access-help-link"
                    onClick={() =>
                      setMessage(
                        'Para restablecer tu contraseña, contacta al administrador de la plataforma.',
                      )
                    }
                  >
                    ¿Olvidaste tu contraseña?
                  </button>
                </div>
                <div className="access-input-wrap">
                  <LockKeyhole size={18} aria-hidden="true" />
                  <input
                    id="login-password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => {
                      setPassword(event.target.value)
                      setError('')
                      setMessage('')
                    }}
                    placeholder="Ingresa tu contraseña"
                    autoComplete="current-password"
                    maxLength={256}
                    required
                  />
                  <button
                    type="button"
                    className="access-password-toggle"
                    onClick={() => setShowPassword((current) => !current)}
                    aria-label={
                      showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'
                    }
                    aria-pressed={showPassword}
                  >
                    {showPassword ? (
                      <EyeOff size={18} aria-hidden="true" />
                    ) : (
                      <Eye size={18} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </div>

              <fieldset className="access-field">
                <legend>Perfil de acceso</legend>
                <div style={{ display: 'flex', gap: 8 }}>
                  {(
                    [
                      ['asesor', 'Asesor', 'Gestiona solicitudes'],
                      ['administrador', 'Administrador', 'Ve score y causales'],
                    ] as const
                  ).map(([valor, titulo, detalle]) => (
                    <button
                      key={valor}
                      type="button"
                      aria-pressed={rol === valor}
                      onClick={() => setRol(valor)}
                      style={{
                        flex: 1,
                        padding: '0.6rem',
                        borderRadius: 8,
                        border: `1.5px solid ${rol === valor ? '#099dd7' : '#e2e8f0'}`,
                        background: rol === valor ? '#edfaff' : '#fff',
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      <span
                        style={{
                          display: 'block',
                          fontSize: '.82rem',
                          fontWeight: 600,
                          color: '#1d2939',
                        }}
                      >
                        {titulo}
                      </span>
                      <span style={{ fontSize: '.68rem', color: '#667085' }}>
                        {detalle}
                      </span>
                    </button>
                  ))}
                </div>
              </fieldset>

              {error && (
                <p
                  className="access-feedback access-feedback-error"
                  role="alert"
                >
                  {error}
                </p>
              )}
              {message && (
                <p
                  className="access-feedback access-feedback-info"
                  role="status"
                >
                  {message}
                </p>
              )}

              <button
                type="submit"
                className="access-submit"
                disabled={loading}
                aria-busy={loading}
              >
                <span>
                  {loading ? 'Verificando acceso...' : 'Ingresar a mi cuenta'}
                </span>
                <ArrowRight size={18} aria-hidden="true" />
              </button>
            </form>

            <div className="access-form-footer">
              <span>Desarrollado por GaRi Software</span>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
