import { expect, request, test } from '@playwright/test'

/**
 * E2E: radica una solicitud vía API, la evalúa con el escenario mock
 * "aprobado" y verifica que la UI (React) refleja el resultado real
 * persistido en la base — lista, detalle, oferta y pantalla de resultado.
 */
const API = 'http://localhost:8010'
const CEDULA = '1000000001'

let idSolicitud: string
let token: string
let usuarioSesion: unknown

test.beforeAll(async () => {
  const api = await request.newContext({ baseURL: API })

  // Sesión real: el seed crea admin@pacifico.co (ve todo el panel).
  const login = await api.post('/api/auth/login', {
    data: { correo: 'admin@pacifico.co', contrasena: 'Admin123!' },
  })
  expect(login.status(), await login.text()).toBe(200)
  const sesion = await login.json()
  token = sesion.access_token
  usuarioSesion = sesion.usuario
  const autenticado = await request.newContext({
    baseURL: API,
    extraHTTPHeaders: { Authorization: `Bearer ${token}` },
  })

  const crear = await autenticado.post('/api/solicitudes', {
    data: {
      cliente: {
        tipo_documento: '1',
        num_cedula: CEDULA,
        nombre_completo: 'Cliente E2E Playwright',
        primer_apellido: 'Playwright',
        fecha_nacimiento: '1990-05-15',
        ocupacion: 'Empleado',
      },
      datos_laborales: {
        tipo_contrato: 'Indefinido',
        ingreso_mensual: 5_000_000,
      },
      plazo_deseado_meses: 36,
    },
  })
  expect(crear.status(), await crear.text()).toBe(201)
  idSolicitud = (await crear.json()).id_solicitud

  const evaluar = await autenticado.post(
    `/api/solicitudes/${idSolicitud}/evaluar`,
    {
      data: {
        saldo_financiar: 5_000_000,
        plazo: 36,
        tasa: 2,
        consultar_experian: false,
        escenario_mock: 'aprobado',
      },
    },
  )
  expect(evaluar.ok(), await evaluar.text()).toBeTruthy()
})

test.beforeEach(async ({ page }) => {
  // Sesión del panel: token JWT + usuario devueltos por el login real.
  await page.addInitScript(
    ([t, u]) => {
      window.localStorage.setItem('uw_token', t as string)
      window.localStorage.setItem('uw_usuario', JSON.stringify(u))
    },
    [token, usuarioSesion] as const,
  )
})

// La columna N° muestra num_solicitud o el prefijo del id — sirve de ancla
// porque la BD de E2E acumula semillas de corridas anteriores.
const filaSembrada = (page: import('@playwright/test').Page) =>
  page.getByRole('row', { name: new RegExp(idSolicitud.slice(0, 8)) })

test('la lista muestra la solicitud evaluada con su insignia', async ({
  page,
}) => {
  await page.goto('/solicitudes')
  const fila = filaSembrada(page)
  await expect(fila).toBeVisible()
  await expect(fila.getByText('Cliente E2E Playwright')).toBeVisible()
  await expect(fila.getByText(/Aprobado/i)).toBeVisible()
})

test('el detalle muestra la evaluación y la oferta elegible', async ({
  page,
}) => {
  await page.goto(`/solicitudes/${idSolicitud}`)
  await expect(
    page.getByText('Cliente E2E Playwright', { exact: true }),
  ).toBeVisible()
  // La evaluación vive en su pestaña; las ofertas en Gestión.
  await page.getByRole('tab', { name: 'Evaluación' }).click()
  await expect(page.getByText('Evaluación del motor')).toBeVisible()
  await page.getByRole('tab', { name: 'Gestión' }).click()
  await expect(
    page.getByRole('heading', { name: 'Oferta elegible' }),
  ).toBeVisible()
  await expect(
    page.getByRole('heading', { name: 'Seleccionar oferta' }),
  ).toBeVisible()
})

test('la pantalla de resultado muestra la decisión aprobada', async ({
  page,
}) => {
  await page.goto(`/solicitudes/${idSolicitud}/resultado`)
  await expect(
    page.getByRole('heading', { name: /Solicitud aprobada/i }),
  ).toBeVisible()
  await expect(page.getByText('Condiciones aprobadas')).toBeVisible()
})

test('el resumen carga KPIs con datos reales', async ({ page }) => {
  await page.goto('/dashboard')
  // Banda KPI: cada celda es un botón de filtro; el lateral usa enlaces.
  await expect(page.getByRole('button', { name: /Solicitudes/ })).toBeVisible()
  await expect(filaSembrada(page)).toBeVisible()
})

test('el admin ve los filtros dimensionales y /asesor redirige al panel', async ({
  page,
}) => {
  await page.goto('/dashboard')
  await expect(page.getByLabel('Filtrar por concesionario')).toBeVisible()
  await expect(page.getByLabel('Filtrar por asesor')).toBeVisible()
  await page.goto('/asesor')
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByLabel('Filtrar por concesionario')).toBeVisible()
})

test('el asesor ve acciones rápidas y su tabla completa, sin filtros de admin', async ({
  page,
}) => {
  const api = await request.newContext({ baseURL: API })
  const login = await api.post('/api/auth/login', {
    data: { correo: 'asesor@pacifico.co', contrasena: 'Asesor123!' },
  })
  expect(login.status(), await login.text()).toBe(200)
  const sesion = await login.json()
  await page.addInitScript(
    ([t, u]) => {
      window.localStorage.setItem('uw_token', t as string)
      window.localStorage.setItem('uw_usuario', JSON.stringify(u))
    },
    [sesion.access_token, sesion.usuario] as const,
  )
  await page.goto('/dashboard')
  await expect(
    page.getByRole('heading', { name: 'Acciones rápidas' }),
  ).toBeVisible()
  await expect(page.getByLabel('Filtrar por concesionario')).not.toBeVisible()
  // La tabla del asesor trae pendientes primero (orden del servidor) y
  // es la tabla completa paginada, no la cola corta — el encabezado
  // cuenta los resultados del alcance aunque la página inicial esté vacía.
  await expect(
    page.getByRole('region', { name: 'Tabla de solicitudes' }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: /Solicitudes/ })).toBeVisible()
})
