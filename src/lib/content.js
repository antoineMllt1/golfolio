// Tout le texte du site vient de content/site.json (français et anglais) : rien n'est écrit ici.
import site from '../../content/site.json';
import { makeCourse } from './course.js';

export const SITE = site;
export const STOPS = site.stops;
export const LAST = STOPS.length - 1;
export const HOLES = site.holes;
export const NEXT = site.next;
export const TOTAL_STROKES = STOPS[LAST].stroke;
// Les arrêts qui ouvrent un projet, dans l'ordre du parcours.
export const PROJECTS = STOPS.filter((s) => s.kind === 'project');
// La géométrie des deux trous (course.js), mariée aux données du site : COURSE[0] est le trou 1.
export const COURSE = makeCourse(site);

// { fr, en } → la bonne langue ; une chaîne simple passe telle quelle.
export const pick = (v, lang) => (v && typeof v === 'object' ? (v[lang] ?? v.fr ?? '') : (v ?? ''));

export const indexOfId = (id) => STOPS.findIndex((s) => s.id === id);
export const holeOf = (stop) => HOLES.find((h) => h.n === stop.hole) || HOLES[0];

// Coups joués sur chaque trou, d'après le champ « stroke » des arrêts : [4, 2].
export const STROKES_BY_HOLE = HOLES.map((h) => {
  const first = STOPS.find((s) => s.hole === h.n);
  const after = STOPS.find((s) => s.hole > h.n);
  return (after ? after.stroke : TOTAL_STROKES) - first.stroke;
});

// Le nom affiché d'un arrêt : le projet, ou le titre de l'accueil et du contact.
export const stopName = (stop, lang, t) => (stop.kind === 'project' ? stop.name : stop.kind === 'contact' ? t.contact : t.tee);
// Le même en court, là où la place manque (points du plan, ligne du tour).
export const shortName = (stop, lang, t) => stop.short || stopName(stop, lang, t);

// « Projet {n} sur {total} » + { n: 2, total: 5 } → « Projet 2 sur 5 ».
export const fill = (text, vars) => text.replace(/\{(\w+)\}/g, (_, key) => vars[key]);
// Le rang du projet d'un arrêt : « Projet 2 sur 5 » (rien pour l'accueil et le contact).
export const projectOf = (stop, t) => (stop.kind === 'project' ? fill(t.projectOf, { n: PROJECTS.indexOf(stop) + 1, total: PROJECTS.length }) : '');
// « 5 projets · 6 coups » : ce que le parcours contient.
export const tourLine = (t) => `${PROJECTS.length}\u00a0${t.projects} · ${TOTAL_STROKES}\u00a0${t.strokes}`;

// ---- le golf
// Un nombre écrit dans la langue : 1,5 en français, 1.5 en anglais.
export const num = (n, lang) => (lang === 'fr' ? String(n).replace('.', ',') : String(n));
// Une distance avec son unité : « 234 m » (espace insécable).
export const metres = (n, lang, t) => `${num(n, lang)}\u00a0${t.metres}`;
// Le rang, sur son trou, du coup qu'on joue en quittant l'arrêt k : 1 à 4 sur le par 5, 1 à 2 sur le par 3.
export const shotInHole = (k) => STOPS[k].stroke - STOPS.find((s) => s.hole === STOPS[k].hole).stroke + 1;
// Un putt n'a pas de portée : la balle roule de l'impact au trou.
export const isPutt = (shot) => shot.carry == null;
// Ce que la balle a devant elle à l'arrêt k, pour la pastille du coup : « 234 m » de loin, « 3 m pour
// birdie » au putter, « Par 5 · 478 m » sur le départ d'un trou qu'on n'atteint pas en un coup.
export function facing(k, lang, t) {
  const g = STOPS[k].golf;
  const hole = holeOf(STOPS[k]);
  if (isPutt(NEXT[k])) return `${num(g.toPin, lang)}\u00a0${pick(g.what, lang)}`;
  if (shotInHole(k) === 1 && hole.par > 3) return `${t.par}\u00a0${hole.par} · ${metres(hole.length, lang, t)}`;
  return metres(g.toPin, lang, t);
}
// Le coup qui a mené à l'arrêt k : « Fer long · 215 m · avant-green » (rien pour le départ).
export function shotInto(k, lang, t) {
  const shot = NEXT[k - 1];
  if (!shot) return '';
  return `${pick(shot.club, lang)} · ${metres(shot.total, lang, t)} · ${pick(shot.lie, lang).toLowerCase()}`;
}
// Le score par rapport au par une fois le trou n fini : « −1 », « −2 », « E ».
export function toParAfter(n) {
  const d = HOLES.filter((h) => h.n <= n).reduce((sum, h) => sum + h.score - h.par, 0);
  return d > 0 ? `+${d}` : d < 0 ? `−${-d}` : 'E';
}
// Le texte d'un lien vers l'arrêt k : « Coup 2 : SpendMap · Fairway, dans la rosée · 234 m au drapeau ».
export function stopLabel(k, lang, t) {
  const s = STOPS[k];
  const g = s.golf;
  if (k === LAST) return `${stopName(s, lang, t)} · ${pick(g.lie, lang)}`;
  // à l'accueil, le nom de l'arrêt (« Départ ») est déjà le premier mot du lie : on ne le dit qu'une fois
  const name = s.kind === 'project' ? `${stopName(s, lang, t)} · ` : '';
  return `${t.stroke}\u00a0${shotInHole(k)}${lang === 'fr' ? '\u00a0:' : ':'} ${name}${pick(g.lie, lang)} · ${num(g.toPin, lang)}\u00a0${pick(g.what, lang)}`;
}
// Ce que le dessin d'un trou (plan.js) doit savoir du site : l'écriture des nombres, le bord du
// drapeau (D/G, R/L), les repères et le vent du trou, et les liens des points de chute.
export function planCtx(h, lang, t, links = true) {
  const data = HOLES[h.n - 1];
  return {
    fmt: (n) => num(n, lang),
    pinFrom: pick(data.pin.from, lang),
    marks: (data.marks || []).map((x) => ({ m: x.m, label: pick(x.label, lang) })),
    wind: { to: data.wind.to ?? 0, label: String(data.wind.kmh), unit: t.kmh },
    links: links ? { ids: STOPS.map((s) => s.id), labels: STOPS.map((_, k) => stopLabel(k, lang, t)) } : null,
  };
}
// L'annonce de l'arrivée, pour les lecteurs d'écran : « Coup 1 : 244 m, fairway. Reste 234 m. »
export function arrival(k, lang, t) {
  const shot = NEXT[k - 1];
  if (!shot || STOPS[k - 1].stroke === STOPS[k].stroke) return '';
  const lie = pick(shot.lie, lang);
  const vars = { n: shotInHole(k - 1), total: metres(shot.total, lang, t), lie: lie.charAt(0).toLowerCase() + lie.slice(1), leaves: metres(shot.leaves, lang, t), score: pick(HOLES[STOPS[k - 1].hole - 1].scoreName, lang) };
  return fill(shot.leaves ? t.arrived : t.arrivedHoled, vars);
}

export function initialLang() {
  try {
    const saved = localStorage.getItem('lang');
    if (saved === 'fr' || saved === 'en') return saved;
  } catch {
    /* stockage indisponible */
  }
  return navigator.language?.toLowerCase().startsWith('fr') ? 'fr' : 'en';
}

export function saveLang(lang) {
  try {
    localStorage.setItem('lang', lang);
  } catch {
    /* stockage indisponible */
  }
}

// « 2 coups sur 6 » : espace insécable après le nombre ; le français garde le singulier pour zéro,
// l'anglais non.
export const strokeLine = (n, t, lang) => `${n}\u00a0${((lang === 'fr' ? n > 1 : n !== 1) ? t.strokes : t.stroke).toLowerCase()} ${t.of}\u00a0${TOTAL_STROKES}`;
