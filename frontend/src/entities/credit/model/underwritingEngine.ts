export const EmploymentType = {
  EMPLOYEE: 'empleado',
  PENSIONER: 'pensionado',
  FORCES: 'fuerzas',
  INDEPENDENT: 'independiente',
} as const

export type EmploymentType =
  (typeof EmploymentType)[keyof typeof EmploymentType]
export type EstadoSolicitud =
  'APROBADO' | 'RECHAZADO' | 'REQUIERE_REVISION' | 'PENDIENTE'

export const EMPLOYMENT_LABELS: Record<EmploymentType, string> = {
  empleado: 'Empleado',
  pensionado: 'Pensionado',
  fuerzas: 'Fuerzas Armadas',
  independiente: 'Independiente',
}

const MULTIPLIERS: Record<EmploymentType, number> = {
  empleado: 1.2,
  pensionado: 1.2,
  fuerzas: 1.2,
  independiente: 1.4,
}

export interface SolicitudEvaluable {
  declaredIncome: number
  employmentType: EmploymentType
  creditScore: number
  quantoFactor: number
  requestedInstallment: number
  revolvingExpenses?: number
  nonRevolvingExpenses?: number
  personalExpensesPct?: number
  paymentCapacityMargin?: number
  monthlyRatePct?: number
  termMonths?: number
  customer?: string
  cedula?: string
  documento?: string
  telefono?: string
  concesionario?: string
  asesor?: string
  vendedor?: string
}

export interface ReglaEvaluacion {
  code: string
  label: string
  passed: boolean
}

export interface ResultadoEvaluacion {
  status: EstadoSolicitud
  creditScore: number
  quantoFactor: number
  finalIncome: number
  personalExpenses: number
  revolvingExpenses: number
  nonRevolvingExpenses: number
  totalExpenses: number
  availableIncome: number
  suggestedQuota: number
  suggestedCreditLimit: number
  requestedInstallment: number
  rejectionReasons: string[]
  rules: ReglaEvaluacion[]
}

const round2 = (n: number) => Math.round(n * 100) / 100

export function evaluateCreditApplication({
  declaredIncome,
  employmentType,
  creditScore,
  quantoFactor,
  requestedInstallment,
  revolvingExpenses = 0,
  nonRevolvingExpenses = 0,
  personalExpensesPct = 0.5,
  paymentCapacityMargin = 0.7,
  monthlyRatePct = 2.0,
  termMonths = 48,
}: SolicitudEvaluable): ResultadoEvaluacion {
  const multiplier = MULTIPLIERS[employmentType] ?? 1.0
  const finalIncome = round2(declaredIncome * multiplier)

  const personalExpenses = round2(finalIncome * personalExpensesPct)
  const totalExpenses = round2(
    personalExpenses + revolvingExpenses + nonRevolvingExpenses,
  )
  const availableIncome = round2(finalIncome - totalExpenses)
  const maxAvailable = Math.max(0, availableIncome)
  const suggestedQuota = round2(maxAvailable * paymentCapacityMargin)

  let suggestedCreditLimit = 0
  if (suggestedQuota > 0 && termMonths > 0) {
    const rate = monthlyRatePct / 100
    const factor = Math.pow(1 + rate, termMonths)
    suggestedCreditLimit = round2(
      suggestedQuota * ((factor - 1) / (rate * factor)),
    )
  }

  const isScoreValid = creditScore >= 600
  const isQuantoValid = quantoFactor >= 1.0
  const isCapacityValid = requestedInstallment <= suggestedQuota

  const rejectionReasons: string[] = []
  if (!isScoreValid)
    rejectionReasons.push(`Score insuficiente (${creditScore} < 600).`)
  if (!isQuantoValid)
    rejectionReasons.push(
      `Factor Quanto por debajo del mínimo (${quantoFactor} < 1.00).`,
    )
  if (!isCapacityValid)
    rejectionReasons.push(
      `Cuota solicitada supera la capacidad de pago (${requestedInstallment.toLocaleString()} > ${suggestedQuota.toLocaleString()}).`,
    )

  let status: EstadoSolicitud = 'APROBADO'
  if (rejectionReasons.length > 0) {
    status = !isScoreValid || !isQuantoValid ? 'RECHAZADO' : 'REQUIERE_REVISION'
  }

  return {
    status,
    creditScore,
    quantoFactor,
    finalIncome,
    personalExpenses,
    revolvingExpenses,
    nonRevolvingExpenses,
    totalExpenses,
    availableIncome,
    suggestedQuota,
    suggestedCreditLimit,
    requestedInstallment,
    rejectionReasons,
    rules: [
      { code: 'SCORE_MIN', label: 'Score ≥ 600', passed: isScoreValid },
      { code: 'QUANTO_MIN', label: 'Quanto ≥ 1.00', passed: isQuantoValid },
      {
        code: 'CAPACITY',
        label: 'Cuota ≤ capacidad de pago',
        passed: isCapacityValid,
      },
    ],
  }
}
