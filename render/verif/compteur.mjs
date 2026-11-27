// Le compteur de distance du traceur part-il à l'impact et finit-il quand la balle touche le sol ?
//   node render/verif/compteur.mjs http://localhost:3004      (le site construit et servi, voir jouer.mjs)
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const base = process.argv[2];
const browser = await chromium.launch();
const ctx = await browser.newContext({ locale: 'fr-FR', viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();
await page.goto(base, { waitUntil: 'networkidle' });
await page.waitForSelector('.app.ready', { state: 'attached' });
await page.waitForTimeout(1500);
const manifest = await page.evaluate(() => fetch('/frames/manifest.json').then((r) => r.json()));
const num = (s) => Number(String(s || '').replace(',', '.').replace(/[^\d.]/g, '') || 0);
for (let k = 0; k < manifest.legs.length; k++) {
  await page.evaluate(() => {
    window.__rec = [];
    window.__on = true;
    const tick = () => {
      const el = document.querySelector('.trace .big');
      window.__rec.push([performance.now(), document.querySelector('.app').classList.contains('moving'), el ? el.textContent : '']);
      if (window.__on) requestAnimationFrame(tick);
    };
    tick();
  });
  await page.keyboard.press('ArrowDown');
  await page.waitForSelector('.app.moving', { state: 'attached', timeout: 3000 });
  await page.waitForSelector('.app:not(.moving)', { state: 'attached', timeout: 15000 });
  const rec = await page.evaluate(() => { window.__on = false; return window.__rec; });
  const t0 = rec.find((r) => r[1])[0];
  const fly = rec.filter((r) => r[1]);
  const values = fly.map((r) => num(r[2]));
  const max = Math.max(...values);
  const first = fly.find((r) => num(r[2]) > 0);
  const carry = [240, 198, 6, 3, 150, 1.5][k]; // la portée qu'affiche le traceur pour ce coup (un putt : sa longueur)
  const last = fly.find((r) => num(r[2]) >= carry);
  const frame = (t) => ((t - t0) * manifest.fps / 1000 + 1).toFixed(1);
  const leg = manifest.legs[k];
  if (k === 3 || k === 5) {
    // Un putt : le compteur décompte ce qui reste jusqu'au trou, puis annonce le birdie.
    const start = num(fly[0][2]);
    const moves = fly.find((r) => /\d/.test(r[2]) && num(r[2]) < start);
    const holed = fly.find((r) => !/\d/.test(r[2]) || num(r[2]) === 0);
    console.log(`coup ${k + 1} (putt) : le compteur part de ${start} m, décompte à partir de l'image ${moves ? frame(moves[0]) : '?'} (impact ${leg.impact}), tombe à zéro (« ${holed ? holed[2].trim() : '?'} ») à l'image ${holed ? frame(holed[0]) : '?'} (dans le trou ${leg.land}), trajet de ${(fly[fly.length - 1][0] - t0).toFixed(0)} ms`);
    await page.waitForTimeout(1200);
    continue;
  }
  console.log(`coup ${k + 1} : le compteur quitte 0 à l'image ${first ? frame(first[0]) : '?'} (impact ${leg.impact}), atteint la portée (${carry} m, total ${max} m) à l'image ${last ? frame(last[0]) : '?'} (sol ${leg.land}), trajet de ${(fly[fly.length - 1][0] - t0).toFixed(0)} ms`);
  await page.waitForTimeout(1200);
}
await browser.close();
