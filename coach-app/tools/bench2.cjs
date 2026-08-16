const { chromium } = require('playwright');
const OUT = process.env.SHOTS;

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 820 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('PAGEERROR ' + e.message.slice(0, 300)));
  await page.goto('http://localhost:5173/juice.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  await page.locator('button:has-text("Mort du boss")').click();
  await page.waitForTimeout(750);
  await page.screenshot({ path: `${OUT}/b2-boss.png` });
  await page.locator('.asc').click({ position: { x: 60, y: 60 } });
  await page.waitForTimeout(400);

  await page.locator('button:has-text("Entrée en session")').click();
  for (const [ms, nom] of [[180, 'debut'], [520, 'impact'], [900, 'pose']]) {
    await page.waitForTimeout(nom === 'debut' ? ms : 0);
    await page.screenshot({ path: `${OUT}/b2-entry-${nom}.png` });
    if (nom !== 'pose') await page.waitForTimeout(340);
  }

  if (errs.length) console.log('ERREURS:\n' + errs.join('\n'));
  await browser.close();
  console.log('capture');
})();
