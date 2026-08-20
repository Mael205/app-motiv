/* La seule mesure qui décide de l'accueil : le bouton de démarrage est-il
 * visible sans faire défiler, et sans passer sous la barre d'onglets ?
 *
 * Le §11.1 veut une décision qui domine l'écran. Sur téléphone, « dominer »
 * commence par « être là quand on ouvre l'app ». C'est un défaut qui s'est déjà
 * produit deux fois et qu'aucun test ni `tsc` ne voit.
 */
const { chromium } = require('playwright')
const { verdictFold, conclure } = require('./verdict.cjs')

const ORIGIN = process.env.ORIGIN || 'http://localhost:5173'

;(async () => {
  const browser = await chromium.launch()
  const resultats = []

  for (const [nom, w, h] of [
    ['phone', 390, 844],
    ['petit', 360, 740],
    ['laptop', 1280, 800],
  ]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h } })
    const page = await ctx.newPage()
    await page.goto(ORIGIN, { waitUntil: 'networkidle' })
    if (await page.locator('input[type=password]').count()) {
      await page.locator('input').first().fill('demo')
      await page.locator('input[type=password]').fill('demo')
      await page.locator('button[type=submit], .cta').first().click()
      await page.waitForTimeout(2500)
    }
    for (let n = 0; n < 12; n++) {
      const s = page.locator('.loot__next')
      if (!(await s.count())) break
      await s.click()
      await page.waitForTimeout(300)
    }
    await page.waitForTimeout(1000)

    const m = await page.evaluate(() => {
      const cta = document.querySelector('.cta--main')
      const bar = document.querySelector('.tabbar')
      if (!cta) return { absent: true }
      const c = cta.getBoundingClientRect()
      const b = bar ? bar.getBoundingClientRect() : null
      // Le plafond utile : le haut de la barre d'onglets si elle est en bas,
      // sinon le bas du viewport.
      const barEnBas = b && b.top > window.innerHeight / 2
      const plafond = barEnBas ? b.top : window.innerHeight
      return {
        ctaTop: Math.round(c.top),
        ctaBottom: Math.round(c.bottom),
        plafond: Math.round(plafond),
        visible: c.bottom <= plafond,
        marge: Math.round(plafond - c.bottom),
      }
    })
    resultats.push({ taille: nom, ...m })
    await ctx.close()
  }

  await browser.close()
  console.log(JSON.stringify(resultats, null, 1))

  // Le verdict. La mesure existait depuis le debut, mais elle sortait en 0 meme
  // quand le bouton passait sous la ligne — c'est-a-dire exactement dans le cas
  // que cet outil a ete ecrit pour attraper, et qui s'est deja produit deux fois.
  conclure(verdictFold(resultats))
})()
