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
import { MODO_DEMO } from '../env'
import {
  ErrorAutenticacionApi,
  iniciarSesion,
} from '../features/auth/api/autenticacionApi'
import VitrinaAcceso from '../features/auth/ui/VitrinaAcceso'
import { guardarSesion } from '../shared/lib/sesion'
import './IniciarSesion.css'

export default function IniciarSesion() {
  const navigate = useNavigate()
  const [email, setEmail] = useState(MODO_DEMO ? 'admin@pacifico.co' : '')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
      guardarSesion(
        respuesta.access_token,
        respuesta.usuario,
        respuesta.refresh_token,
      )
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

        <VitrinaAcceso />

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
                    onClick={() => navigate('/recuperar-clave')}
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
