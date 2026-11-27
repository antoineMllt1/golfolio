// L'avancée du vol : un petit magasin d'état alimenté par le lecteur de film (film.js), pour tout ce
// qui s'anime au rythme des images sans passer par React (la ligne du coup sur le plan du carnet, la
// réglette portée / roule / total ; demain le compteur et le profil du traceur, le segment de la
// ligne du tour).
//
// USAGE
//   import { flight, ratio, travelled, useFlight } from '../lib/flight.js';
//
//   useFlight((s) => {                       // dans un composant : appelé à chaque image dessinée,
//     if (s.leg == null) return;             // jamais de setState ici : on écrit dans le DOM
//     el.textContent = Math.round(travelled(NEXT[s.leg], s));
//     bar.style.setProperty('--p', ratio(NEXT[s.leg], s));
//   });
//   const stop = flight.subscribe(fn);       // hors de React ; fn est appelée tout de suite, puis à chaque image
//
// L'ÉTAT (un seul objet, réutilisé : ne pas le garder, ne pas le modifier)
//   leg     trajet en cours, 0 à 5 (le coup joué : NEXT[leg], de l'arrêt leg à leg + 1) ; null au repos
//   frames  nombre d'images du trajet
//   frame   image courante, de 1 à frames (nombre à virgule : le film avance entre deux images)
//   p       avancée du trajet entier, de 0 à 1
//   impact, land  images de l'impact et de la chute (dans le trou, pour un putt)
//   t       avancée de 0 à 1 entre l'impact et la chute : 0 avant l'impact, 1 dès que la balle touche
//   roll    avancée de 0 à 1 entre la chute et la dernière image (la roule)
//   done    true dès que la dernière image est atteinte (ou le vol sauté) : tout est à sa valeur finale
//
// Un trajet se déroule ainsi : begin (t = 0), une notification par image, puis une dernière avec
// t = 1, roll = 1, done = true (aussi quand un geste saute à l'arrivée), enfin leg = null quand la
// page est posée sur l'arrêt. Les fondus (retour arrière, saut, animations réduites, trajet absent)
// ne passent pas par ici : leg reste null, et les composants affichent directement l'état final.
//
// CALAGE de l'impact et de la chute : legs[k].impact et legs[k].land de public/frames/manifest.json
// s'ils existent ; sinon next[k].sync de content/site.json ; sinon 20 % et 85 % du trajet.
import { useEffect, useRef } from 'react';
import { NEXT } from './content.js';

const clamp01 = (x) => Math.min(1, Math.max(0, x));
const state = { leg: null, frames: 0, frame: 0, p: 0, impact: 0, land: 0, t: 0, roll: 0, done: false };
const subs = new Set();
const emit = () => {
  for (const fn of subs) fn(state);
};

// Les images d'impact et de chute du trajet k, pour un trajet de n images.
export function cue(k, n, leg) {
  const valid = (c) => c && Number.isFinite(c.impact) && Number.isFinite(c.land) && c.impact >= 1 && c.impact < c.land && c.land <= n;
  if (valid(leg)) return { impact: leg.impact, land: leg.land };
  const sync = NEXT[k]?.sync;
  if (valid(sync)) return { impact: sync.impact, land: sync.land };
  return { impact: Math.max(1, Math.round(n * 0.2)), land: Math.max(2, Math.round(n * 0.85)) };
}

export const flight = {
  state,
  subscribe(fn) {
    subs.add(fn);
    fn(state);
    return () => subs.delete(fn);
  },
  // --- côté film
  // Le trajet k part : n images ; leg est son entrée dans le manifeste (pour le calage).
  begin(k, n, leg) {
    Object.assign(state, { leg: k, frames: n, done: false }, cue(k, n, leg));
    this.at(0);
  },
  // Le film est à la position f du trajet (0 = première image, n - 1 = dernière).
  at(f) {
    if (state.leg == null || state.done) return;
    const n = state.frames;
    const frame = Math.min(n, Math.max(1, f + 1));
    state.frame = frame;
    state.p = n > 1 ? clamp01((frame - 1) / (n - 1)) : 1;
    state.t = clamp01((frame - state.impact) / (state.land - state.impact));
    state.roll = state.land < n ? clamp01((frame - state.land) / (n - state.land)) : state.t >= 1 ? 1 : 0;
    emit();
  },
  // Dernière image, ou vol sauté : tout prend sa valeur finale.
  finish() {
    if (state.leg == null) return;
    Object.assign(state, { frame: state.frames, p: 1, t: 1, roll: 1, done: true });
    emit();
  },
  // La page est posée (ou le vol a été remplacé par un autre déplacement).
  rest() {
    if (state.leg == null) return;
    state.leg = null;
    emit();
  },
};

// Les mètres parcourus par la balle pour le coup « shot » (une entrée de NEXT) : la portée pendant le
// vol, puis la roule ; un putt (sans portée) roule de l'impact à la chute.
export function travelled(shot, s = state) {
  if (shot.carry == null) return shot.total * s.t;
  return shot.carry * s.t + (shot.total - shot.carry) * s.roll;
}
// La même avancée rapportée au total du coup, de 0 à 1 : la place de la balle le long de sa ligne.
export const ratio = (shot, s = state) => (shot.total ? clamp01(travelled(shot, s) / shot.total) : 1);

// Dans un composant : fn(state) à chaque image, sans rendu React.
export function useFlight(fn) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => flight.subscribe((s) => ref.current(s)), []);
}
