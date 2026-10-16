export const currency = (n: number | null | undefined) =>
  new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(n || 0)

export const number = (n: number | null | undefined) =>
  new Intl.NumberFormat('es-CO').format(n || 0)

export const dateShort = (iso: string | Date) =>
  new Date(iso).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

export const dateTime = (iso: string | Date) =>
  `${dateShort(iso)} ${new Date(iso).toLocaleTimeString('es-CO', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })}`
