/* Audit visuel : chevauchements, animations mortes, débordements.
 *
 * Les captures montrent ce qui est laid ; ce script montre ce qui est *cassé*
 * sans forcément se voir — une animation dont le `playState` est `idle`, une
 * boîte qui en recouvre une autre de trente pixels, un bloc plus large que le
 * viewport. Trois défauts qu'on regarde sans les voir.
 *
 *   ORIGIN=http://localhost:5180 SHOTS=/sortie node tools/audit.cjs
 */
const { chromium } = require('playwright')
const fs = require('fs')

const ORIGIN = process.env.ORIGIN || 'http://localhost:5173'
const OUT = process.env.SHOTS
const TABS = (process.env.TABS || 'Ce soir,Projets,Personnage,Journal').split(',')

;(async () => {
  const browser = await chromium.launch()
  const sizes = { desktop: [1440, 900], laptop: [1280, 800], phone: [390, 844] }
  const rapport = []

  for (const [nom, [w, h]] of Object.entries(sizes)) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 })
    const page = await ctx.newPage()
    const erreurs = []
    page.on('console', (m) => {
      if (m.type() === 'error') erreurs.push(m.text().slice(0, 300))
    })
    page.on('pageerror', (e) => erreurs.push('PAGEERROR ' + String(e).slice(0, 300)))

    await page.goto(ORIGIN, { waitUntil: 'networkidle' })
    if (await page.locator('input[type=password]').count()) {
      await page.locator('input').first().fill(process.env.USER_NAME || 'demo')
      await page.locator('input[type=password]').fill(process.env.USER_PASS || 'demo')
      await page.locator('button[type=submit], .cta').first().click()
      await page.waitForTimeout(2500)
    }
    await page.waitForTimeout(1200)

    for (const tab of TABS) {
      // Le tirage de cartes couvre l'ecran et bloque la barre d'onglets : on le
      // vide avant de naviguer, sinon le clic sur l'onglet suivant expire.
      for (let n = 0; n < 12; n++) {
        const suivant = page.locator('.loot__next')
        if (!(await suivant.count())) break
        await suivant.click()
        await page.waitForTimeout(400)
      }

      const btn = page.locator(`button:has-text("${tab}")`).last()
      if (await btn.count()) {
        await btn.click()
        await page.waitForTimeout(1000)
      }
      if (OUT) await page.screenshot({ path: `${OUT}/${nom}-${tab}.png`, fullPage: true })

      const trouve = await page.evaluate(() => {
        const out = { overflow: [], overlap: [], animations: [], invisible: [], layout: [] }

        // 1. Debordement horizontal : rien ne doit depasser le viewport.
        //
        // Un element clippe par un ancetre en `overflow: hidden` ne deborde
        // pas, meme si sa boite le dit : c'est le cas de tout ce qui se
        // deplace par `transform` a l'interieur d'une piste. Sans ce filtre le
        // rapport se remplit de faux positifs qu'on reapprend a ignorer a
        // chaque passage — et une sonde qu'on ignore ne sert plus a rien.
        const clippe = (el) => {
          for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
            const o = getComputedStyle(p)
            if (o.overflowX === 'hidden' || o.overflowX === 'clip' || o.overflow === 'hidden') return true
          }
          return false
        }

        const vw = document.documentElement.clientWidth
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect()
          if (r.width === 0 || r.height === 0) continue
          if (clippe(el)) continue
          if (r.right > vw + 1 || r.left < -1) {
            out.overflow.push({
              sel: el.className && typeof el.className === 'string' ? el.className.slice(0, 60) : el.tagName,
              left: Math.round(r.left),
              right: Math.round(r.right),
              vw,
            })
          }
        }

        // 2. Chevauchement entre elements frères qui ne devraient pas se toucher.
        const blocs = [...document.querySelectorAll('.panel, section, aside > *, .deck__main > *')]
        for (let i = 0; i < blocs.length; i++) {
          for (let j = i + 1; j < blocs.length; j++) {
            const a = blocs[i]
            const b = blocs[j]
            if (a.contains(b) || b.contains(a)) continue
            const ra = a.getBoundingClientRect()
            const rb = b.getBoundingClientRect()
            if (!ra.width || !rb.width) continue
            const ox = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)
            const oy = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top)
            if (ox > 4 && oy > 4) {
              out.overlap.push({
                a: String(a.className).slice(0, 40),
                b: String(b.className).slice(0, 40),
                ox: Math.round(ox),
                oy: Math.round(oy),
              })
            }
          }
        }

        // 3. Animations : celles qui existent, et leur etat reel.
        //
        // Une animation sur `width`, `left`, `top` ou `height` recalcule la
        // mise en page a chaque image. Sur un ecran qu'on laisse ouvert toute
        // la soiree — la jauge du soir se redessine chaque seconde — c'est un
        // cout permanent que rien ne signale : l'ecran a l'air normal.
        const LAYOUT = ['width', 'height', 'top', 'left', 'margin-left', 'margin-top']
        for (const anim of document.getAnimations()) {
          const cible = anim.effect && anim.effect.target
          const cls = cible ? String(cible.className.baseVal ?? cible.className).slice(0, 40) : '?'
          const prop = anim.transitionProperty
          if (prop && LAYOUT.includes(prop)) {
            out.layout.push({ prop, cls, state: anim.playState })
          }
          out.animations.push({
            name: anim.animationName || (prop ?? '?'),
            state: anim.playState,
            cls,
          })
        }

        // 4. Elements a taille nulle alors qu'ils portent du contenu.
        for (const el of document.querySelectorAll('svg, .rankbadge__wing, .rankbadge__feather')) {
          const r = el.getBoundingClientRect()
          if (r.width < 2 || r.height < 2) {
            out.invisible.push({ sel: String(el.className.baseVal ?? el.className).slice(0, 40), w: r.width, h: r.height })
          }
        }
        return out
      })

      rapport.push({ taille: nom, tab, ...trouve })
    }

    if (erreurs.length) rapport.push({ taille: nom, tab: '-', console: erreurs })
    await ctx.close()
  }

  await browser.close()
  const texte = JSON.stringify(rapport, null, 1)
  if (OUT) fs.writeFileSync(`${OUT}/audit.json`, texte)
  console.log(texte.slice(0, 12000))
})()
