// Tout le texte du site vient de content/site.json (français et anglais) : rien n'est écrit ici.
import site from '../../content/site.json';

export const SITE = site;
export const STOPS = site.stops;
export const LAST = STOPS.length - 1;
export const HOLES = site.holes;
export const NEXT = site.next;
export const TOTAL_STROKES = STOPS[LAST].stroke;

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
