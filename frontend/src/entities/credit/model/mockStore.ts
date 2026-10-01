import { MOCK_APPLICATIONS, type SolicitudMock } from './mockData'
import {
  evaluateCreditApplication,
  type ResultadoEvaluacion,
  type SolicitudEvaluable,
} from './underwritingEngine'

export interface DocumentosSolicitud {
  cedulaFrente: string
  cedulaDorso: string
  videoSala: string
  videoMeta: {
    duracion_seg: number
    fecha: string
    concesionario?: string
    asesor?: string
  }
  datacredito: Record<string, unknown>
  ingresos: Record<string, unknown>
}

export type RegistroSolicitud = SolicitudMock &
  ResultadoEvaluacion & {
    cedula?: string
    vendedor?: string
    documentos: DocumentosSolicitud
  }

type BaseDocumentos = Partial<SolicitudMock & ResultadoEvaluacion> & {
  cedula?: string
  vendedor?: string
  documentos?: DocumentosSolicitud
}

let applications: RegistroSolicitud[] = []

function buildDocumentos(base: BaseDocumentos): DocumentosSolicitud {
  // Si ya trae documentos, los respetamos
  if (base.documentos) return base.documentos

  const seed =
    base.cedula || base.documento || base.id || Math.random().toString()
  const puntaje = base.creditScore ?? 680
  // fotos aleatorias para no repetir siempre la misma cédula
  const cedulaId = String(seed).slice(-4)

  return {
    cedulaFrente: `https://placehold.co/600x380/1e293b/ffffff?text=CEDULA+ANVERSO+${cedulaId}`,
    cedulaDorso: `https://placehold.co/600x380/334155/ffffff?text=CEDULA+REVERSO+${cedulaId}`,
    // video corto de muestra - luego reemplazas por el real subido
    videoSala:
      'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4',
    videoMeta: {
      duracion_seg: 12,
      fecha: base.createdAt || new Date().toISOString(),
      concesionario: base.concesionario,
      asesor: base.asesor || base.vendedor,
    },
    // JSON 1 - Historial crediticio Experian
    datacredito: {
      producto: 'Historia de Crédito - DataCrédito Experian',
      fecha_consulta: new Date().toISOString().slice(0, 10),
      documento_consultado: base.cedula || base.documento,
      score: puntaje,
      resumen: {
        obligaciones_vigentes: 3,
        obligaciones_al_dia: 2,
        obligaciones_en_mora: 1,
        mora_max_12m_dias: puntaje < 600 ? 60 : 15,
        cupo_total_aprobado: 45000000,
        utilizacion_pct: 0.34,
        tipo_riesgo: puntaje > 700 ? 'BAJO' : puntaje > 600 ? 'MEDIO' : 'ALTO',
      },
      detalle_obligaciones: [
        {
          tipo: 'Tarjeta Crédito',
          entidad: 'Bancolombia',
          saldo: 2800000,
          mora: 0,
          estado: 'AL DIA',
        },
        {
          tipo: 'Crédito Consumo',
          entidad: 'Banco de Bogotá',
          saldo: 12500000,
          mora: puntaje < 600 ? 30 : 0,
          estado: puntaje < 600 ? 'MORA 30' : 'AL DIA',
        },
      ],
    },
    // JSON 2 - Valida Ingresos Experian
    ingresos: {
      producto: 'Valida Ingresos - DataCrédito Experian',
      fecha_consulta: new Date().toISOString().slice(0, 10),
      documento_consultado: base.cedula || base.documento,
      validacion: {
        ingreso_validado: base.finalIncome || base.declaredIncome || 3500000,
        ingreso_declarado: base.declaredIncome || 3500000,
        confianza: 0.92,
        coincide: true,
        actividad: 'Empleado dependiente',
        antiguedad: '3 años 2 meses',
        empresa: 'Ingenio Manuelita S.A.',
        tipo_contrato: 'Término indefinido',
      },
      fuentes: ['PILA', 'RUNT', 'Registros tributarios'],
    },
  }
}

function seed(): void {
  if (applications.length) return
  applications = MOCK_APPLICATIONS.map((a) => {
    const result = evaluateCreditApplication(a)
    return {
      ...a,
      ...result,
      // normalizamos nombres viejos -> nuevos
      documento: a.documento || a.cedula || '',
      asesor: a.asesor || a.vendedor || '',
      documentos: buildDocumentos(a),
    }
  })
}
seed()

export function listApplications(): RegistroSolicitud[] {
  return [...applications].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )
}

export function getApplication(
  id: string | undefined,
): RegistroSolicitud | undefined {
  return applications.find((a) => a.id === id)
}

export function createApplication(
  payload: SolicitudEvaluable,
): RegistroSolicitud {
  const result = evaluateCreditApplication(payload)
  const id = `SOL-${1000 + applications.length + 1}`
  const base = {
    id,
    createdAt: new Date().toISOString(),
    customer: payload.customer || `Cliente ${id}`,
    cedula: payload.cedula || payload.documento || '',
    documento: payload.documento || payload.cedula || '',
    telefono: payload.telefono || '',
    concesionario: payload.concesionario || 'Pacífico Motors Palmira',
    asesor: payload.asesor || payload.vendedor || '',
    vendedor: payload.asesor || payload.vendedor || '',
    ...payload,
    ...result,
  } as SolicitudMock &
    ResultadoEvaluacion & { cedula: string; vendedor: string }
  const app = {
    ...base,
    documentos: buildDocumentos(base),
  }
  applications.unshift(app)
  return app
}
