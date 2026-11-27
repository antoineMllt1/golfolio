// Vérification du film dans le site : joue les six coups (Flèche bas) sur un écran 1440 × 900 et sur un
// téléphone 390 × 844, capture deux images en plein vol et l'arrivée de chaque coup, compte les erreurs de console.
//   npm run build && PORT=3004 node server/index.js &
//   node render/verif/jouer.mjs http://localhost:3004 render/out/site/animatique
//   python render/verif/planches_site.py render/out/site/animatique      # les planches
import { createRequire } from 'node:module';
import fs from 'node:fs';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const [base, out] = process.argv.slice(2);
fs.mkdirSync(out, { recursive: true });
const DEVICES = [
  { name: 'ordi', viewport: { width: 1440, height: 900 } },
  { name: 'tel', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
];
const browser = await chromium.launch();
let errors = 0;
for (const d of DEVICES) {
  const { name, ...opts } = d;
  const ctx = await browser.newContext({ locale: 'fr-FR', ...opts });
  const page = await ctx.newPage();
  page.on('console', (m) => { if (m.type() === 'error') { errors++; console.log(`[${name}] console:`, m.text()); } });
  page.on('pageerror', (e) => { errors++; console.log(`[${name}] erreur:`, e.message); });
  page.on('requestfailed', (r) => console.log(`[${name}] requête échouée:`, r.url()));
  page.on('response', (r) => { if (r.status() >= 400) console.log(`[${name}] ${r.status()}`, r.url()); });
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForSelector('.app.ready', { state: 'attached', timeout: 30000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/${name}-0-arret.png` });
  for (let k = 1; k <= 6; k++) {
    await page.keyboard.press('ArrowDown');
    const t0 = Date.now();
    const moved = await page.waitForSelector('.app.moving', { state: 'attached', timeout: 3000 }).then(() => true, () => false);
    await page.waitForTimeout(Math.max(0, 620 - (Date.now() - t0)));
    await page.screenshot({ path: `${out}/${name}-${k}-vol-a.png` });
    const ta = Date.now() - t0;
    await page.waitForTimeout(Math.max(0, 1120 - (Date.now() - t0)));
    await page.screenshot({ path: `${out}/${name}-${k}-vol-b.png` });
    const tb = Date.now() - t0;
    await page.waitForSelector('.app:not(.moving)', { state: 'attached', timeout: 15000 });
    const tc = Date.now() - t0;
    await page.waitForTimeout(1400);
    await page.screenshot({ path: `${out}/${name}-${k}-arret.png` });
    console.log(`[${name}] coup ${k} : en mouvement ${moved}, captures à ${ta} et ${tb} ms, arrivée à ${tc} ms, ${page.url()}`);
  }
  await ctx.close();
}
await browser.close();
console.log(`erreurs de console : ${errors}`);
process.exit(errors ? 1 : 0);
