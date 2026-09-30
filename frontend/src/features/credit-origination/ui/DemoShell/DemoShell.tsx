import { useState } from 'react'
import ValidacionInicial, {
  type DatosValidacion,
} from '../ValidacionInicial.tsx'
import AutorizacionDatos, {
  type DatosAutorizacion,
} from '../AutorizacionDatos.tsx'
import CapturaCedula, { type ResultadoBiometrico } from '../CapturaCedula.tsx'
import ProcesamientoOCR, { type ResultadoOCR } from '../ProcesamientoOCR.tsx'
import RevisionDatos, { type DatosRevisados } from '../RevisionDatos.tsx'
import ResultadoValidacion, {
  type ResultadoFinal,
} from '../ResultadoValidacion.tsx'
import CrearSolicitud, { type DatosSolicitud } from '../CrearSolicitud.tsx'
import PreparacionConsulta, {
  type DatosConsulta,
} from '../PreparacionConsulta.tsx'

import './DemoShell.css'

interface DemoShellProps {
  onExit: () => void
  embedded?: boolean
}

const sections = [
  { id: 'resumen', label: 'Resumen', number: '01' },
  { id: 'inversiones', label: 'Inversiones', number: '02' },
  { id: 'movimientos', label: 'Movimientos', number: '03' },
  { id: 'documentos', label: 'Documentos', number: '04' },
  { id: 'perfil', label: 'Mi perfil', number: '05' },
  { id: 'originacion', label: 'Originación', number: '06' },
] as const

type SectionId = (typeof sections)[number]['id']

type PasoOriginacion = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12

/** Contexto acumulado a lo largo del flujo de originación. */
interface ContextoOriginacion {
  validacion?: DatosValidacion
  autorizacion?: DatosAutorizacion
  biometria?: ResultadoBiometrico
  ocr?: ResultadoOCR
  revision?: DatosRevisados
  resultado?: ResultadoFinal
  solicitud?: DatosSolicitud
  consulta?: DatosConsulta
}

/** Títulos de los pasos 9-12 para el placeholder. */
const PASOS_FUTUROS: Record<number, { titulo: string; detalle: string }> = {
  9: {
    titulo: 'Consulta en Curso',
    detalle: 'Conexión activa con Datacrédito API.',
  },
  10: {
    titulo: 'Informe Crediticio',
    detalle: 'Análisis de score y comportamiento histórico.',
  },
  11: {
    titulo: 'Evaluación Integral',
    detalle: 'Motor de políticas y decisión automatizada.',
  },
  12: {
    titulo: 'Resultado Final',
    detalle: 'Firma y desembolso del crédito.',
  },
}

function DemoShell({ onExit, embedded = false }: DemoShellProps) {
  const [activeSection, setActiveSection] = useState<SectionId>('resumen')
  const [pasoOriginacion, setPasoOriginacion] = useState<PasoOriginacion>(1)
  const [contexto, setContexto] = useState<ContextoOriginacion>({})

  const activeLabel = sections.find(
    (section) => section.id === activeSection,
  )?.label

  const handleNavClick = (sectionId: SectionId) => {
    // Si el usuario sale de originación y vuelve, reinicia el flujo
    if (sectionId === 'originacion' && activeSection !== 'originacion') {
      resetOriginacion()
    }
    setActiveSection(sectionId)
  }

  const resetOriginacion = () => {
    setPasoOriginacion(1)
    setContexto({})
  }

  const renderOriginacion = () => {
    if (pasoOriginacion === 1) {
      return (
        <ValidacionInicial
          onContinue={(datos) => {
            setContexto((prev) => ({ ...prev, validacion: datos }))
            setPasoOriginacion(2)
          }}
        />
      )
    }

    if (pasoOriginacion === 2) {
      return (
        <AutorizacionDatos
          onBack={() => setPasoOriginacion(1)}
          onContinue={(datos) => {
            setContexto((prev) => ({ ...prev, autorizacion: datos }))
            setPasoOriginacion(3)
          }}
        />
      )
    }

    if (pasoOriginacion === 3) {
      return (
        <CapturaCedula
          onBack={() => setPasoOriginacion(2)}
          onContinue={(resultado) => {
            setContexto((prev) => ({ ...prev, biometria: resultado }))
            setPasoOriginacion(4)
          }}
        />
      )
    }

    if (pasoOriginacion === 4) {
      return (
        <ProcesamientoOCR
          onBack={() => setPasoOriginacion(3)}
          onContinue={(resultado) => {
            setContexto((prev) => ({ ...prev, ocr: resultado }))
            setPasoOriginacion(5)
          }}
        />
      )
    }

    if (pasoOriginacion === 5) {
      return (
        <RevisionDatos
          onBack={() => setPasoOriginacion(4)}
          onContinue={(datos) => {
            setContexto((prev) => ({ ...prev, revision: datos }))
            setPasoOriginacion(6)
          }}
        />
      )
    }

    if (pasoOriginacion === 6) {
      return (
        <ResultadoValidacion
          onBack={() => setPasoOriginacion(5)}
          onContinue={(resultado) => {
            setContexto((prev) => ({ ...prev, resultado }))
            setPasoOriginacion(7)
          }}
        />
      )
    }

    if (pasoOriginacion === 7) {
      return (
        <CrearSolicitud
          onBack={() => setPasoOriginacion(6)}
          onContinue={(solicitud) => {
            setContexto((prev) => ({ ...prev, solicitud }))
            setPasoOriginacion(8)
          }}
        />
      )
    }

    if (pasoOriginacion === 8) {
      return (
        <PreparacionConsulta
          onBack={() => setPasoOriginacion(7)}
          onContinue={(consulta) => {
            setContexto((prev) => ({ ...prev, consulta }))
            setPasoOriginacion(9)
          }}
        />
      )
    }

    // ---------- Pasos 9 a 12: placeholders ----------
    const futuro = PASOS_FUTUROS[pasoOriginacion]

    return (
      <div className="demo-shell__placeholder">
        <span className="demo-shell__placeholder-icon" aria-hidden="true">
          {String(pasoOriginacion).padStart(2, '0')}
        </span>
        <p className="demo-shell__eyebrow">
          Originación · Paso {pasoOriginacion} de 12
        </p>
        <h1>{futuro?.titulo ?? 'En construcción'}</h1>
        <p>
          {futuro?.detalle ??
            'Esta pantalla está lista para integrar su contenido.'}
        </p>

        <details className="demo-shell__contexto">
          <summary>
            Ver contexto acumulado ({Object.keys(contexto).length} bloques)
          </summary>
          <pre>{JSON.stringify(contexto, null, 2)}</pre>
        </details>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            className="demo-shell__back-button"
            type="button"
            onClick={() =>
              setPasoOriginacion(
                (prev) => (prev > 1 ? prev - 1 : 1) as PasoOriginacion,
              )
            }
          >
            ← Volver al paso anterior
          </button>
          <button
            className="demo-shell__back-button"
            type="button"
            onClick={resetOriginacion}
          >
            Reiniciar originación
          </button>
        </div>
      </div>
    )
  }

  const renderContent = () => {
    if (activeSection === 'originacion') {
      return renderOriginacion()
    }

    if (activeSection === 'resumen') {
      return (
        <>
          <div className="demo-shell__page-heading">
            <div>
              <p className="demo-shell__eyebrow">Tu espacio financiero</p>
              <h1>Hola, bienvenido</h1>
              <p>Este es el punto de partida para consultar tu información.</p>
            </div>
            <span className="demo-shell__date-chip">Vista previa</span>
          </div>

          <div className="demo-shell__summary-card">
            <div className="demo-shell__summary-orb" aria-hidden="true" />
            <div>
              <span className="demo-shell__card-caption">
                Resumen de cuenta
              </span>
              <h2>Tu información, en un solo lugar</h2>
              <p>
                En esta demostración puedes recorrer las secciones del portal.
              </p>
            </div>
            <span className="demo-shell__summary-mark" aria-hidden="true">
              IP
            </span>
          </div>

          <div className="demo-shell__section-heading">
            <h2>Accesos rápidos</h2>
            <span>Secciones del portal</span>
          </div>
          <div className="demo-shell__cards">
            {sections.slice(1, 4).map((section) => (
              <button
                className="demo-shell__card"
                key={section.id}
                type="button"
                onClick={() => handleNavClick(section.id)}
              >
                <span className="demo-shell__card-icon" aria-hidden="true">
                  {section.number}
                </span>
                <span className="demo-shell__card-label">{section.label}</span>
                <span className="demo-shell__card-link">
                  Explorar <span aria-hidden="true">→</span>
                </span>
              </button>
            ))}
          </div>

          <p className="demo-shell__notice">
            Datos de ejemplo no disponibles · Modo demostración
          </p>
        </>
      )
    }

    return (
      <div className="demo-shell__placeholder">
        <span className="demo-shell__placeholder-icon" aria-hidden="true">
          {sections.find((section) => section.id === activeSection)?.number}
        </span>
        <p className="demo-shell__eyebrow">Sección del portal</p>
        <h1>{activeLabel}</h1>
        <p>
          Esta sección ya está en la navegación y está lista para integrar su
          pantalla.
        </p>
        <button
          className="demo-shell__back-button"
          type="button"
          onClick={() => setActiveSection('resumen')}
        >
          Volver al resumen
        </button>
      </div>
    )
  }

  // OriginaciÃ³n tambiÃ©n puede montarse dentro del layout operativo principal.
  if (embedded) {
    return (
      <section className="originacion-workflow">{renderOriginacion()}</section>
    )
  }

  return (
    <div className="demo-shell">
      <aside className="demo-shell__sidebar">
        <img src="/brand/pacifico-blancos.png" alt="Inversiones Pacífico" />
        <div className="demo-shell__nav-label">Tu espacio</div>
        <nav className="demo-shell__nav" aria-label="Navegación principal">
          {sections.map((section) => (
            <button
              className={`demo-shell__nav-item${activeSection === section.id ? ' is-active' : ''}`}
              key={section.id}
              type="button"
              aria-current={activeSection === section.id ? 'page' : undefined}
              onClick={() => handleNavClick(section.id)}
            >
              <span className="demo-shell__nav-number" aria-hidden="true">
                {section.number}
              </span>
              {section.label}
              {activeSection === section.id && (
                <span className="demo-shell__nav-arrow" aria-hidden="true">
                  ›
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="demo-shell__sidebar-footer">
          <span className="demo-shell__avatar">DP</span>
          <span className="demo-shell__profile-copy">
            <strong>Demo Pacífico</strong>
            <small>Vista de prueba</small>
          </span>
          <button
            className="demo-shell__exit"
            type="button"
            onClick={onExit}
            aria-label="Salir de la demostración"
            title="Salir de la demostración"
          >
            ↗
          </button>
        </div>
      </aside>

      <main className="demo-shell__main">
        <header className="demo-shell__topbar">
          <div className="demo-shell__breadcrumb">
            <span>Portal de clientes</span>
            <span aria-hidden="true">/</span>
            <strong>
              {activeSection === 'originacion'
                ? `Originación · Paso ${pasoOriginacion}`
                : activeLabel}
            </strong>
          </div>
          <div className="demo-shell__topbar-actions">
            <span className="demo-shell__environment">
              <span />
              Entorno de prueba
            </span>
            <button
              className="demo-shell__topbar-exit"
              type="button"
              onClick={onExit}
            >
              Salir
            </button>
          </div>
        </header>

        <section className="demo-shell__content" aria-live="polite">
          {renderContent()}
        </section>
      </main>
    </div>
  )
}

export default DemoShell
