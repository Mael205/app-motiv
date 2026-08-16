/* Le son, vérifié sans écouter.
 *
 * On ne peut pas entendre un test, mais on peut compter ce qu'il programme.
 * Le contexte audio est remplacé par un espion qui note chaque oscillateur et
 * chaque source de bruit créés : si une séquence n'en programme aucun, elle est
 * muette, et c'est exactement le défaut qu'on ne remarquerait qu'en production.
 *
 * Vérifie aussi les deux règles qui comptent autant que le son lui-même :
 * la coupure fait vraiment taire, et la hiérarchie des raretés s'entend —
 * une légendaire doit programmer plus de voix qu'une commune.
 */
const { chromium } = require('playwright')

const ORIGIN = process.env.ORIGIN || 'http://localhost:5180'

const ESPION = `
window.__voix = []
class FakeParam {
  constructor(){ this.value = 0 }
  setValueAtTime(){ return this } exponentialRampToValueAtTime(){ return this }
  linearRampToValueAtTime(){ return this } setTargetAtTime(){ return this }
}
class FakeNode {
  constructor(){ this.frequency = new FakeParam(); this.Q = new FakeParam(); this.gain = new FakeParam() }
  connect(n){ return n } disconnect(){} start(){} stop(){}
}
class FakeCtx {
  constructor(){ this.currentTime = 0; this.state = 'running'; this.sampleRate = 44100; this.destination = new FakeNode() }
  resume(){ this.state = 'running'; return Promise.resolve() }
  createGain(){ return new FakeNode() }
  createBiquadFilter(){ return new FakeNode() }
  createOscillator(){ window.__voix.push('osc'); return new FakeNode() }
  createBufferSource(){ window.__voix.push('bruit'); return new FakeNode() }
  createBuffer(){ return { getChannelData: () => new Float32Array(64) } }
}
window.AudioContext = FakeCtx
window.webkitAudioContext = FakeCtx
`

;(async () => {
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: 700, height: 760 } })
  await ctx.addInitScript(ESPION)
  const page = await ctx.newPage()
  const resultats = {}

  async function joue(bouton, attente = 2600) {
    await page.goto(`${ORIGIN}/juice.html`, { waitUntil: 'networkidle' })
    await page.evaluate(() => {
      localStorage.setItem('coach.sound', 'on')
      window.__voix = []
    })
    await page.locator(`button:has-text("${bouton}")`).click()
    await page.waitForTimeout(attente)
    return page.evaluate(() => window.__voix.length)
  }

  for (const b of ['Entrée en session', 'Mort du boss', 'Carte Commun', 'Carte Rare', 'Carte Épique', 'Carte Légendaire']) {
    resultats[b] = await joue(b)
  }

  // La coupure doit vraiment couper : aucune voix programmée du tout.
  await page.goto(`${ORIGIN}/juice.html`, { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    localStorage.setItem('coach.sound', 'off')
  })
  await page.goto(`${ORIGIN}/juice.html`, { waitUntil: 'networkidle' })
  await page.evaluate(() => {
    window.__voix = []
  })
  await page.locator('button:has-text("Carte Légendaire")').click()
  await page.waitForTimeout(2600)
  resultats['coupé'] = await page.evaluate(() => window.__voix.length)

  console.log(JSON.stringify(resultats, null, 1))
  await browser.close()
})()
