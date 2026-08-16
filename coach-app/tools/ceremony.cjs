const { chromium } = require('playwright');
const OUT = process.env.SHOTS;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 900 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 300)); });
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 300)));

  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
  if (await page.locator('input[type=password]').count()) {
    await page.locator('input').first().fill('demo');
    await page.locator('input[type=password]').fill('demo');
    await page.locator('button[type=submit], .cta').first().click();
  }
  await page.waitForTimeout(3500);

  const noms = ['score', 'fantome', 'titre', 'carte', 'ouverture'];
  for (const nom of noms) {
    await page.screenshot({ path: `${OUT}/cer-${nom}.png` });
    const suite = page.locator('.cer__hint');
    if (await suite.count()) await page.locator('.cer').click({ position: { x: 60, y: 60 } });
    else {
      const cont = page.locator('button:has-text("Continuer")');
      if (await cont.count()) await cont.click();
    }
    await page.waitForTimeout(1600);
  }
  await page.screenshot({ path: `${OUT}/cer-final.png`, fullPage: true });

  if (errs.length) console.log('ERREURS:\n' + errs.join('\n'));
  await browser.close();
  console.log('ceremonie capturee');
})();
