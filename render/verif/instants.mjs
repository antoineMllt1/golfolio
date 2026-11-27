// Captures du site à des images précises du film : l'horloge de la page est tenue par Playwright,
// la capture tombe donc sur l'image demandée, pas « à peu près pendant le vol ».
//   node render/verif/instants.mjs <base> <dossier> <nom> <largeur> <hauteur> [tel] [images]
//   images : « 0:14,18,24;4:16,20 » (trajet : images) ; par défaut quelques images de chaque trajet.
// Exemple : node render/verif/instants.mjs http://localhost:3010 /tmp/x tel 390 844 tel "0:13,18,24,27,33"
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const [base, out, name, w, h, tel, spec] = process.argv.slice(2);
if (!base || !out || !name || !w || !h) {
  console.error('usage : node render/verif/instants.mjs <base> <dossier> <nom> <largeur> <hauteur> [tel|-] [images]');
  process.exit(2);
}
fs.mkdirSync(out, { recursive: true });
let want = [[14, 18, 24, 31, 37], [16, 19, 31], [13, 20, 38], [15, 19, 26, 30, 36], [16, 20, 28, 33], [11, 22, 30]];
if (spec) {
  want = [[], [], [], [], [], []];
  for (const part of spec.split(';')) {
    const [k, list] = part.split(':');
    want[+k] = list.split(',').map(Number).sort((a, b) => a - b);
  }
}
const lastLeg = want.reduce((m, l, k) => (l.length ? k : m), 0);
const browser = await chromium.launch();
const opts = { locale: 'fr-FR', viewport: { width: +w, height: +h } };
if (tel === 'tel') Object.assign(opts, { isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
const ctx = await browser.newContext(opts);
const page = await ctx.newPage();
let errors = 0;
page.on('console', (m) => {
  if (m.type() === 'error') errors += 1;
});
page.on('pageerror', () => {
  errors += 1;
});
await page.clock.install();
await page.goto(base, { waitUntil: 'networkidle' });
await page.waitForSelector('.app.ready', { state: 'attached', timeout: 30000 });
await page.waitForTimeout(2500);
await page.clock.pauseAt(new Date(Date.now() + 1000));
await page.clock.runFor(500);
for (let k = 0; k <= lastLeg; k++) {
  await page.keyboard.press('ArrowDown');
  await page.clock.runFor(20);
  let f = 0.5; // image courante du film (le départ suit la touche d'une image d'écran)
  for (const n of want[k]) {
    await page.clock.runFor(Math.round(((n - f) * 1000) / 27));
    f = n;
    await page.waitForTimeout(250); // le temps de décoder l'image demandée
    await page.clock.runFor(1);
    await page.screenshot({ path: `${out}/${name}-l${k}-${String(n).padStart(2, '0')}.png` });
  }
  await page.clock.runFor(1200);
  await page.waitForTimeout(400);
  await page.clock.runFor(2500);
  await page.waitForTimeout(300);
  await page.clock.runFor(100);
  await page.screenshot({ path: `${out}/${name}-${k + 1}-arret.png` });
}
console.log(`${name} : erreurs de console : ${errors}`);
await browser.close();
