import { useId, useState, useRef, useCallback, useEffect } from 'react'
import type { ChangeEvent, InputHTMLAttributes, ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
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
import {
  User,
  Cpu,
  ShieldCheck,
  Users,
  Building2,
  FileText,
  LineChart,
  KeyRound,
  HardDrive,
  X,
  Trash2,
  Plus,
  Pencil,
  Eye,
  EyeOff,
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

type SeccionId =
  | 'perfil'
  | 'usuarios'
  | 'motor'
  | 'riesgo'
  | 'concesionarios'
  | 'documentos'
  | 'auditoria'
  | 'seguridad'
  | 'backup'
type Usuario = {
  id: number
  n: string
  email: string
  telefono: string
  r: string
  c: string
  estado: 'Activo' | 'Inactivo'
}

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
    desc: 'Score, Quanto y límites',
  },
  {
    id: 'riesgo',
    label: 'Reglas de Riesgo',
    mobileLabel: 'Riesgo',
    icon: ShieldCheck,
    desc: 'Filtros y listas',
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
  <div className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
    <div className="mb-4 flex flex-col gap-3 sm:mb-5 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <h3 className="font-semibold text-[14px] tracking-tight">{title}</h3>
        {desc && <p className="text-xs text-zinc-500 mt-1">{desc}</p>}
      </div>
      {action}
    </div>
    {children}
  </div>
)

const Input = ({
  label,
  id,
  ...props
}: { label: string } & InputHTMLAttributes<HTMLInputElement>) => {
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <div className="space-y-1.5">
      <label
        htmlFor={inputId}
        className="text-[11px] font-medium uppercase tracking-wide text-zinc-600"
      >
        {label}
      </label>
      <input
        {...props}
        id={inputId}
        className="h-11 w-full rounded-md border border-zinc-200 bg-white px-3 text-base focus:outline-none focus:ring-1 focus:ring-zinc-900 sm:h-9 sm:text-sm"
      />
    </div>
  )
}

const CLASE_INPUT_NUMERICO =
  'h-9 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm focus:outline-none focus:ring-1 focus:ring-zinc-900'

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
    <div className="space-y-1.5">
      <label
        htmlFor={inputId}
        className="text-[11px] font-medium uppercase tracking-wide text-zinc-600"
      >
        {label}
      </label>
      <CampoNumerico
        id={inputId}
        className={CLASE_INPUT_NUMERICO}
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
  const [seccion, setSeccion] = useState<SeccionId>('perfil')
  const [hasChanges, setHasChanges] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const userModalRef = useRef<HTMLDivElement>(null)
  const [avatar, setAvatar] = useState<string | null>(null)
  const [concesionarios, setConcesionarios] = useState<string[]>([
    'Suzuki Palmira',
    'Hero Cali',
    'Bajaj Tuluá',
  ])
  const [nuevoConcesionario, setNuevoConcesionario] = useState('')
  const [showPass, setShowPass] = useState(false)
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

  // USUARIOS
  const [usuarios, setUsuarios] = useState<Usuario[]>([
    {
      id: 1,
      n: 'Laura G.',
      email: 'laura@sumoto.com',
      telefono: '310 111 1111',
      r: 'Analista',
      c: 'Suzuki Palmira',
      estado: 'Activo',
    },
    {
      id: 2,
      n: 'Juan P.',
      email: 'juan@sumoto.com',
      telefono: '310 222 2222',
      r: 'Asesor',
      c: 'Hero Cali',
      estado: 'Activo',
    },
  ])
  const [searchUser, setSearchUser] = useState('')
  const [showUserModal, setShowUserModal] = useState(false)
  const [editingUser, setEditingUser] = useState<Usuario | null>(null)
  useEffect(() => {
    if (!showUserModal) return

    const returnFocusTo =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    userModalRef.current
      ?.querySelector<HTMLElement>(
        'input:not([disabled]), select:not([disabled])',
      )
      ?.focus()

    return () => returnFocusTo?.focus()
  }, [showUserModal])

  const [userForm, setUserForm] = useState({
    nombre: '',
    email: '',
    telefono: '',
    cargo: 'Asesor',
    concesionario: 'Suzuki Palmira',
    estado: 'Activo',
    password: '',
  })

  // DOCUMENTOS
  const [documentos, setDocumentos] = useState([
    {
      id: 1,
      nombre: 'Cédula frontal',
      requerido: true,
      formato: 'PDF/JPG',
      max: '5MB',
      activo: true,
    },
    {
      id: 2,
      nombre: 'Desprendible de nómina',
      requerido: true,
      formato: 'PDF',
      max: '10MB',
      activo: true,
    },
    {
      id: 3,
      nombre: 'Contrato de crédito',
      requerido: false,
      formato: 'PDF/DOCX',
      max: '20MB',
      activo: true,
    },
  ])

  // AUDITORIA
  const [logs] = useState([
    {
      id: 1,
      fecha: '02/10/2026 11:42',
      usuario: 'Alejandro G.',
      accion: 'Evaluó crédito #9821',
      ip: '190.121.45.XX',
    },
    {
      id: 2,
      fecha: '02/10/2026 10:15',
      usuario: 'Laura G.',
      accion: 'Actualizó parametros.json',
      ip: '190.121.46.10',
    },
    {
      id: 3,
      fecha: '01/10/2026 16:20',
      usuario: 'Sistema',
      accion: 'Backup automático completado',
      ip: 'localhost',
    },
  ])

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
    email: 'desarrollo@saumoto.com.co',
    telefono: '3211234567',
    cargo: 'Super Admin',
    passActual: '',
    passNueva: '',
    passConfirma: '',
    twoFA: true,
    metodo2FA: 'App autenticadora',
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
    void cargarParametros()
  }, [cargarParametros])

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
  const openCreateModal = () => {
    setEditingUser(null)
    setUserForm({
      nombre: '',
      email: '',
      telefono: '',
      cargo: 'Asesor',
      concesionario: concesionarios[0],
      estado: 'Activo',
      password: '',
    })
    setShowUserModal(true)
  }
  const openEditModal = (u: Usuario) => {
    setEditingUser(u)
    setUserForm({
      nombre: u.n,
      email: u.email,
      telefono: u.telefono,
      cargo: u.r,
      concesionario: u.c,
      estado: u.estado,
      password: '',
    })
    setShowUserModal(true)
  }
  const handleSaveUser = () => {
    if (!userForm.nombre || !userForm.email) return
    if (editingUser)
      setUsuarios((p) =>
        p.map((x) =>
          x.id === editingUser.id
            ? {
                ...x,
                n: userForm.nombre,
                email: userForm.email,
                telefono: userForm.telefono,
                r: userForm.cargo,
                c: userForm.concesionario,
                estado: userForm.estado as Usuario['estado'],
              }
            : x,
        ),
      )
    else
      setUsuarios((p) => [
        ...p,
        {
          id: Date.now(),
          n: userForm.nombre,
          email: userForm.email,
          telefono: userForm.telefono,
          r: userForm.cargo,
          c: userForm.concesionario,
          estado: userForm.estado as Usuario['estado'],
        },
      ])
    setShowUserModal(false)
    setHasChanges(true)
  }

  return (
    <div className="min-h-screen overflow-x-clip bg-[#F8FAFC] text-zinc-900">
      <div className="sticky top-0 z-20 border-b bg-white">
        <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-2 pl-16 pr-3 sm:px-6">
          <h1 className="flex min-w-0 items-center gap-2 text-base font-semibold">
            Ajustes
            {(hasChanges || parametrosModificados) && (
              <span className="truncate rounded-full bg-amber-100 px-2.5 py-1 text-[10px] font-medium text-amber-900 sm:text-[11px]">
                <span className="sm:hidden">Sin guardar</span>
                <span className="hidden sm:inline">Cambios sin guardar</span>
              </span>
            )}
          </h1>
          <button
            onClick={() => void guardarCambios()}
            disabled={
              guardandoParametros || (!hasChanges && !parametrosModificados)
            }
            aria-label="Guardar cambios"
            className="h-10 shrink-0 rounded-lg bg-zinc-900 px-3 text-xs font-medium text-white shadow-sm transition hover:bg-zinc-700 disabled:opacity-40 sm:px-4"
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
        </div>
      </div>

      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-4 px-3 py-4 sm:px-6 sm:py-6 lg:grid-cols-[260px_minmax(0,1fr)] lg:gap-6">
        <nav
          aria-label="Secciones de ajustes"
          className="sticky top-14 z-10 -mx-3 flex min-w-0 snap-x snap-mandatory gap-2 overflow-x-auto border-b border-zinc-200 bg-[#F8FAFC]/95 px-3 py-2 backdrop-blur sm:-mx-6 sm:px-6 lg:top-[68px] lg:mx-0 lg:block lg:h-fit lg:space-y-1 lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0 lg:backdrop-blur-none"
        >
          {SECCIONES.map((s) => {
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
                    ? 'border-zinc-900 bg-zinc-900 text-white shadow-sm'
                    : 'border-zinc-200 bg-white text-zinc-600 hover:border-zinc-300 hover:bg-zinc-50 lg:border-transparent lg:bg-transparent lg:shadow-none'
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
              <p className="font-medium text-[11px] uppercase text-zinc-600">
                Última conexión
              </p>
              <p className="text-zinc-500 mt-1">
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
          <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900">
            La configuración conectada al backend corresponde al motor de
            decisión y sus reglas de riesgo. Las demás secciones aún no cuentan
            con endpoints de persistencia y sus cambios no se guardan en el
            servidor.
          </div>
          {(errorParametros || mensajeParametros) && (
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
                        className="h-24 w-24 rounded-full bg-zinc-50 border-2 border-dashed border-zinc-300 overflow-hidden flex items-center justify-center cursor-pointer hover:border-zinc-900 group focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900"
                      >
                        {avatar ? (
                          <img
                            src={avatar}
                            alt="Foto de perfil"
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex flex-col items-center">
                            <User className="h-7 w-7 text-zinc-400 group-hover:text-zinc-900" />
                            <span className="text-[10px] uppercase text-zinc-500 mt-1">
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
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 flex-1 min-w-0">
                    <Input
                      label="Nombre completo"
                      value={form.nombre}
                      onChange={(e: ChangeEvent<HTMLInputElement>) =>
                        onChange('nombre', e.target.value)
                      }
                    />
                    <Input
                      label="Correo"
                      value={form.email}
                      onChange={(e: ChangeEvent<HTMLInputElement>) =>
                        onChange('email', e.target.value)
                      }
                    />
                    <Input
                      label="Teléfono"
                      value={form.telefono}
                      onChange={(e: ChangeEvent<HTMLInputElement>) =>
                        onChange('telefono', e.target.value)
                      }
                    />
                    <div className="space-y-1.5">
                      <label
                        className="text-[11px] uppercase text-zinc-600"
                        htmlFor="profile-role"
                      >
                        Cargo
                      </label>
                      <select
                        id="profile-role"
                        value={form.cargo}
                        onChange={(e) => onChange('cargo', e.target.value)}
                        className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                      >
                        <option>Super Admin</option>
                        <option>Administrador</option>
                        <option>Analista</option>
                        <option>Asesor</option>
                      </select>
                    </div>
                    <div className="sm:col-span-2">
                      <p className="text-[11px] uppercase text-zinc-600">
                        Concesionarios asignados
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-2">
                        {concesionarios.map((c) => (
                          <span
                            key={c}
                            className="text-xs px-2.5 py-1 rounded-full bg-zinc-900 text-white flex items-center gap-1.5"
                          >
                            {c}
                            <button
                              type="button"
                              onClick={() => removeConcesionario(c)}
                              aria-label={`Quitar concesionario ${c}`}
                              className="h-6 w-6 rounded-full bg-white/20 grid place-items-center"
                            >
                              <X className="h-3 w-3" />
                            </button>
                          </span>
                        ))}
                      </div>
                      <div className="mt-3 flex flex-col gap-2 max-w-sm sm:flex-row">
                        <label className="sr-only" htmlFor="new-dealer">
                          Nuevo concesionario
                        </label>
                        <input
                          id="new-dealer"
                          value={nuevoConcesionario}
                          onChange={(e) =>
                            setNuevoConcesionario(e.target.value)
                          }
                          onKeyDown={(e) =>
                            e.key === 'Enter' && addConcesionario()
                          }
                          placeholder="Ej: Suzuki Yumbo"
                          className="h-11 w-full min-w-0 rounded-lg border px-3 text-base sm:h-9 sm:flex-1 sm:rounded-md sm:text-sm"
                        />
                        <button
                          type="button"
                          onClick={addConcesionario}
                          className="flex h-11 items-center justify-center gap-1 rounded-lg border bg-white px-3 text-xs sm:h-9 sm:rounded-md"
                        >
                          <Plus className="h-3 w-3" /> Añadir
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
              <Card title="Seguridad" desc="Contraseña y 2FA">
                <div className="grid md:grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <label
                      className="text-[11px] uppercase text-zinc-600"
                      htmlFor="current-password"
                    >
                      Actual
                    </label>
                    <div className="relative">
                      <input
                        id="current-password"
                        type={showPass ? 'text' : 'password'}
                        value={form.passActual}
                        onChange={(e) => onChange('passActual', e.target.value)}
                        placeholder="••••••••"
                        className="h-11 w-full rounded-lg border px-3 pr-10 text-base sm:h-9 sm:rounded-md sm:text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPass(!showPass)}
                        aria-label={
                          showPass
                            ? 'Ocultar contraseña actual'
                            : 'Mostrar contraseña actual'
                        }
                        aria-pressed={showPass}
                        className="absolute right-1 top-1.5 grid h-6 w-6 place-items-center text-zinc-600"
                      >
                        {showPass ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                  <Input
                    label="Nueva"
                    type="password"
                    value={form.passNueva}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      onChange('passNueva', e.target.value)
                    }
                  />
                  <Input
                    label="Confirmar"
                    type="password"
                    value={form.passConfirma}
                    onChange={(e: ChangeEvent<HTMLInputElement>) =>
                      onChange('passConfirma', e.target.value)
                    }
                  />
                </div>
                <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border p-4 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4" /> 2FA
                      </p>
                      <p className="text-xs text-zinc-500">Segundo factor</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onChange('twoFA', !form.twoFA)}
                      aria-label="Autenticación de dos factores"
                      aria-pressed={form.twoFA}
                      className={`h-6 w-11 rounded-full flex items-center ${form.twoFA ? 'bg-zinc-900 justify-end' : 'bg-zinc-200 justify-start'}`}
                    >
                      <span className="h-4 w-4 rounded-full bg-white shadow mx-1" />
                    </button>
                  </div>
                  <div className="rounded-lg border p-4">
                    <label
                      className="text-[11px] uppercase text-zinc-600"
                      htmlFor="two-factor-method"
                    >
                      Método
                    </label>
                    <select
                      id="two-factor-method"
                      value={form.metodo2FA}
                      onChange={(e) => onChange('metodo2FA', e.target.value)}
                      className="mt-1 h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:px-2 sm:text-sm"
                    >
                      <option>App autenticadora</option>
                      <option>SMS</option>
                      <option>Email</option>
                    </select>
                  </div>
                </div>
              </Card>
              <div className="grid md:grid-cols-2 gap-4">
                <Card
                  title="Preferencias"
                  action={<Palette className="h-4 w-4 text-zinc-400" />}
                >
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label
                        className="text-[11px] uppercase text-zinc-600"
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
                        className="text-[11px] uppercase text-zinc-600"
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
                  action={<Monitor className="h-4 w-4 text-zinc-400" />}
                >
                  <div className="rounded-md bg-zinc-50 border p-3 text-xs">
                    <p className="font-medium">Sesión actual</p>
                    <p className="text-zinc-600 mt-1">
                      02/10/2026 11:42 • 190.121.45.XX
                      <br />
                      Palmira, CO • Chrome / Windows
                    </p>
                    <span className="mt-2 inline-flex text-[10px] px-2 py-0.5 rounded-full bg-green-50 border border-green-200 text-green-700">
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

          {seccion === 'usuarios' && (
            <Card
              title="Usuarios y Permisos"
              desc="Edita, crea y elimina. El límite está en Motor"
            >
              <div className="flex flex-col sm:flex-row gap-2 mb-4">
                <button
                  onClick={openCreateModal}
                  type="button"
                  className="flex h-11 items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 text-xs font-medium text-white sm:h-9 sm:rounded-md"
                >
                  <Plus className="h-4 w-4 sm:h-3 sm:w-3" /> Crear
                </button>
                <input
                  aria-label="Buscar usuarios"
                  value={searchUser}
                  onChange={(e) => setSearchUser(e.target.value)}
                  placeholder="Buscar..."
                  className="h-11 w-full min-w-0 rounded-lg border px-3 text-base sm:h-9 sm:w-64 sm:rounded-md sm:text-sm"
                />
              </div>
              <div className="hidden overflow-auto rounded-md border sm:block">
                <table className="w-full text-sm">
                  <thead className="bg-zinc-50 text-[11px] uppercase text-zinc-500">
                    <tr>
                      <th scope="col" className="text-left p-3">
                        Usuario
                      </th>
                      <th scope="col" className="text-left p-3">
                        Rol
                      </th>
                      <th scope="col" className="text-left p-3">
                        Concesionario
                      </th>
                      <th scope="col" className="text-left p-3">
                        Estado
                      </th>
                      <th scope="col" className="text-right p-3">
                        Acciones
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuarios
                      .filter((u) =>
                        u.n.toLowerCase().includes(searchUser.toLowerCase()),
                      )
                      .map((u) => (
                        <tr key={u.id} className="border-t hover:bg-zinc-50">
                          <td className="p-3">
                            <p className="font-medium">{u.n}</p>
                            <p className="text-xs text-zinc-500">{u.email}</p>
                          </td>
                          <td className="p-3">
                            <span className="text-xs px-2 py-1 rounded border bg-white">
                              {u.r}
                            </span>
                          </td>
                          <td className="p-3 text-xs">{u.c}</td>
                          <td className="p-3">
                            <span
                              className={`text-[11px] px-2 py-0.5 rounded-full border ${u.estado === 'Activo' ? 'bg-green-50 text-green-700 border-green-200' : 'bg-zinc-100'}`}
                            >
                              {u.estado}
                            </span>
                          </td>
                          <td className="p-3">
                            <div className="flex justify-end gap-1">
                              <button
                                type="button"
                                onClick={() => openEditModal(u)}
                                aria-label={`Editar usuario ${u.n}`}
                                className="h-7 w-7 grid place-items-center rounded border"
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setUsuarios((p) =>
                                    p.filter((x) => x.id !== u.id),
                                  )
                                }
                                aria-label={`Eliminar usuario ${u.n}`}
                                className="h-7 w-7 grid place-items-center rounded border"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <div className="space-y-3 sm:hidden">
                {usuarios
                  .filter((u) =>
                    u.n.toLowerCase().includes(searchUser.toLowerCase()),
                  )
                  .map((u) => (
                    <article
                      key={u.id}
                      className="rounded-xl border border-zinc-200 bg-white p-4 shadow-sm"
                    >
                      <div className="flex min-w-0 items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold">
                            {u.n}
                          </p>
                          <p className="mt-1 break-all text-xs text-zinc-500">
                            {u.email}
                          </p>
                        </div>
                        <span
                          className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] ${u.estado === 'Activo' ? 'border-green-200 bg-green-50 text-green-700' : 'border-zinc-200 bg-zinc-100 text-zinc-600'}`}
                        >
                          {u.estado}
                        </span>
                      </div>
                      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-zinc-100 pt-3">
                        <div>
                          <dt className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                            Rol
                          </dt>
                          <dd className="mt-1 text-xs font-medium">{u.r}</dd>
                        </div>
                        <div className="min-w-0">
                          <dt className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                            Concesionario
                          </dt>
                          <dd className="mt-1 truncate text-xs font-medium">
                            {u.c}
                          </dd>
                        </div>
                      </dl>
                      <div className="mt-3 flex gap-2 border-t border-zinc-100 pt-3">
                        <button
                          type="button"
                          onClick={() => openEditModal(u)}
                          className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border text-xs font-medium"
                        >
                          <Pencil className="h-4 w-4" /> Editar
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setUsuarios((actuales) =>
                              actuales.filter((usuario) => usuario.id !== u.id),
                            )
                          }
                          aria-label={`Eliminar usuario ${u.n}`}
                          className="grid h-11 w-11 place-items-center rounded-lg border text-zinc-500 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </article>
                  ))}
              </div>
            </Card>
          )}

          {seccion === 'motor' && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-zinc-500">
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

          {seccion === 'riesgo' && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-zinc-500">
                  Reglas de elegibilidad, buró y endeudamiento del backend.
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
                seccion="riesgo"
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

          {seccion === 'concesionarios' && (
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
                  placeholder="Ej: Suzuki Yumbo"
                  className="h-11 w-full flex-1 rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                />
                <button
                  type="button"
                  onClick={addConcesionario}
                  className="h-11 w-full rounded-lg bg-zinc-900 px-4 text-sm font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                >
                  Agregar
                </button>
              </div>
              <div className="grid md:grid-cols-2 gap-3">
                {concesionarios.map((c) => (
                  <div
                    key={c}
                    className="flex items-center justify-between p-4 rounded-lg border bg-white hover:border-zinc-300 transition-colors"
                  >
                    <div>
                      <p className="text-sm font-medium">{c}</p>
                      <p className="text-xs text-zinc-500 mt-0.5">
                        Cupo: $120M • Usado: $45M • Asesores: 3
                      </p>
                      <div className="mt-2 h-1.5 w-32 bg-zinc-100 rounded-full overflow-hidden">
                        <div className="h-full w-[37%] bg-zinc-900" />
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeConcesionario(c)}
                      aria-label={`Quitar concesionario ${c}`}
                      className="grid h-11 w-11 shrink-0 place-items-center rounded-lg border text-zinc-500 hover:bg-red-50 hover:text-red-600 sm:h-9 sm:w-9 sm:rounded-md"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {seccion === 'documentos' && (
            <>
              <Card
                title="Documentos y Plantillas"
                desc="Gestiona requisitos por tipo de crédito. Afecta el checklist del asesor"
                action={
                  <button
                    type="button"
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 text-xs font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                  >
                    <Upload className="h-4 w-4 sm:h-3 sm:w-3" /> Subir plantilla
                  </button>
                }
              >
                <div className="hidden overflow-auto rounded-md border sm:block">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 text-[11px] uppercase text-zinc-500">
                      <tr>
                        <th scope="col" className="text-left p-3">
                          Documento
                        </th>
                        <th scope="col" className="text-left p-3">
                          Requerido
                        </th>
                        <th scope="col" className="text-left p-3">
                          Formato
                        </th>
                        <th scope="col" className="text-left p-3">
                          Tamaño Máx
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
                      {documentos.map((d) => (
                        <tr key={d.id} className="border-t hover:bg-zinc-50">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <FileCheck className="h-4 w-4 text-zinc-400" />
                              <span className="font-medium">{d.nombre}</span>
                            </div>
                          </td>
                          <td className="p-3">
                            <span
                              className={`text-[11px] px-2 py-0.5 rounded-full border ${d.requerido ? 'bg-amber-50 text-amber-700 border-amber-200' : 'bg-zinc-50 text-zinc-600'}`}
                            >
                              {d.requerido ? 'Obligatorio' : 'Opcional'}
                            </span>
                          </td>
                          <td className="p-3 text-xs">{d.formato}</td>
                          <td className="p-3 text-xs">{d.max}</td>
                          <td className="p-3">
                            <button
                              type="button"
                              onClick={() =>
                                setDocumentos((p) =>
                                  p.map((x) =>
                                    x.id === d.id
                                      ? { ...x, activo: !x.activo }
                                      : x,
                                  ),
                                )
                              }
                              aria-label={`Documento activo: ${d.nombre}`}
                              aria-pressed={d.activo}
                              className={`h-6 w-11 rounded-full flex items-center ${d.activo ? 'bg-zinc-900 justify-end' : 'bg-zinc-200 justify-start'}`}
                            >
                              <span className="h-4 w-4 rounded-full bg-white shadow mx-1" />
                            </button>
                          </td>
                          <td className="p-3">
                            <div className="flex justify-end gap-1">
                              <button
                                type="button"
                                aria-label={`Descargar ${d.nombre}`}
                                className="h-7 w-7 grid place-items-center rounded border"
                              >
                                <Download className="h-3.5 w-3.5" />
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  setDocumentos((p) =>
                                    p.filter((x) => x.id !== d.id),
                                  )
                                }
                                aria-label={`Eliminar documento ${d.nombre}`}
                                className="h-7 w-7 grid place-items-center rounded border hover:bg-red-50"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-3 sm:hidden">
                  {documentos.map((d) => (
                    <article
                      key={d.id}
                      className="rounded-xl border border-zinc-200 bg-white p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2">
                          <FileCheck className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                          <div className="min-w-0">
                            <p className="text-sm font-semibold">{d.nombre}</p>
                            <p className="mt-1 text-xs text-zinc-500">
                              {d.formato} · Máx. {d.max}
                            </p>
                          </div>
                        </div>
                        <span
                          className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium ${d.requerido ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-zinc-200 bg-zinc-50 text-zinc-600'}`}
                        >
                          {d.requerido ? 'Obligatorio' : 'Opcional'}
                        </span>
                      </div>
                      <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3">
                        <span className="text-xs font-medium text-zinc-600">
                          {d.activo ? 'Documento activo' : 'Documento inactivo'}
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            setDocumentos((actuales) =>
                              actuales.map((documento) =>
                                documento.id === d.id
                                  ? { ...documento, activo: !documento.activo }
                                  : documento,
                              ),
                            )
                          }
                          aria-label={`Documento activo: ${d.nombre}`}
                          aria-pressed={d.activo}
                          className={`flex h-11 w-14 items-center rounded-full ${d.activo ? 'justify-end bg-zinc-900' : 'justify-start bg-zinc-200'}`}
                        >
                          <span className="mx-1 h-5 w-5 rounded-full bg-white shadow" />
                        </button>
                      </div>
                      <div className="mt-3 flex gap-2">
                        <button
                          type="button"
                          aria-label={`Descargar ${d.nombre}`}
                          className="flex h-11 flex-1 items-center justify-center gap-2 rounded-lg border text-xs font-medium"
                        >
                          <Download className="h-4 w-4" /> Descargar
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setDocumentos((actuales) =>
                              actuales.filter(
                                (documento) => documento.id !== d.id,
                              ),
                            )
                          }
                          aria-label={`Eliminar documento ${d.nombre}`}
                          className="grid h-11 w-11 place-items-center rounded-lg border text-zinc-500 hover:bg-red-50 hover:text-red-600"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </Card>
              <Card
                title="Plantilla de Contrato Base"
                desc="PDF que se genera automáticamente al aprobar"
              >
                <div className="rounded-xl border border-dashed bg-zinc-50 p-5 text-center sm:p-8">
                  <FileText className="h-8 w-8 mx-auto text-zinc-400" />
                  <p className="text-sm font-medium mt-2">
                    contrato_base_v4.pdf
                  </p>
                  <p className="text-xs text-zinc-500 mt-1">
                    Última actualización: 28/09/2026 • 2.4MB
                  </p>
                  <div className="mt-4 grid grid-cols-1 gap-2 sm:flex sm:justify-center">
                    <button
                      type="button"
                      className="h-11 rounded-lg border bg-white px-3 text-xs sm:h-9 sm:rounded-md"
                    >
                      Ver PDF
                    </button>
                    <button
                      type="button"
                      className="h-11 rounded-lg bg-zinc-900 px-3 text-xs text-white sm:h-9 sm:rounded-md"
                    >
                      Reemplazar
                    </button>
                  </div>
                </div>
              </Card>
            </>
          )}

          {seccion === 'auditoria' && (
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
                    className="h-11 flex-1 rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                  />
                  <select
                    aria-label="Filtrar registros por acción"
                    className="h-11 w-full min-w-0 rounded-lg border px-3 text-base sm:h-9 sm:w-auto sm:rounded-md sm:px-2 sm:text-sm"
                  >
                    <option>Todas las acciones</option>
                    <option>Evaluaciones</option>
                    <option>Cambios de parámetros</option>
                    <option>Login</option>
                  </select>
                </div>
                <div className="hidden overflow-auto rounded-md border sm:block">
                  <table className="w-full text-sm">
                    <thead className="bg-zinc-50 text-[11px] uppercase text-zinc-500">
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
                        <tr key={l.id} className="border-t hover:bg-zinc-50">
                          <td className="p-3 text-xs flex items-center gap-1.5">
                            <Clock className="h-3 w-3 text-zinc-400" />
                            {l.fecha}
                          </td>
                          <td className="p-3 font-medium">{l.usuario}</td>
                          <td className="p-3 text-xs">{l.accion}</td>
                          <td className="p-3 text-xs text-zinc-500">{l.ip}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-3 sm:hidden">
                  {logs.map((l) => (
                    <article
                      key={l.id}
                      className="rounded-xl border border-zinc-200 bg-white p-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-2">
                          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" />
                          <p className="text-xs font-medium">{l.fecha}</p>
                        </div>
                        <span className="shrink-0 rounded-full bg-zinc-100 px-2.5 py-1 text-[10px] font-medium text-zinc-600">
                          {l.ip}
                        </span>
                      </div>
                      <p className="mt-3 text-sm font-semibold">{l.usuario}</p>
                      <p className="mt-1 text-xs leading-5 text-zinc-600">
                        {l.accion}
                      </p>
                    </article>
                  ))}
                </div>
                <div className="mt-3 flex items-center gap-2 text-[11px] text-zinc-500">
                  <AlertTriangle className="h-3 w-3" /> Los logs se retienen{' '}
                  {form.retencionLogs} días según tu configuración. Cumple con
                  auditoría interna.
                </div>
              </Card>
            </>
          )}

          {seccion === 'seguridad' && (
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
                    className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 px-3 text-xs font-medium text-white sm:h-9 sm:w-auto sm:rounded-md"
                  >
                    <Key className="h-4 w-4 sm:h-3 sm:w-3" /> Nueva Key
                  </button>
                }
              >
                <div className="space-y-2">
                  {apiKeys.map((k) => (
                    <div
                      key={k.id}
                      className="flex flex-col gap-3 rounded-xl border bg-zinc-50 p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                          {k.nombre}{' '}
                          <span className="text-[11px] px-2 py-0.5 rounded-full bg-green-50 border border-green-200 text-green-700">
                            Activa
                          </span>
                        </p>
                        <p className="mt-1 break-all text-xs font-mono text-zinc-600">
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
                  action={<Globe className="h-4 w-4 text-zinc-400" />}
                >
                  <label
                    className="text-[11px] uppercase text-zinc-600"
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
                  <p className="text-[11px] text-zinc-500 mt-2">
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

          {seccion === 'backup' && (
            <>
              <div className="grid md:grid-cols-3 gap-4">
                <Card title="Salud del Sistema">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-600">API Motor</span>
                      <span className="flex items-center gap-1.5 text-green-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> Operativo
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-600">Base de datos</span>
                      <span className="flex items-center gap-1.5 text-green-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> 42ms
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-zinc-600">Storage docs</span>
                      <span className="flex items-center gap-1.5 text-green-700 text-xs">
                        <CheckCircle2 className="h-4 w-4" /> 78% libre
                      </span>
                    </div>
                    <div className="mt-3 h-2 w-full bg-zinc-100 rounded-full overflow-hidden">
                      <div className="h-full w-[92%] bg-green-600" />
                    </div>
                    <p className="text-[11px] text-zinc-500">
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
                        className="flex items-center justify-between p-2 rounded border bg-zinc-50"
                      >
                        <div>
                          <p className="font-medium text-xs">{b.f}</p>
                          <p className="text-[11px] text-zinc-500">
                            {b.s} • {b.e}
                          </p>
                        </div>
                        <Database className="h-4 w-4 text-zinc-400" />
                      </div>
                    ))}
                  </div>
                </Card>
                <Card title="Backup Manual">
                  <div className="text-center py-2">
                    <HardDrive className="h-8 w-8 mx-auto text-zinc-400" />
                    <p className="text-sm font-medium mt-2">
                      Respaldo bajo demanda
                    </p>
                    <p className="text-xs text-zinc-500 mt-1">
                      Incluye parametros.json, usuarios y plantillas
                    </p>
                    <button className="mt-4 w-full h-9 rounded-md bg-zinc-900 text-white text-sm flex items-center justify-center gap-1.5">
                      <RefreshCw className="h-4 w-4" /> Crear backup ahora
                    </button>
                    <p className="text-[11px] text-zinc-500 mt-2">
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
                      <p className="text-xs text-zinc-500">
                        Todos los días a la hora indicada
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => onChange('backupAuto', !form.backupAuto)}
                      aria-label="Respaldo automático"
                      aria-pressed={form.backupAuto}
                      className={`h-6 w-11 rounded-full flex items-center ${form.backupAuto ? 'bg-zinc-900 justify-end' : 'bg-zinc-200 justify-start'}`}
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

      {showUserModal && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4">
          <div
            ref={userModalRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="user-modal-title"
            aria-describedby="user-modal-description"
            onKeyDown={(event) => {
              if (event.key === 'Escape') {
                setShowUserModal(false)
                return
              }
              if (event.key !== 'Tab') return

              const focusable =
                userModalRef.current?.querySelectorAll<HTMLElement>(
                  'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]',
                )
              if (!focusable?.length) return
              const first = focusable[0]
              const last = focusable[focusable.length - 1]
              if (event.shiftKey && document.activeElement === first) {
                event.preventDefault()
                last.focus()
              } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault()
                first.focus()
              }
            }}
            className="flex max-h-[92dvh] w-full max-w-[520px] flex-col overflow-hidden rounded-t-2xl border bg-white shadow-2xl sm:max-h-[calc(100dvh-2rem)] sm:rounded-xl"
          >
            <div className="flex shrink-0 items-center justify-between border-b p-4 sm:p-5">
              <div>
                <h3 id="user-modal-title" className="font-semibold text-sm">
                  {editingUser ? 'Editar usuario' : 'Nuevo usuario'}
                </h3>
                <p
                  id="user-modal-description"
                  className="text-xs text-zinc-500"
                >
                  {editingUser ? `Editando a ${editingUser.n}` : 'Crear acceso'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowUserModal(false)}
                aria-label="Cerrar diálogo"
                className="grid h-11 w-11 place-items-center rounded-full hover:bg-zinc-100 sm:h-8 sm:w-8"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-4 overflow-y-auto p-4 sm:p-5">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input
                  label="Nombre *"
                  value={userForm.nombre}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setUserForm((s) => ({ ...s, nombre: e.target.value }))
                  }
                />
                <Input
                  label="Teléfono"
                  value={userForm.telefono}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setUserForm((s) => ({ ...s, telefono: e.target.value }))
                  }
                />
              </div>
              <Input
                label="Email *"
                value={userForm.email}
                onChange={(e: ChangeEvent<HTMLInputElement>) =>
                  setUserForm((s) => ({ ...s, email: e.target.value }))
                }
              />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase" htmlFor="modal-role">
                    Rol
                  </label>
                  <select
                    id="modal-role"
                    value={userForm.cargo}
                    onChange={(e) =>
                      setUserForm((s) => ({ ...s, cargo: e.target.value }))
                    }
                    className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                  >
                    <option>Asesor</option>
                    <option>Analista</option>
                    <option>Administrador</option>
                    <option>Super Admin</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <label
                    className="text-[11px] uppercase"
                    htmlFor="modal-dealer"
                  >
                    Concesionario
                  </label>
                  <select
                    id="modal-dealer"
                    value={userForm.concesionario}
                    onChange={(e) =>
                      setUserForm((s) => ({
                        ...s,
                        concesionario: e.target.value,
                      }))
                    }
                    className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                  >
                    {concesionarios.map((c) => (
                      <option key={c}>{c}</option>
                    ))}
                    <option>Todos</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <label
                    className="text-[11px] uppercase"
                    htmlFor="modal-state"
                  >
                    Estado
                  </label>
                  <select
                    id="modal-state"
                    value={userForm.estado}
                    onChange={(e) =>
                      setUserForm((s) => ({ ...s, estado: e.target.value }))
                    }
                    className="h-11 w-full rounded-lg border px-3 text-base sm:h-9 sm:rounded-md sm:text-sm"
                  >
                    <option>Activo</option>
                    <option>Inactivo</option>
                  </select>
                </div>
                <Input
                  label={editingUser ? 'Nueva contraseña' : 'Contraseña *'}
                  type="password"
                  value={userForm.password}
                  onChange={(e: ChangeEvent<HTMLInputElement>) =>
                    setUserForm((s) => ({ ...s, password: e.target.value }))
                  }
                />
              </div>
            </div>
            <div className="flex shrink-0 flex-col-reverse gap-2 rounded-b-xl bg-zinc-50 p-4 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => setShowUserModal(false)}
                className="h-11 rounded-lg border bg-white px-4 text-sm sm:h-9 sm:rounded-md"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveUser}
                className="h-11 rounded-lg bg-zinc-900 px-5 text-sm text-white sm:h-9 sm:rounded-md"
              >
                {editingUser ? 'Guardar' : 'Crear'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
