const { chromium } = require('playwright');
const fs = require('fs');
const OUT = process.env.SHOTS;

(async () => {
  const browser = await chromium.launch();
  const sizes = { desktop: [1440, 900], laptop: [1280, 800], phone: [390, 844] };
  const tabs = process.env.TABS ? process.env.TABS.split(',') : ['Accueil'];

  for (const [name, [w, h]] of Object.entries(sizes)) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const errs = [];
    page.on('console', m => { if (m.type() === 'error') errs.push(m.text().slice(0, 200)); });
    await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });

    // Connexion si l'ecran de boot est la
    if (await page.locator('input[type=password]').count()) {
      await page.locator('input').first().fill(process.env.USER_NAME || 'arthur');
      await page.locator('input[type=password]').fill(process.env.USER_PASS || 'coach');
      await page.locator('button[type=submit], .cta').first().click();
      await page.waitForTimeout(2500);
    }
    await page.waitForTimeout(1200);

    for (const tab of tabs) {
      const btn = page.locator(`button:has-text("${tab}"), a:has-text("${tab}")`).last();
      if (await btn.count()) { await btn.click(); await page.waitForTimeout(900); }

      // Derouler avant de capturer. Les cartes n'entrent qu'une fois atteintes
      // par le defilement (`revelerAuDefilement`) : une capture pleine page
      // prise sans avoir descendu montre des blancs a la place de tout ce qui
      // etait sous la ligne de flottaison, et la capture ment.
      await page.evaluate(async () => {
        const pas = window.innerHeight * 0.8;
        for (let y = 0; y < document.body.scrollHeight; y += pas) {
          window.scrollTo(0, y);
          await new Promise((r) => setTimeout(r, 260));
        }
        window.scrollTo(0, 0);
      });
      await page.waitForTimeout(1400);

      await page.screenshot({ path: `${OUT}/${name}-${tab}.png`, fullPage: true });
    }
    if (errs.length) fs.appendFileSync(`${OUT}/errors.txt`, `\n[${name}]\n` + errs.join('\n'));
    await ctx.close();
  }
  await browser.close();
  console.log('captures faites');
})();
