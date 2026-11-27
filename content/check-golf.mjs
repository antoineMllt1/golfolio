// Vérifie que les données de golf de content/site.json se recoupent, entre elles et avec la
// géométrie des trous (src/lib/course.js) : node content/check-golf.mjs (ou « npm run check »).
// À relancer dès qu'une distance change : aucune cote ne doit être saisie sans repasser par ici.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dist, makeCourse, measures } from '../src/lib/course.js';

const here = dirname(fileURLToPath(import.meta.url));
const site = JSON.parse(readFileSync(join(here, 'site.json'), 'utf8'));
const course = makeCourse(site);
let bad = 0;
const ok = (cond, text) => {
  if (!cond) bad += 1;
  console.log(`${cond ? '  ok ' : 'FAUX '} ${text}`);
};
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const num = (s) => Number(String(s).replace(',', '.'));

for (const h of course) {
  const data = site.holes[h.n - 1];
  const m = measures(h);
  const stops = site.stops.filter((s) => s.hole === h.n);
  const shots = site.next.slice(h.first, h.first + h.shots.length);
  console.log(`\nTrou ${h.n} : par ${h.par}, ${h.len} m`);

  // --- les coups : portée + roule = total ; la somme fait la longueur du trou
  shots.forEach((s, i) => {
    if (s.carry != null) ok(s.carry + s.roll === s.total, `coup ${i + 1} : portée ${s.carry} + roule ${s.roll} = ${s.total}`);
    ok(near(m.shots[i], s.total, s.total < 10 ? 0.05 : 0.5), `coup ${i + 1} : ${s.total} m sur le plan (mesuré ${m.shots[i].toFixed(2)})`);
    const after = site.stops[h.first + i + 1];
    if (after.hole === h.n) ok(after.golf.toPin === s.leaves, `coup ${i + 1} : reste ${s.leaves} m = distance au drapeau à l'arrêt « ${after.id} »`);
    else ok(s.leaves === 0, `coup ${i + 1} : dans le trou, reste ${s.leaves}`);
    for (const key of ['lands', 'lie']) {
      for (const lang of ['fr', 'en']) {
        const quoted = [...s[key][lang].matchAll(/(\d+(?:[.,]\d+)?)\s*m\b/g)].map((x) => num(x[1]));
        ok(quoted.every((q) => q === s.leaves), `coup ${i + 1} : « ${s[key][lang]} » cite ${quoted.length ? quoted.join(', ') : 'aucune distance'}`);
      }
    }
    ok(s.sync.impact >= 1 && s.sync.impact < s.sync.land && s.sync.land <= 44, `coup ${i + 1} : calage ${s.sync.impact} → ${s.sync.land} sur 44 images`);
  });
  if (h.par > 3) {
    const sum = shots.reduce((a, s) => a + s.total, 0);
    ok(sum === h.len, `${shots.map((s) => s.total).join(' + ')} = ${sum} = longueur du trou`);
  } else {
    ok(shots[0].total === h.len, `par 3 : la mise en jeu fait la longueur du trou (${shots[0].total})`);
    ok(near(dist(h.tee, h.pin), h.len, 0.5), `du départ au drapeau : ${h.len} m (mesuré ${dist(h.tee, h.pin).toFixed(2)})`);
  }

  // --- la distance au drapeau : elle décroît, et le plan dit la même chose
  const toPin = [...stops.map((s) => s.golf.toPin), ...(h.n === site.holes.length ? [] : [0])];
  ok(toPin.every((d, i) => i === 0 || d < toPin[i - 1]), `distance au drapeau décroissante : ${toPin.join(' > ')}`);
  stops.slice(0, h.balls.length - 1).forEach((s, i) => {
    if (i === 0 && h.par > 3) ok(s.golf.toPin === h.len, `« ${s.id} » : ${s.golf.toPin} m, la longueur du trou (dog-leg)`);
    else ok(near(m.balls[i].toPin, s.golf.toPin, s.golf.toPin < 10 ? 0.05 : 0.5), `« ${s.id} » : ${s.golf.toPin} m du drapeau (mesuré ${m.balls[i].toPin.toFixed(2)})`);
  });

  // --- le green et le drapeau du jour
  const pinL = h.local(h.pin);
  ok(near(pinL[0] + h.depth / 2, h.pinOn, 0.5), `drapeau à ${h.pinOn} m de l'entrée (mesuré ${(pinL[0] + h.depth / 2).toFixed(1)})`);
  const half = Math.max(...h.green.map((p) => Math.abs(p[1])));
  ok(near(half - Math.abs(pinL[1]), h.pinSide, 0.6), `drapeau à ${h.pinSide} m du bord ${h.pinRight ? 'droit' : 'gauche'} (mesuré ${(half - Math.abs(pinL[1])).toFixed(1)})`);
  ok((data.pin.from.fr === 'D') === h.pinRight, `le bord annoncé (${data.pin.from.fr}) est le bon`);
  const span = (axis) => Math.max(...h.green.map((p) => p[axis])) - Math.min(...h.green.map((p) => p[axis]));
  ok(near(span(0), h.depth, 0.6) && near(span(1), h.width, 0.6), `green ${h.depth} × ${h.width} m (mesuré ${span(0).toFixed(1)} × ${span(1).toFixed(1)})`);
  ok(data.score === h.shots.length && data.score - h.par === -1, `score ${data.score} : ${h.shots.length} coups, birdie`);

  // --- bunkers, arroseurs, repères
  for (const b of data.bunkers || []) {
    const got = m.bunkers[b.id];
    ok(!!got && got.reach === b.reach && (b.carry == null || got.carry === b.carry), `bunker ${b.id} : ${b.reach}${b.carry ? ` · ${b.carry}` : ''} (mesuré ${got?.reach} · ${got?.carry})`);
  }
  if (data.sprinklers) ok(JSON.stringify(m.sprinklers) === JSON.stringify(data.sprinklers), `arroseurs : ${data.sprinklers.join(', ')} (mesuré ${m.sprinklers.join(', ')})`);
  if (data.marks) {
    const want = [Math.round(m.water), h.len - h.pinOn, h.len, h.len - h.pinOn + h.depth];
    ok(JSON.stringify(data.marks.map((x) => x.m)) === JSON.stringify(want), `repères du départ : ${data.marks.map((x) => `${x.label.fr} ${x.m}`).join(', ')} (mesuré ${want.join(', ')})`);
  }
}

// --- les notes du caddie qui citent une mesure
const golf = (id) => site.stops.find((s) => s.id === id).golf;
const side = (id, i) => num(golf(id).side[i][1]);
const m1 = measures(course[0]);
ok(side('depart', 0) === site.next[0].total, `départ : zone à ${side('depart', 0)} m = total de la mise en jeu`);
ok(side('depart', 1) === m1.bunkers['fairway-gauche'].reach, `départ : bunker de gauche à ${side('depart', 1)} m`);
ok(side('spendmap', 0) === Math.round(m1.balls[1].toFront), `SpendMap : entrée du green à ${side('spendmap', 0)} m (mesuré ${m1.balls[1].toFront.toFixed(1)})`);
ok(side('spendmap', 1) === Math.round(m1.balls[1].toBack), `SpendMap : fond du green à ${side('spendmap', 1)} m (mesuré ${m1.balls[1].toBack.toFixed(1)})`);
ok(side('fnac-darty', 0) + side('fnac-darty', 1) === golf('fnac-darty').toPin, `Fnac Darty : avant-green ${side('fnac-darty', 0)} + green ${side('fnac-darty', 1)} = ${golf('fnac-darty').toPin} m au trou`);
ok(side('revenue-engine', 1) === site.holes[1].marks[0].m, `Revenue Engine : eau à ${side('revenue-engine', 1)} m`);

// --- les distances du joueur, données par lui : bois 3 à 250 m, fer 7 plein à 160 m par temps calme
const PLAYER = { wood3: 250, iron7: 160 };
const cited = (text) => [...String(text).matchAll(/\d+(?:[.,]\d+)?/g)].map((x) => num(x[0]));
ok(site.next[0].total === PLAYER.wood3, `bois 3 : ${site.next[0].total} m au total, sa distance (${PLAYER.wood3})`);
ok(side('revenue-engine', 0) === PLAYER.iron7, `Revenue Engine : joue ${side('revenue-engine', 0)} m, un fer 7 plein (${PLAYER.iron7})`);
for (const lang of ['fr', 'en']) {
  // « Arroseur 215, moins 4 » : l'arroseur existe, et le compte tombe sur l'entrée du green
  const [n, minus] = cited(golf('spendmap').facts[0][1][lang]);
  ok(site.holes[0].sprinklers.includes(n) && n - minus === side('spendmap', 0) && minus <= 5, `SpendMap (${lang}) : arroseur ${n}, moins ${minus} = entrée à ${side('spendmap', 0)} m`);
  // « Porter 198 » : la portée du fer long
  ok(cited(golf('spendmap').say[lang])[0] === site.next[1].carry, `SpendMap (${lang}) : la phrase du caddie cite la portée du fer long (${site.next[1].carry})`);
  // « Poser 4 m après l'entrée » : la portée du wedge, moins l'avant-green
  ok(side('fnac-darty', 0) + cited(golf('fnac-darty').say[lang])[0] === site.next[2].carry, `Fnac Darty (${lang}) : avant-green ${side('fnac-darty', 0)} + ${cited(golf('fnac-darty').say[lang])[0]} m = portée du wedge (${site.next[2].carry})`);
  // « Contre, 12 km/h : + 8 m » : le vent du trou, et ce qu'il ajoute fait la distance jouée
  const [kmh, plus] = cited(golf('revenue-engine').facts[1][1][lang]);
  ok(kmh === site.holes[1].wind.kmh && cited(site.holes[1].wind.label[lang])[0] === kmh, `Revenue Engine (${lang}) : vent de ${kmh} km/h, comme sur la page du trou`);
  ok(golf('revenue-engine').toPin + plus === side('revenue-engine', 0), `Revenue Engine (${lang}) : ${golf('revenue-engine').toPin} + ${plus} = joue ${side('revenue-engine', 0)}`);
  // « Fer 7 plein » : le club de la phrase est celui du coup
  const plain = (text) => text.toLowerCase().replace(/\s+/g, ' '); // les espaces insécables comptent comme des espaces
  ok(plain(golf('revenue-engine').say[lang]).includes(plain(site.next[4].club[lang])), `Revenue Engine (${lang}) : la phrase du caddie nomme le ${site.next[4].club[lang]}`);
}

// --- la carte
const card = golf('contact').card;
const strokes = site.holes.reduce((a, h) => a + h.score, 0);
const par = site.holes.reduce((a, h) => a + h.par, 0);
ok(card.strokes === strokes && card.toPar === strokes - par && site.stops.at(-1).stroke === strokes, `carte : ${strokes} coups, ${strokes - par} par rapport au par ${par}`);

console.log(bad ? `\n${bad} incohérence(s)` : '\nTout se recoupe.');
process.exit(bad ? 1 : 0);
