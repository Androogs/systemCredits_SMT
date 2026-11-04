/** "Olvidé mi contraseña" (D124): pide el correo y avisa genérico —
 * el backend decide si envía el enlace sin revelar si la cuenta existe. */

import { ArrowRight, Mail, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { FormEvent } from 'react'
import {
  ErrorAutenticacionApi,
  solicitarRecuperacion,
} from '../features/auth/api/autenticacionApi'
import VitrinaAcceso from '../features/auth/ui/VitrinaAcceso'
import { ALIADO, MARCA, tituloPagina } from '../shared/lib/marca'
import './IniciarSesion.css'

export default function RecuperarClave() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [enviado, setEnviado] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.title = tituloPagina('Recuperar contraseña')
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setLoading(true)
    try {
      await solicitarRecuperacion(email.trim())
      // Siempre el mismo mensaje: no se confirma ni se niega la cuenta.
      setEnviado(true)
    } catch (cause) {
      setError(
        cause instanceof ErrorAutenticacionApi
          ? cause.message
          : 'No pudimos conectar con el servidor. Inténtalo de nuevo.',
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
            src={MARCA.logoClaro}
            alt={MARCA.razonSocial}
            width="900"
            height="129"
          />
          <p className="access-mobile-aliado">
            Consulta de crédito con el respaldo de {ALIADO.nombre}
          </p>
        </div>

        <VitrinaAcceso />

        <section
          className="access-form-panel"
          aria-labelledby="recuperar-heading"
        >
          <div className="access-form-content">
            <div className="access-security">
              <span className="access-security-icon">
                <ShieldCheck size={17} aria-hidden="true" />
              </span>
              <span>Acceso seguro | Tus datos están protegidos</span>
            </div>

            <header className="access-form-header">
              <p className="access-welcome">Recuperación de acceso</p>
              <h2 id="recuperar-heading" className="access-form-title">
                Restablece tu contraseña
              </h2>
              <p className="access-form-subtitle">
                Escribe el correo con el que ingresas a la plataforma y te
                enviaremos un enlace para definir una nueva contraseña.
              </p>
            </header>

            {enviado ? (
              <>
                <p
                  className="access-feedback access-feedback-info"
                  role="status"
                >
                  Si el correo está registrado recibirás un enlace para
                  restablecer tu contraseña. Revisa también la carpeta de spam.
                </p>
                <p
                  className="access-form-subtitle"
                  style={{ marginTop: '1rem' }}
                >
                  <Link to="/login">Volver al inicio de sesión</Link>
                </p>
              </>
            ) : (
              <form className="access-form" onSubmit={submit}>
                <div className="access-field">
                  <label htmlFor="recuperar-email">Correo electrónico</label>
                  <div className="access-input-wrap">
                    <Mail size={18} aria-hidden="true" />
                    <input
                      id="recuperar-email"
                      type="email"
                      value={email}
                      onChange={(event) => {
                        setEmail(event.target.value)
                        setError('')
                      }}
                      placeholder="nombre@sumoto.com.co"
                      autoComplete="username"
                      maxLength={254}
                      required
                    />
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

                <button
                  type="submit"
                  className="access-submit"
                  disabled={loading}
                  aria-busy={loading}
                >
                  <span>
                    {loading ? 'Enviando enlace...' : 'Enviar enlace de acceso'}
                  </span>
                  <ArrowRight size={18} aria-hidden="true" />
                </button>

                <p
                  className="access-form-subtitle"
                  style={{ marginTop: '1rem', textAlign: 'center' }}
                >
                  <Link to="/login">Volver al inicio de sesión</Link>
                </p>
              </form>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
