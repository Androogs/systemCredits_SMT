export default async function run(page, ui) {
  await page.locator('#login-username').fill('admin@sumoto.com.co')
  await page.locator('#login-password').fill('Admin123!')
  await page.getByRole('button', { name: /ingresar|entrar|acceder/i }).click()

  await page.waitForURL(/dashboard/, { timeout: 15000 })
  await page.waitForSelector('text=Causales de rechazo', { timeout: 20000 })
  await page.waitForTimeout(2500)

  // Hover sobre la segunda barra (R18, la más alta junto a R21)
  const columnas = page.locator('.group.relative.flex.h-full')
  const n = await columnas.count()
  // hover en una del medio para probar el centrado
  const medio = columnas.nth(Math.floor(n / 2))
  await medio.scrollIntoViewIfNeeded()
  await medio.hover()
  await page.waitForTimeout(400)

  const visible = await page.evaluate(() => {
    const tips = [...document.querySelectorAll('.group > .pointer-events-none')]
    const v = tips.filter((t) => getComputedStyle(t).display !== 'none')
    return {
      tooltipsVisibles: v.length,
      texto: v[0]?.innerText?.replace(/\n/g, ' | '),
    }
  })

  // Y una del borde derecho para probar el anclaje
  await columnas.nth(n - 1).hover()
  await page.waitForTimeout(400)
  const bordeDer = await page.evaluate(() => {
    const tips = [...document.querySelectorAll('.group > .pointer-events-none')]
    const v = tips.filter((t) => getComputedStyle(t).display !== 'none')
    if (!v.length) return { visible: 0 }
    const r = v[0].getBoundingClientRect()
    const card = v[0].closest('.card')?.getBoundingClientRect()
    return {
      visible: v.length,
      texto: v[0]?.innerText?.replace(/\n/g, ' | '),
      dentroDeCard: card ? r.right <= card.right + 1 && r.left >= card.left - 1 : null,
    }
  })

  return { columnas: n, visible, bordeDer }
}
