const { chromium } = require('playwright');
const OUT = process.env.SHOTS;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 300)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 300)));

  await page.goto('http://localhost:5173/juice.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/bench-repos.png` });

  // Ascension : on capture chaque temps de la sequence.
  await page.locator('button:has-text("Ascension")').click();
  for (const [name, wait] of [['niveau', 700], ['branche', 900], ['relique', 900], ['carte', 1400]]) {
    await page.waitForTimeout(wait);
    await page.screenshot({ path: `${OUT}/bench-asc-${name}.png` });
    if (name !== 'carte') await page.locator('.asc').click({ position: { x: 60, y: 60 } });
  }
  await page.keyboard.press('Escape');
  await page.reload({ waitUntil: 'networkidle' });

  // Une legendaire, une commune : verifier que la juice se dose.
  for (const [label, file] of [['Légendaire', 'legendaire'], ['Commun', 'commun']]) {
    await page.locator(`button:has-text("Carte ${label}")`).click();
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/bench-carte-${file}.png` });
    await page.locator('button:has-text("Continuer")').click();
    await page.waitForTimeout(300);
  }

  if (errs.length) console.log('ERREURS:\n' + errs.join('\n'));
  await browser.close();
  console.log('banc capture');
})();
