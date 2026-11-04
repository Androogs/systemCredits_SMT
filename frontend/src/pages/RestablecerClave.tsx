/** Destino del enlace del correo de recuperación (D124): define la
 * nueva clave con el token de un solo uso de la URL. */

import { ArrowRight, Eye, EyeOff, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { FormEvent } from 'react'
import {
  ErrorAutenticacionApi,
  restablecerClave,
} from '../features/auth/api/autenticacionApi'
import VitrinaAcceso from '../features/auth/ui/VitrinaAcceso'
import { ALIADO, MARCA, tituloPagina } from '../shared/lib/marca'
import './IniciarSesion.css'

export default function RestablecerClave() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [nueva, setNueva] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [hecho, setHecho] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    document.title = tituloPagina('Nueva contraseña')
  }, [])

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (nueva !== confirmar) {
      setError('Las contraseñas no coinciden.')
      return
    }
    setLoading(true)
    try {
      await restablecerClave(token, nueva)
      setHecho(true)
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
          aria-labelledby="restablecer-heading"
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
              <h2 id="restablecer-heading" className="access-form-title">
                Define tu nueva contraseña
              </h2>
              <p className="access-form-subtitle">
                El enlace vence a los 30 minutos y solo se puede usar una vez.
              </p>
            </header>

            {!token ? (
              <>
                <p
                  className="access-feedback access-feedback-error"
                  role="alert"
                >
                  El enlace no es válido. Solicita uno nuevo desde la pantalla
                  de recuperación.
                </p>
                <p
                  className="access-form-subtitle"
                  style={{ marginTop: '1rem' }}
                >
                  <Link to="/recuperar-clave">Solicitar nuevo enlace</Link>
                </p>
              </>
            ) : hecho ? (
              <>
                <p
                  className="access-feedback access-feedback-info"
                  role="status"
                >
                  Contraseña restablecida. Ya puedes iniciar sesión con tu nueva
                  clave.
                </p>
                <p
                  className="access-form-subtitle"
                  style={{ marginTop: '1rem' }}
                >
                  <Link to="/login">Ir al inicio de sesión</Link>
                </p>
              </>
            ) : (
              <form className="access-form" onSubmit={submit}>
                <div className="access-field">
                  <label htmlFor="nueva-clave">Nueva contraseña</label>
                  <div className="access-input-wrap">
                    <LockKeyhole size={18} aria-hidden="true" />
                    <input
                      id="nueva-clave"
                      type={showPassword ? 'text' : 'password'}
                      value={nueva}
                      onChange={(event) => {
                        setNueva(event.target.value)
                        setError('')
                      }}
                      placeholder="Mínimo 8 caracteres"
                      autoComplete="new-password"
                      minLength={8}
                      maxLength={128}
                      required
                    />
                    <button
                      type="button"
                      className="access-password-toggle"
                      onClick={() => setShowPassword((v) => !v)}
                      aria-label={
                        showPassword
                          ? 'Ocultar contraseña'
                          : 'Mostrar contraseña'
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

                <div className="access-field">
                  <label htmlFor="confirmar-clave">Confirmar contraseña</label>
                  <div className="access-input-wrap">
                    <LockKeyhole size={18} aria-hidden="true" />
                    <input
                      id="confirmar-clave"
                      type={showPassword ? 'text' : 'password'}
                      value={confirmar}
                      onChange={(event) => {
                        setConfirmar(event.target.value)
                        setError('')
                      }}
                      placeholder="Repite la nueva contraseña"
                      autoComplete="new-password"
                      minLength={8}
                      maxLength={128}
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
                    {loading ? 'Guardando...' : 'Guardar nueva contraseña'}
                  </span>
                  <ArrowRight size={18} aria-hidden="true" />
                </button>
              </form>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
