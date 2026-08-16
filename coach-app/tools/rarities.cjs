/* Les quatre raretés, prises au même instant relatif de leur séquence.
 *
 * Deux prises par carte : pendant le suspense — le seul moment où l'épique et
 * la légendaire frémissent — et après le retournement. Comparer les quatre
 * côte à côte est la seule façon de vérifier qu'elles se distinguent : chacune
 * prise isolément paraît toujours correcte.
 */
const { chromium } = require('playwright')

const ORIGIN = process.env.ORIGIN || 'http://localhost:5180'
const OUT = process.env.SHOTS

;(async () => {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 640, height: 720 } })
  const page = await ctx.newPage()
  const erreurs = []
  page.on('pageerror', (e) => erreurs.push(String(e).slice(0, 200)))

  for (const rarete of ['Commun', 'Rare', 'Épique', 'Légendaire']) {
    await page.goto(`${ORIGIN}/juice.html`, { waitUntil: 'networkidle' })
    await page.locator(`button:has-text("Carte ${rarete}")`).click()
    // Pendant le suspense : la légendaire attend 1150 ms, la commune 380.
    await page.waitForTimeout(260)
    await page.screenshot({ path: `${OUT}/dos-${rarete}.png` })
    await page.waitForTimeout(1400)
    await page.screenshot({ path: `${OUT}/face-${rarete}.png` })
  }

  console.log(erreurs.length ? 'ERREURS ' + erreurs.join(' | ') : 'captures faites')
  await browser.close()
})()
