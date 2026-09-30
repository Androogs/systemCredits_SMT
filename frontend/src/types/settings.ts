export type SettingsTab =
  | 'profile'
  | 'underwriting'
  | 'integrations'
  | 'commercial'
  | 'users'
  | 'dealers'
  | 'documents'
  | 'notifications'
  | 'audit'
  | 'appearance'
  | 'security'
  | 'backup'
  | 'preferences'

export interface ProfileSettings {
  photoUrl?: string
  fullName: string
  email: string
  phone: string
  role: string
  dealers: string[]
  twoFactorEnabled: boolean
  twoFactorMethod: 'sms' | 'app' | 'email'
}

export interface UnderwritingSettings {
  scoreMinAuto: number
  scoreMinManual: number
  scoreReject: number
  scoreWeight: number
  quantoMin: number
  quantoOptimo: number
  quantoWeight: number
  multiplicador: {
    empleado: number
    pensionado: number
    fuerzas_armadas: number
    independiente: number
  }
  porcentajeGastos: number
  margenCapacidad: number
  tasaMensualCupo: number
  plazoEstandarCupo: number
}

export interface IntegrationSettings {
  datacredito: {
    apiKey: string
    endpoint: string
    env: 'prod' | 'sandbox'
    timeout: number
    retries: number
    checkHistorial: boolean
    checkValidaIngresos: boolean
    costPerQuery: number
  }
}
