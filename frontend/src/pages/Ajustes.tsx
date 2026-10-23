import { useId, useState, useRef, useCallback, useEffect } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import { env } from '../env'
import {
  actualizarParametros,
  obtenerParametros,
  restablecerParametros,
} from '../features/settings/api/parametrosApi'
import type {
  ParametrosMotor,
  ValorParametro,
} from '../features/settings/api/parametrosApi'
import { EditorParametros } from '../features/settings/ui/EditorParametros'
import GestionUsuarios from '../features/settings/ui/GestionUsuarios'
import FormularioCambioClave from '../features/auth/ui/FormularioCambioClave'
import {
  User,
  Cpu,
  Users,
  Building2,
  FileText,
  LineChart,
  KeyRound,
  HardDrive,
  X,
  Trash2,
  LogOut,
  Monitor,
  Palette,
  Upload,
  Download,
  FileCheck,
  Clock,
  AlertTriangle,
  Key,
  Globe,
  Database,
  RefreshCw,
  CheckCircle2,
  Copy,
} from 'lucide-react'
import CampoNumerico from '../shared/ui/CampoNumerico'
import CampoEntrada from '../shared/ui/CampoEntrada'
import { fetchAutenticado } from '../shared/lib/fetchAutenticado'
import { useRol, useUsuario } from '../shared/lib/sesion'

type SeccionId =
  | 'perfil'
  | 'usuarios'
  | 'motor'
  | 'concesionarios'
  | 'documentos'
  | 'auditoria'
  | 'seguridad'
  | 'backup'
const SECCIONES: {
  id: SeccionId
  label: string
  mobileLabel: string
  icon: LucideIcon
  desc: string
}[] = [
  {
    id: 'perfil',
    label: 'Panel de Cuenta',
    mobileLabel: 'Cuenta',
    icon: User,
    desc: 'Datos de sesión y seguridad',
  },
  {
    id: 'usuarios',
    label: 'Usuarios y Permisos',
    mobileLabel: 'Usuarios',
    icon: Users,
    desc: 'Roles y Accesos',
  },
  {
    id: 'motor',
    label: 'Motor de Decisión',
    mobileLabel: 'Motor',
    icon: Cpu,
    desc: 'Score, Quanto y límites, reglas de buró y endeudamiento',
  },
  {
    id: 'concesionarios',
    label: 'Concesionarios',
    mobileLabel: 'Aliados',
    icon: Building2,
    desc: 'Aliados y cupos',
  },
  {
    id: 'documentos',
    label: 'Documentos y Plantillas',
    mobileLabel: 'Documentos',
    icon: FileText,
    desc: 'Requisitos y formatos',
  },
  {
    id: 'auditoria',
    label: 'Auditoría y Logs',
    mobileLabel: 'Auditoría',
    icon: LineChart,
    desc: 'Trazabilidad',
  },
  {
    id: 'seguridad',
    label: 'API y Seguridad',
    mobileLabel: 'Seguridad',
    icon: KeyRound,
    desc: 'Keys, CORS',
  },
  {
    id: 'backup',
    label: 'Backup y Mantenimiento',
    mobileLabel: 'Sistema',
    icon: HardDrive,
    desc: 'Respaldos y salud',
  },
]

const Card = ({
  children,
  title,
  desc,
  action,
}: {
  children: ReactNode
  title: string
  desc?: string
  action?: ReactNode
}) => (
  <div className="card p-4 sm:p-5">
    <div className="mb-4 flex flex-col gap-3 sm:mb-5 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h3 className="font-semibold text-[14px] tracking-tight">{title}</h3>
        {desc && <p className="text-xs text-slate-500 mt-1">{desc}</p>}
      </div>
      {action}
    </div>
    {children}
  </div>
)

const Input = CampoEntrada

const InputNumerico = ({
  label,
  id,
  value,
  onValor,
  decimales,
  formatoMiles,
  minimo,
  maximo,
}: {
  label: string
  id?: string
  value: number | null
  onValor: (n: number | null) => void
  decimales?: boolean
  formatoMiles?: boolean
  minimo?: number
  maximo?: number
}) => {
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <div>
      <label htmlFor={inputId} className="label-base">
        {label}
      </label>
      <CampoNumerico
        id={inputId}
        className="input-base"
        value={value}
        onValor={onValor}
        decimales={decimales}
        formatoMiles={formatoMiles}
        minimo={minimo}
        maximo={maximo}
        mostrarCero
      />
    </div>
  )
}

export default function Ajustes() {
  const rol = useRol()
  const usuario = useUsuario()
  const vistaBinaria = rol !== 'admin'
  // El concesionario administra los asesores de su sede: además de
  // Cuenta ve Usuarios (la API ya le devuelve solo su sede).
  const gestionaAsesores = rol === 'concesionario'
  const seccionVisible = (id: SeccionId): boolean =>
    !vistaBinaria || id === 'perfil' || (gestionaAsesores && id === 'usuarios')
  const [seccion, setSeccion] = useState<SeccionId>('perfil')
  const [hasChanges, setHasChanges] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [avatar, setAvatar] = useState<string | null>(null)
  const [concesionarios, setConcesionarios] = useState<string[]>([
    'Sumoto Palmira',
    'Tulua Motos',
    'Pijaos Motos',
  ])
  const [nuevoConcesionario, setNuevoConcesionario] = useState('')
  const [parametros, setParametros] = useState<ParametrosMotor | null>(null)
  const [parametrosGuardados, setParametrosGuardados] =
    useState<ParametrosMotor | null>(null)
  const [bloqueadosPorEntorno, setBloqueadosPorEntorno] = useState<string[]>([])
  const [cargandoParametros, setCargandoParametros] = useState(true)
  const [guardandoParametros, setGuardandoParametros] = useState(false)
  const [errorParametros, setErrorParametros] = useState<string | null>(null)
  const [mensajeParametros, setMensajeParametros] = useState<string | null>(
    null,
  )

  const [documentosVisuales] = useState([
    { id: 1, nombre: 'Cédula anverso', formato: 'PDF/JPG', tamano: '5MB' },
    { id: 2, nombre: 'Cédula reverso', formato: 'PDF/JPG', tamano: '5MB' },
    {
      id: 3,
      nombre: 'Documento de valor ingreso',
      formato: 'PDF',
      tamano: '10MB',
    },
    {
      id: 4,
      nombre: 'Documento de historial crediticio',
      formato: 'PDF',
      tamano: '10MB',
    },
  ])

  const [plantillas] = useState([
    {
      id: 5,
      nombre: 'AUTORIZACION CONSULTA CENTRALES INVERSIONES PACIFICO.docx',
      formato: 'DOCX',
      tamano: '59 kB',
    },
    {
      id: 6,
      nombre: 'autorizacionDeCanalesDeContacto735.pdf',
      formato: 'PDF',
      tamano: '102 kB',
    },
    {
      id: 7,
      nombre: 'CARTA DE APROBACION INVERSIONES PACIFICO.docx',
      formato: 'DOCX',
      tamano: '52 kB',
    },
    {
      id: 8,
      nombre: 'cartaAprobacion735.pdf',
      formato: 'PDF',
      tamano: '94 kB',
    },
    {
      id: 9,
      nombre: 'PAGARE INVERSIONES PACIFICO.docx',
      formato: 'DOCX',
      tamano: '56 kB',
    },
    { id: 10, nombre: 'pagare735.pdf', formato: 'PDF', tamano: '103 kB' },
    {
      id: 11,
      nombre: 'DECLARACION ASEGURABILIDAD INVERSIONES PACIFICO.docx',
      formato: 'DOCX',
      tamano: '34 kB',
    },
    {
      id: 12,
      nombre: 'declaracionAsegurabilidad735.pdf',
      formato: 'PDF',
      tamano: '94 kB',
    },
    {
      id: 13,
      nombre: 'solicitudCredito735.pdf',
      formato: 'PDF',
      tamano: '96 kB',
    },
    {
      id: 14,
      nombre: 'Tabla de amortización',
      formato: 'PDF',
      tamano: '—',
      nota: 'Plantilla pendiente',
    },
  ])

  // AUDITORIA
  const [logs, setLogs] = useState<
    { id: string; fecha: string; usuario: string; accion: string; ip: string }[]
  >([])
  const [cargandoAuditoria, setCargandoAuditoria] = useState(false)
  const [errorAuditoria, setErrorAuditoria] = useState<string | null>(null)
  const [filtroAuditoria, setFiltroAuditoria] = useState('')
  const [filtroDecision, setFiltroDecision] = useState('')

  const cargarAuditoria = useCallback(async () => {
    setCargandoAuditoria(true)
    setErrorAuditoria(null)
    try {
      const params = new URLSearchParams()
      params.set('limite', '100')
      if (filtroAuditoria) params.set('numero_id', filtroAuditoria)
      if (filtroDecision) params.set('decision', filtroDecision)
      const respuesta = await fetchAutenticado(
        `${env.VITE_API_URL.replace(/\/$/, '')}/api/auditoria?${params}`,
        { headers: { 'Content-Type': 'application/json' } },
      )
      if (!respuesta.ok) throw new Error(`Error HTTP ${respuesta.status}`)
      const data = await respuesta.json()
      setLogs(
        data.map(
          (e: {
            evaluacion_id: string
            fecha_evaluacion: string
            numero_id: string | null
            ocupacion: string
            decision: string
            origen_datos: string | null
          }) => ({
            id: e.evaluacion_id,
            fecha: new Date(e.fecha_evaluacion).toLocaleString('es-CO', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            }),
            usuario: e.numero_id || '-',
            accion: `${e.decision} • ${e.ocupacion}`,
            ip: e.origen_datos || '-',
          }),
        ),
      )
    } catch (error) {
      setErrorAuditoria(
        error instanceof Error ? error.message : 'Error al cargar auditoría.',
      )
    } finally {
      setCargandoAuditoria(false)
    }
  }, [filtroAuditoria, filtroDecision])

  useEffect(() => {
    if (vistaBinaria) return
    void cargarAuditoria()
  }, [cargarAuditoria, vistaBinaria])

  // SEGURIDAD
  const [apiKeys, setApiKeys] = useState([
    {
      id: 1,
      nombre: 'Frontend Prod',
      key: 'sk_live_51H...',
      creado: '01/10/2026',
      ultimoUso: 'Hoy',
    },
  ])
  const [cors, setCors] = useState(
    'https://sumoto.com.co, https://app.sumoto.com.co',
  )

  // FORM GLOBAL
  const [form, setForm] = useState({
    nombre: 'Alejandro Garcia',
    email: 'desarrollo@sumoto.com.co',
    telefono: '3211234567',
    cargo: 'Super Admin',
    tema: 'Claro',
    idioma: 'Español',
    moneda: 'COP',
    fechaFmt: 'DD/MM/YYYY',
    smmlv: 1750905,
    scoreMin: 600,
    quantoMin: 1.0,
    capacidadMax: 40,
    endeudamientoMax: 50,
    ingresoMinimo: 1300000,
    limitesRol: {
      Asesor: 0,
      Analista: 20000000,
      Administrador: 50000000,
      'Super Admin': 999999999,
    },
    reglasEmpleo: [
      { tipo: 'Empleado', scoreMin: 600, ingresoMin: 1.5, activo: true },
      { tipo: 'Independiente', scoreMin: 650, ingresoMin: 2.0, activo: true },
      { tipo: 'Pensionado', scoreMin: 580, ingresoMin: 1.2, activo: true },
    ],
    edadMin: 18,
    edadMax: 74,
    moraMax: 30,
    listaNegra: true,
    retencionLogs: 180,
    timeoutSesion: 30,
    intentosFallidos: 5,
    bloqueoMin: 15,
    longitudPass: 8,
    backupAuto: true,
    backupHora: '02:00',
    backupRetencion: 30,
  })

  const cargarParametros = useCallback(async () => {
    setCargandoParametros(true)
    setErrorParametros(null)
    try {
      const respuesta = await obtenerParametros()
      setParametros(respuesta.parametros)
      setParametrosGuardados(respuesta.parametros)
      setBloqueadosPorEntorno(respuesta.bloqueados_por_entorno)
      setMensajeParametros(null)
    } catch (error) {
      setErrorParametros(
        error instanceof Error
          ? error.message
          : 'Error desconocido al conectar con el backend.',
      )
    } finally {
      setCargandoParametros(false)
    }
  }, [])

  useEffect(() => {
    if (vistaBinaria) return
    void cargarParametros()
  }, [cargarParametros, vistaBinaria])

  useEffect(() => {
    if (!seccionVisible(seccion)) {
      setSeccion('perfil')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vistaBinaria, seccion])

  const parametrosModificados =
    parametros !== null &&
    parametrosGuardados !== null &&
    JSON.stringify(parametros) !== JSON.stringify(parametrosGuardados)

  const recargarParametros = () => {
    if (
      parametrosModificados &&
      !window.confirm(
        'Hay cambios sin guardar. ¿Descartarlos y recargar desde el backend?',
      )
    ) {
      return
    }
    void cargarParametros()
  }

  const handleParametroChange = (key: string, valor: ValorParametro) => {
    setParametros((actuales) =>
      actuales ? { ...actuales, [key]: valor } : actuales,
    )
    setErrorParametros(null)
    setMensajeParametros(null)
  }

  const guardarCambios = async () => {
    if (!parametros || !parametrosGuardados || !parametrosModificados) {
      if (hasChanges) {
        setErrorParametros(
          'Las otras secciones aún no tienen endpoints de persistencia en el backend. No se guardaron esos cambios.',
        )
      }
      return
    }

    const bloqueados = new Set(bloqueadosPorEntorno)
    const cambios = Object.entries(parametros).reduce<ParametrosMotor>(
      (resultado, [key, valor]) => {
        if (
          !bloqueados.has(key) &&
          JSON.stringify(valor) !== JSON.stringify(parametrosGuardados[key])
        ) {
          resultado[key] = valor
        }
        return resultado
      },
      {},
    )

    if (Object.keys(cambios).length === 0) {
      setParametros(parametrosGuardados)
      setErrorParametros(
        'No hay cambios editables: los valores modificados están fijados por el entorno.',
      )
      return
    }

    setGuardandoParametros(true)
    setErrorParametros(null)
    setMensajeParametros(null)
    try {
      const respuesta = await actualizarParametros(cambios)
      setParametros(respuesta.parametros)
      setParametrosGuardados(respuesta.parametros)
      setBloqueadosPorEntorno(respuesta.bloqueados_por_entorno)
      setMensajeParametros('Parámetros del motor guardados correctamente.')
    } catch (error) {
      setErrorParametros(
        error instanceof Error
          ? error.message
          : 'No fue posible guardar los parámetros.',
      )
    } finally {
      setGuardandoParametros(false)
    }
  }

  const restablecerValores = async () => {
    if (
      !window.confirm(
        '¿Restablecer los parámetros del motor a sus valores por defecto?',
      )
    ) {
      return
    }

    setGuardandoParametros(true)
    setErrorParametros(null)
    setMensajeParametros(null)
    try {
      const respuesta = await restablecerParametros()
      setParametros(respuesta.parametros)
      setParametrosGuardados(respuesta.parametros)
      setBloqueadosPorEntorno(respuesta.bloqueados_por_entorno)
      setMensajeParametros(
        'Parámetros del motor restablecidos a sus valores por defecto.',
      )
    } catch (error) {
      setErrorParametros(
        error instanceof Error
          ? error.message
          : 'No fue posible restablecer los parámetros.',
      )
    } finally {
      setGuardandoParametros(false)
    }
  }

  const onChange = useCallback((k: string, v: unknown) => {
    setForm((s) => ({ ...s, [k]: v }))
    setHasChanges(true)
  }, [])
  const handleAvatarChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) {
      if (avatar) URL.revokeObjectURL(avatar)
      setAvatar(URL.createObjectURL(f))
      setHasChanges(true)
    }
  }
  const handleAvatarRemove = () => {
    if (avatar) URL.revokeObjectURL(avatar)
    setAvatar(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    setHasChanges(true)
  }
  const addConcesionario = () => {
    const v = nuevoConcesionario.trim()
    if (!v || concesionarios.includes(v)) return
    setConcesionarios((p) => [...p, v])
    setNuevoConcesionario('')
    setHasChanges(true)
  }
  const removeConcesionario = (name: string) => {
    setConcesionarios((p) => p.filter((c) => c !== name))
    setHasChanges(true)
  }
  return (
    <div className="min-h-screen overflow-x-clip bg-slate-50 text-slate-900">
      <div className="sticky top-0 z-20 border-b bg-white">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-2 pl-16 pr-3 sm:px-6">
          <h1 className="flex min-w-0 items-center gap-2 text-base font-semibold">
            Ajustes
            {(hasChanges || parametrosModificados) && (
              <span className="truncate rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-600 sm:text-[11px]">
                <span className="sm:hidden">Sin guardar</span>
                <span className="hidden sm:inline">Cambios sin guardar</span>
              </span>
            )}
          </h1>
          {!vistaBinaria && (
            <button
              onClick={() => void guardarCambios()}
              disabled={
                guardandoParametros || (!hasChanges && !parametrosModificados)
              }
              aria-label="Guardar cambios"
              className="h-10 shrink-0 rounded-lg bg-[#000033] px-3 text-xs font-medium text-white shadow-sm transition hover:bg-[#000033] disabled:opacity-40 sm:px-4"
            >
              {guardandoParametros ? (
                'Guardando…'
              ) : (
                <>
                  <span className="sm:hidden">Guardar</span>
                  <span className="hidden sm:inline">Guardar cambios</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-4 px-3 py-4 sm:px-6 sm:py-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-6">
        <nav
          aria-label="Secciones de ajustes"
          className="sticky top-14 z-10 -mx-3 flex min-w-0 snap-x snap-mandatory gap-2 overflow-x-auto border-b border-slate-200 bg-slate-50/95 px-3 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:top-[68px] lg:mx-0 lg:block lg:h-fit lg:space-y-1 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
        >
          {SECCIONES.filter((s) => seccionVisible(s.id)).map((s) => {
            const Icon = s.icon
            const active = seccion === s.id
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => setSeccion(s.id)}
                aria-pressed={active}
                className={`flex min-h-11 shrink-0 snap-start items-center gap-2 rounded-full border px-3 text-xs font-medium transition-colors lg:mb-1 lg:w-full lg:justify-start lg:gap-3 lg:rounded-md lg:px-3 lg:py-2.5 lg:text-left lg:text-sm ${
                  active
                    ? 'border-[#000033] bg-[#000033] text-white shadow-sm'
                    : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50 lg:border-transparent lg:bg-transparent lg:shadow-none'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0 lg:h-[18px] lg:w-[18px]" />
                <span className="lg:hidden">{s.mobileLabel}</span>
                <div className="hidden min-w-0 lg:block">
                  <p className="text-[13px] font-medium leading-none">
                    {s.label}
                  </p>
                  <p className="text-[11px] opacity-70 mt-1 truncate">
                    {s.desc}
                  </p>
                </div>
              </button>
            )
          })}
          <div className="mt-4 hidden border-t pt-4 lg:block">
            <div className="rounded-md bg-white border p-3 text-xs">
              <p className="font-medium text-[11px] uppercase text-slate-600">
                Última conexión
              </p>
              <p className="text-slate-500 mt-1">
                02/10/2026 11:42
                <br />
                IP: 190.121.45.XX
                <br />
                Palmira, CO
              </p>
            </div>
          </div>
        </nav>

        <div className="min-w-0 space-y-4 pb-28 sm:pb-24">
          {!vistaBinaria && (
            <div className="rounded-md border border-brand-100 bg-brand-50 p-3 text-xs text-brand-900">
              La configuración conectada al backend corresponde al motor de
              decisión y sus reglas de riesgo. Las demás secciones aún no
              cuentan con endpoints de persistencia y sus cambios no se guardan
              en el servidor.
            </div>
          )}
          {!vistaBinaria && (errorParametros || mensajeParametros) && (
            <div
              role={errorParametros ? 'alert' : 'status'}
              className={`rounded-md border p-3 text-sm ${
                errorParametros
                  ? 'border-red-200 bg-red-50 text-red-800'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-800'
              }`}
            >
              {errorParametros ?? mensajeParametros}
            </div>
          )}
          {seccion === 'perfil' && (
            <>
              <Card
                title="Perfil y Cuenta"
                desc="Información visible para SOCIP"
              >
                <div className="flex flex-col sm:flex-row gap-8">
                  <div className="flex flex-col items-center shrink-0">
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        aria-label="Seleccionar foto de perfil"
                        className="h-24 w-24 rounded-full bg-slate-50 border-2 border-dashed border-slate-300 overflow-hidden flex items-center justify-center cursor-pointer hover:border-brand-900 group focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900"
                      >
                        {avatar ? (
                          <img
                            src={avatar}
                            alt="Foto de perfil"
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex flex-col items-center">
                            <User className="h-7 w-7 text-slate-400 group-hover:text-slate-900" />
                            <span className="text-[10px] uppercase text-slate-500 mt-1">
                              Foto
                            </span>
                          </div>
                        )}
                      </button>
                      {avatar && (
                        <button
                          type="button"
                          onClick={handleAvatarRemove}
                          aria-label="Eliminar foto de perfil"
                          className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-red-500 text-white grid place-items-center"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept="image/*"
                      className="hidden"
                      onChange={handleAvatarChange}
                    />
                    {avatar && (
                      <button
                        onClick={handleAvatarRemove}
                        className="mt-2 text-[10px] text-red-700 flex items-center gap-1"
                      >
                        <Trash2 className="h-3 w-3" /> Eliminar
                      </button>
                    )}
                  </div>
                  {/* Identidad de la sesión autenticada: solo lectura —
                      el nombre/rol se asignan desde Usuarios y Permisos. */}
                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1 min-w-0">
                    <div>
                      <dt className="text-[11px] uppercase text-slate-600">
                        Nombre completo
                      </dt>
                      <dd className="mt-1 text-sm font-medium">
                        {usuario?.nombre ?? '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[11px] uppercase text-slate-600">
                        Correo
                      </dt>
                      <dd className="mt-1 text-sm font-medium break-all">
                        {usuario?.correo ?? '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[11px] uppercase text-slate-600">
                        Rol
                      </dt>
                      <dd className="mt-1 text-sm font-medium">
                        {rol === 'admin'
                          ? 'Administrador'
                          : rol === 'asesor'
                            ? 'Asesor'
                            : 'Aliado'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[11px] uppercase text-slate-600">
                        Concesionario
                      </dt>
                      <dd className="mt-1 text-sm font-medium">
                        {usuario?.concesionario?.nombre ?? '—'}
                      </dd>
                    </div>
                  </dl>
                </div>
              </Card>
              <Card
                title="Seguridad"
                desc="Contraseña de tu cuenta (el cambio aplica de inmediato)"
              >
                <FormularioCambioClave />
              </Card>
              <div className="grid md:grid-cols-2 gap-4">
                <Card
                  title="Preferencias"
                  action={<Palette className="h-4 w-4 text-slate-400" />}
                >
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label
                        className="text-[11px] uppercase text-slate-600"
                        htmlFor="settings-theme"
                      >
                        Tema
                      </label>
                      <select
                        id="settings-theme"
                        value={form.tema}
                        onChange={(e) => onChange('tema', e.target.value)}
                        className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                      >
                        <option>Claro</option>
                        <option>Oscuro</option>
                        <option>Sistema</option>
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label
                        className="text-[11px] uppercase text-slate-600"
                        htmlFor="settings-language"
                      >
                        Idioma
                      </label>
                      <select
                        id="settings-language"
                        value={form.idioma}
                        onChange={(e) => onChange('idioma', e.target.value)}
                        className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                      >
                        <option>Español</option>
                        <option>English</option>
                      </select>
                    </div>
                  </div>
                </Card>
                <Card
                  title="Sesión activa"
                  action={<Monitor className="h-4 w-4 text-slate-400" />}
                >
                  <div className="rounded-md bg-slate-50 border p-3 text-xs">
                    <p className="font-medium">Sesión actual</p>
                    <p className="text-slate-600 mt-1">
                      02/10/2026 11:42 • 190.121.45.XX
                      <br />
                      Palmira, CO • Chrome / Windows
                    </p>
                    <span className="mt-2 inline-flex text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700">
                      Activa
                    </span>
                  </div>
                  <button className="mt-3 flex h-11 w-full items-center justify-center gap-1.5 rounded-lg border text-xs">
                    <LogOut className="h-3.5 w-3.5" /> Cerrar otras sesiones
                  </button>
                </Card>
              </div>
            </>
          )}

          {(!vistaBinaria || gestionaAsesores) && seccion === 'usuarios' && (
            <Card
              title="Usuarios y Permisos"
              desc={
                gestionaAsesores
                  ? 'Asesores de tu sede: altas, estado y clave temporal'
                  : 'Cuentas con acceso al panel: roles, vínculos y estado'
              }
            >
              <GestionUsuarios />
            </Card>
          )}

          {!vistaBinaria && seccion === 'motor' && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-slate-500">
                  Parámetros activos del motor cargados desde el servidor.
                </p>
                <button
                  type="button"
                  onClick={recargarParametros}
                  disabled={cargandoParametros || guardandoParametros}
                  className="h-8 rounded-md border bg-white px-3 text-xs disabled:opacity-50"
                >
                  Recargar desde backend
                </button>
              </div>
              <EditorParametros
                seccion="motor"
                parametros={parametros}
                bloqueados={bloqueadosPorEntorno}
                cargando={cargandoParametros}
                deshabilitado={cargandoParametros || guardandoParametros}
                error={errorParametros}
                onRetry={recargarParametros}
                onChange={handleParametroChange}
              />
              {parametros && (
                <div className="flex flex-wrap justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => void restablecerValores()}
                    disabled={guardandoParametros || cargandoParametros}
                    className="h-9 rounded-md border bg-white px-4 text-xs disabled:opacity-50"
                  >
                    Restablecer valores por defecto
                  </button>
                </div>
              )}
            </>
          )}

          {!vistaBinaria && seccion === 'concesionarios' && (
            <Card title="Concesionarios" desc="Aliados y cupos de crédito">
              <div className="flex flex-col sm:flex-row gap-2 mb-4">
                <label className="sr-only" htmlFor="dealer-name">
                  Nombre del concesionario
                </label>
                <input
                  id="dealer-name"
                  value={nuevoConcesionario}
                  onChange={(e) => setNuevoConcesionario(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addConcesionario()}
                  placeholder="Ej: Suzuki Palmira"
                  className="h-11 w-full flex-1 rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                />
                <button
                  type="button"
                  onClick={addConcesionario}
                  className="h-11 w-full rounded-lg bg-[#000033] px-4 text-sm font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                >
                  Agregar
                </button>
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                {concesionarios.map((c) => (
                  <div
                    key={c}
                    className="flex items-center justify-between p-4 rounded-lg border bg-white hover:border-slate-300 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium">{c}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Cupo: $120M • Usado: $45M • Asesores: 3
                      </p>
                      <div className="mt-2 h-1.5 w-32 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full w-[37%] bg-[#000033]" />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeConcesionario(c)}
                      aria-label={`Quitar concesionario ${c}`}
                      className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border text-slate-500 hover:bg-red-50 hover:text-red-600 sm:h-9 sm:w-9 sm:rounded-md"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {!vistaBinaria && seccion === 'documentos' && (
            <>
              <Card
                title="Documentos"
                desc="Documentos requeridos (solo visual)"
              >
                <div className="hidden overflow-auto rounded-md border sm:block">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                      <tr>
                        <th scope="col" className="text-left p-3">
                          Documento
                        </th>
                        <th scope="col" className="text-left p-3">
                          Formato
                        </th>
                        <th scope="col" className="text-left p-3">
                          Tamaño
                        </th>
                        <th scope="col" className="text-left p-3">
                          Ver
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {documentosVisuales.map((d) => (
                        <tr key={d.id} className="border-t hover:bg-slate-50">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <FileCheck className="h-4 w-4 text-slate-400" />
                              <span className="font-medium">{d.nombre}</span>
                            </div>
                          </td>
                          <td className="p-3 text-xs">{d.formato}</td>
                          <td className="p-3 text-xs">{d.tamano}</td>
                          <td className="p-3">
                            <button
                              type="button"
                              aria-label={`Ver ${d.nombre}`}
                              className="h-7 w-7 grid place-items-center rounded border"
                            >
                              <Download className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-3 sm:hidden">
                  {documentosVisuales.map((d) => (
                    <article
                      key={d.id}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                    >
                      <div className="flex min-w-0 items-start gap-3">
                        <div className="flex min-w-0 items-start gap-2">
                          <FileCheck className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold">{d.nombre}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {d.formato} · {d.tamano}
                            </p>
                          </div>
                        </div>
                        <div className="shrink-0 flex gap-2">
                          <button
                            type="button"
                            aria-label={`Ver ${d.nombre}`}
                            className="flex h-11 items-center justify-center gap-2 rounded-lg border text-xs font-medium"
                          >
                            <Download className="h-4 w-4" /> Ver
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
              <Card
                title="Plantillas"
                desc="Plantillas descargables y reemplazables"
                action={
                  <button
                    type="button"
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#000033] px-3 text-xs font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                  >
                    <Upload className="h-4 w-4 sm:h-3 sm:w-3" /> Subir plantilla
                  </button>
                }
              >
                <div className="hidden overflow-auto rounded-md border sm:block">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                      <tr>
                        <th scope="col" className="text-left p-3">
                          Plantilla
                        </th>
                        <th scope="col" className="text-left p-3">
                          Formato
                        </th>
                        <th scope="col" className="text-left p-3">
                          Tamaño
                        </th>
                        <th scope="col" className="text-left p-3">
                          Estado
                        </th>
                        <th scope="col" className="text-right p-3">
                          Acción
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {plantillas.map((d) => (
                        <tr key={d.id} className="border-t hover:bg-slate-50">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-slate-400" />
                              <span className="font-medium">{d.nombre}</span>
                              {d.nota && (
                                <span className="ml-2 text-[10px] text-amber-500">
                                  ({d.nota})
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-3 text-xs">{d.formato}</td>
                          <td className="p-3 text-xs">{d.tamano}</td>
                          <td className="p-3">
                            <span
                              className={`text-[11px] px-2 py-0.5 rounded-full border ${
                                d.nota
                                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                                  : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                              }`}
                            >
                              {d.nota || 'Disponible'}
                            </span>
                          </td>
                          <td className="p-3">
                            <div className="flex gap-1">
                              <button
                                type="button"
                                aria-label={`Descargar ${d.nombre}`}
                                disabled={!!d.nota}
                                className={`h-7 w-7 grid place-items-center rounded border ${
                                  d.nota
                                    ? 'text-slate-400 border-slate-200'
                                    : 'text-slate-600 border-slate-300'
                                }`}
                              >
                                <Download className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                aria-label={`Reemplazar ${d.nombre}`}
                                className="h-7 w-7 grid place-items-center rounded border bg-[#000033] text-white"
                              >
                                <RefreshCw className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-3 sm:hidden">
                  {plantillas.map((d) => (
                    <article
                      key={d.id}
                      className="rounded-xl border border-slate-200 bg-white p-4"
                    >
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2">
                          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold">{d.nombre}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {d.formato} · {d.tamano}
                            </p>
                          </div>
                          <span
                            className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium ${
                              d.nota
                                ? 'border-amber-200 bg-amber-50 text-amber-700'
                                : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            }`}
                          >
                            {d.nota || 'Disponible'}
                          </span>
                        </div>
                        <div className="shrink-0 flex gap-2">
                          <button
                            type="button"
                            aria-label={`Descargar ${d.nombre}`}
                            disabled={!!d.nota}
                            className={`flex h-11 items-center justify-center gap-2 rounded-lg border text-xs font-medium ${
                              d.nota
                                ? 'text-slate-400 border-slate-200'
                                : 'text-slate-600 border-slate-300'
                            }`}
                          >
                            <Download className="h-4 w-4" /> Descargar
                          </button>
                          <button
                            type="button"
                            aria-label={`Reemplazar ${d.nombre}`}
                            className="flex h-11 items-center justify-center gap-2 rounded-lg border bg-[#000033] text-white text-xs font-medium"
                          >
                            <RefreshCw className="h-3.5 w-3.5" /> Reemplazar
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
            </>
          )}

          {!vistaBinaria && seccion === 'auditoria' && (
            <>
              <Card
                title="Auditoría y Logs"
                desc="Trazabilidad completa de cambios y evaluaciones"
                action={
                  <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                    <button
                      type="button"
                      className="h-11 rounded-lg border bg-white px-3 text-xs sm:h-8 sm:rounded-md"
                    >
                      Exportar CSV
                    </button>
                    <label className="sr-only" htmlFor="log-retention">
                      Retención de registros
                    </label>
                    <select
                      id="log-retention"
                      value={form.retencionLogs}
                      onChange={(e) =>
                        onChange('retencionLogs', Number(e.target.value))
                      }
                      className="h-11 rounded-lg border px-3 text-xs sm:h-8 sm:rounded-md sm:px-2"
                    >
                      <option value={30}>30 días</option>
                      <option value={90}>90 días</option>
                      <option value={180}>180 días</option>
                      <option value={365}>1 año</option>
                    </select>
                  </div>
                }
              >
                <div className="mb-4 flex flex-col gap-2 sm:flex-row">
                  <input
                    aria-label="Buscar en el registro de auditoría"
                    placeholder="Buscar por usuario, acción o IP..."
                    value={filtroAuditoria}
                    onChange={(e) => setFiltroAuditoria(e.target.value)}
                    className="h-11 flex-1 rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                  />
                  <select
                    aria-label="Filtrar registros por acción"
                    value={filtroDecision}
                    onChange={(e) => setFiltroDecision(e.target.value)}
                    className="h-11 w-full min-w-0 rounded-lg border px-3 text-base sm:h-9 sm:w-auto sm:rounded-md sm:px-2 sm:text-sm"
                  >
                    <option>Todas las acciones</option>
                    <option>Evaluaciones</option>
                    <option>Cambios de parámetros</option>
                    <option>Login</option>
                  </select>
                </div>
                {cargandoAuditoria && (
                  <div className="rounded-lg border bg-white p-6 text-sm text-zinc-600 text-center">
                    Cargando registros de auditoría…
                  </div>
                )}
                {errorAuditoria && !cargandoAuditoria && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-800 text-center">
                    {errorAuditoria}
                  </div>
                )}
                {!cargandoAuditoria && !errorAuditoria && (
                  <>
                    <div className="hidden overflow-auto rounded-md border sm:block">
                      <table className="w-full text-sm">
                        <thead className="bg-slate-50 text-[11px] uppercase text-slate-500">
                          <tr>
                            <th scope="col" className="text-left p-3">
                              Fecha
                            </th>
                            <th scope="col" className="text-left p-3">
                              Usuario
                            </th>
                            <th scope="col" className="text-left p-3">
                              Acción
                            </th>
                            <th scope="col" className="text-left p-3">
                              IP
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {logs.map((l) => (
                            <tr
                              key={l.id}
                              className="border-t hover:bg-slate-50"
                            >
                              <td className="p-3 text-xs flex items-center gap-1.5">
                                <Clock className="h-3 w-3 text-slate-400" />
                                {l.fecha}
                              </td>
                              <td className="p-3 font-medium">{l.usuario}</td>
                              <td className="p-3 text-xs">{l.accion}</td>
                              <td className="p-3 text-xs text-slate-500">
                                {l.ip}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="space-y-3 sm:hidden">
                      {logs.map((l) => (
                        <article
                          key={l.id}
                          className="rounded-xl border border-slate-200 bg-white p-4"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex min-w-0 items-start gap-2">
                              <Clock className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                              <p className="text-xs font-medium">{l.fecha}</p>
                            </div>
                            <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-medium text-slate-600">
                              {l.ip}
                            </span>
                          </div>
                          <p className="mt-3 text-sm font-semibold">
                            {l.usuario}
                          </p>
                          <p className="mt-1 text-xs leading-5 text-slate-600">
                            {l.accion}
                          </p>
                        </article>
                      ))}
                    </div>
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-500">
                      <AlertTriangle className="h-3 w-3" /> Los logs se retienen{' '}
                      {form.retencionLogs} días según tu configuración. Cumple
                      con auditoría interna.
                    </div>
                  </>
                )}
              </Card>
            </>
          )}

          {!vistaBinaria && seccion === 'seguridad' && (
            <>
              <Card
                title="API Keys"
                desc="Usa estas llaves en header X-API-Key. Nunca expongas en frontend público"
                action={
                  <button
                    type="button"
                    onClick={() =>
                      setApiKeys((p) => [
                        ...p,
                        {
                          id: Date.now(),
                          nombre: `Key ${p.length + 1}`,
                          key: `sk_live_${Math.random().toString(36).slice(2, 10)}...`,
                          creado: 'Hoy',
                          ultimoUso: 'Nunca',
                        },
                      ])
                    }
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#000033] px-3 text-xs font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                  >
                    <Key className="h-4 w-4 sm:h-3 sm:w-3" /> Nueva Key
                  </button>
                }
              >
                <div className="space-y-2">
                  {apiKeys.map((k) => (
                    <div
                      key={k.id}
                      className="flex flex-col gap-3 rounded-xl border bg-slate-50 p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                          {k.nombre}{' '}
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700">
                            Activa
                          </span>
                        </p>
                        <p className="mt-1 break-all text-xs font-mono text-slate-600">
                          {k.key} • Creada: {k.creado} • Último uso:{' '}
                          {k.ultimoUso}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          aria-label={`Copiar clave ${k.nombre}`}
                          className="grid h-11 flex-1 place-items-center rounded-lg border bg-white sm:h-9 sm:w-9 sm:flex-none sm:rounded"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setApiKeys((p) => p.filter((x) => x.id !== k.id))
                          }
                          aria-label={`Eliminar clave ${k.nombre}`}
                          className="grid h-11 flex-1 place-items-center rounded-lg border bg-white hover:bg-red-50 sm:h-9 sm:w-9 sm:flex-none sm:rounded"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
              <div className="grid md:grid-cols-2 gap-4">
                <Card
                  title="CORS y Dominios"
                  desc="Orígenes permitidos para consumir la API"
                  action={<Globe className="h-4 w-4 text-slate-400" />}
                >
                  <label
                    className="text-[11px] uppercase text-slate-600"
                    htmlFor="allowed-domains"
                  >
                    Dominios permitidos (separados por coma)
                  </label>
                  <textarea
                    id="allowed-domains"
                    value={cors}
                    onChange={(e) => setCors(e.target.value)}
                    className="mt-1 min-h-[96px] w-full rounded-lg border px-3 py-2 text-base sm:rounded-md sm:text-sm"
                    placeholder="https://..."
                  />
                  <p className="text-[11px] text-slate-500 mt-2">
                    Usa * solo en desarrollo. En producción lista blanca
                    estricta.
                  </p>
                </Card>
                <Card
                  title="Políticas de Seguridad"
                  desc="Bloqueos y complejidad"
                >
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <InputNumerico
                      label="Timeout sesión (min)"
                      minimo={1}
                      maximo={1440}
                      value={form.timeoutSesion}
                      onValor={(n) => onChange('timeoutSesion', n ?? 0)}
                    />
                    <InputNumerico
                      label="Intentos fallidos"
                      minimo={1}
                      maximo={20}
                      value={form.intentosFallidos}
                      onValor={(n) => onChange('intentosFallidos', n ?? 0)}
                    />
                    <InputNumerico
                      label="Bloqueo (min)"
                      minimo={1}
                      maximo={1440}
                      value={form.bloqueoMin}
                      onValor={(n) => onChange('bloqueoMin', n ?? 0)}
                    />
                    <InputNumerico
                      label="Longitud mín pass"
                      minimo={6}
                      maximo={128}
                      value={form.longitudPass}
                      onValor={(n) => onChange('longitudPass', n ?? 0)}
                    />
                  </div>
                </Card>
              </div>
            </>
          )}

          {!vistaBinaria && seccion === 'backup' && (
            <>
              <div className="grid md:grid-cols-3 gap-4">
                <Card title="Salud del Sistema">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">API Motor</span>
                      <span className="flex items-center gap-1.5 text-emerald-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> Operativo
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Base de datos</span>
                      <span className="flex items-center gap-1.5 text-emerald-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> 42ms
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-slate-600">Storage docs</span>
                      <span className="flex items-center gap-1.5 text-emerald-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> 78% libre
                      </span>
                    </div>
                    <div className="mt-3 h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full w-[92%] bg-emerald-600" />
                    </div>
                    <p className="text-[11px] text-slate-500">
                      Uptime 99.94% últimos 30 días
                    </p>
                  </div>
                </Card>
                <Card title="Últimos Respaldos">
                  <div className="space-y-2 text-sm">
                    {[
                      { f: '02/10/2026 02:00', s: '210MB', e: 'OK' },
                      { f: '01/10/2026 02:00', s: '208MB', e: 'OK' },
                      { f: '30/09/2026 02:00', s: '205MB', e: 'OK' },
                    ].map((b, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-2 rounded border bg-slate-50"
                      >
                        <div>
                          <p className="font-medium text-xs">{b.f}</p>
                          <p className="text-[11px] text-slate-500">
                            {b.s} • {b.e}
                          </p>
                        </div>
                        <Database className="h-4 w-4 text-slate-400" />
                      </div>
                    ))}
                  </div>
                </Card>
                <Card title="Backup Manual">
                  <div className="text-center py-2">
                    <HardDrive className="h-8 w-8 mx-auto text-slate-400" />
                    <p className="text-sm font-medium mt-2">
                      Respaldo bajo demanda
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Incluye parametros.json, usuarios y plantillas
                    </p>
                    <button className="mt-4 w-full h-9 rounded-md bg-[#000033] text-white text-sm flex items-center justify-center gap-1.5">
                      <RefreshCw className="h-4 w-4" /> Crear backup ahora
                    </button>
                    <p className="text-[11px] text-slate-500 mt-2">
                      Se guardará en /backups y S3 si está configurado
                    </p>
                  </div>
                </Card>
              </div>
              <Card
                title="Automatización"
                desc="Programación de respaldos automáticos"
              >
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="flex items-center justify-between rounded-lg border p-4">
                    <div>
                      <p className="text-sm font-medium">Backup automático</p>
                      <p className="text-xs text-slate-500">
                        Todos los días a la hora indicada
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onChange('backupAuto', !form.backupAuto)}
                      aria-label="Respaldo automático"
                      aria-pressed={form.backupAuto}
                      className={`h-6 w-11 rounded-full flex items-center ${form.backupAuto ? 'bg-[#000033] justify-end' : 'bg-slate-200 justify-start'}`}
                    >
                      <span className="h-4 w-4 rounded-full bg-white shadow mx-1" />
                    </button>
                  </div>
                  <Input
                    label="Hora ejecución"
                    type="time"
                    value={form.backupHora}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      onChange('backupHora', e.target.value)
                    }
                  />
                  <InputNumerico
                    label="Retención (días)"
                    minimo={1}
                    maximo={3650}
                    value={form.backupRetencion}
                    onValor={(n) => onChange('backupRetencion', n ?? 0)}
                  />
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
