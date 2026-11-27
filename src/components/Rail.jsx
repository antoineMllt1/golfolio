// La ligne du tour : les sept arrêts du parcours sur un trait, tout en bas de l'écran. Au-dessus du
// trait le golf (les deux trous, leurs drapeaux, le club du coup à jouer, les birdies), en dessous le
// métier (le nom de chaque arrêt, son concept quand la largeur le permet). Joué : trait plein ; ici :
// l'anneau ambre ; à venir : estompé. Chaque arrêt est un lien ; au survol ou au focus, un aperçu.
// Pendant un vol, l'anneau avance sur le trait au rythme des images du film, sans rendu React
// (flight.js). Sur téléphone et dans une petite fenêtre, la ligne se réduit à une bande de sept
// points qui ouvre la liste des arrêts (Tour.jsx).
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { HOLES, LAST, NEXT, SITE, STOPS, fill, pick, projectOf, shortName, shotInto, stopName, toParAfter, tourLine } from '../lib/content.js';
import { flight as store, ratio, useCue, useFlight } from '../lib/flight.js';
import { Txt } from './Icons.jsx';

const TEES = HOLES.map((h) => STOPS.findIndex((s) => s.hole === h.n)); // le premier arrêt de chaque trou
const TEE2 = TEES[1]; // le départ du second trou : le putt d'avant tombe, puis on y va à pied
const GAP = 18; // l'air entre deux noms voisins
const PV = 328; // largeur de l'aperçu
// La place qu'il faut au nom d'un club écrit sur le trait du coup à jouer (deux bouts de trait, la pointe).
const armRoom = (club) => club.length * 6.9 + 45;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const colon = (lang) => (lang === 'fr' ? ' : ' : ': ');
// Les blancs autour des signes, en pixels : la ligne complète et la bande réduite.
const FULL = { gap: 10, ball: 14 };
const SMALL = { gap: 7, ball: 14, small: true };

// La largeur d'un élément (en pixels de mise en page), suivie quand elle change.
function useWidth(ref) {
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const read = () => setW(el.clientWidth);
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

// Sept largeurs qui remplissent W : égales si tous les noms y tiennent (c'est la ligne de la maquette),
// sinon les plus longs gardent ce qu'il leur faut et les autres se partagent le reste.
function slots(W, needs) {
  if (needs.reduce((a, b) => a + b, 0) > W) return null;
  let rest = W;
  let n = needs.length;
  for (const need of [...needs].sort((a, b) => b - a)) {
    if (need <= rest / n) break;
    rest -= need;
    n -= 1;
  }
  const even = n ? rest / n : 0;
  return needs.map((need) => Math.max(need, even));
}

const FlagMark = ({ x }) => (
  <svg className="g g-cup" style={{ left: x }} viewBox="0 0 12 17" fill="none">
    <path d="M2.5 15.5V1.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
    <path d="M2.5 1.6 10 4.3 2.5 7z" fill="currentColor" />
    <circle cx="2.5" cy="15.5" r="1.4" fill="#0a1410" stroke="currentColor" strokeWidth="1" />
  </svg>
);
const Tip = () => (
  <svg viewBox="0 0 7 9" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1.5 1 5.5 4.5 1.5 8" />
  </svg>
);

// Le dessin : les traits (joués, à jouer, en vol), les points, les drapeaux, la balle. c : le centre
// de chaque arrêt, cup : le trou du premier trou, entre son dernier arrêt et le départ suivant.
function Art({ c, cup, stop, flying, holed, g, label, total, lang, t }) {
  const at = flying ?? stop; // l'arrêt où repose la balle, ou d'où elle vient de partir
  // (sur la bande réduite, la balle et le score du trou ne tiennent pas côte à côte : le drapeau reste jusqu'à l'arrivée)
  const hole1 = at >= TEE2 || (flying === TEE2 - 1 && holed && !g.small);
  const hole2 = (flying == null && stop === LAST) || (flying === LAST - 1 && holed);
  const out = [];
  const line = (key, a, b, ga, gb, cls, inner = null) =>
    out.push(
      <span key={key} className={`ln ${cls}`} style={{ left: a - 0.5 + ga, width: Math.max(0, b - a - ga - gb) }}>
        {inner}
      </span>,
    );
  // un morceau de trait entre a et b, pour le coup j (ou la marche vers le départ suivant)
  const piece = (key, a, b, j, { walk = false, ga = g.gap, gb = g.gap } = {}) => {
    if (flying === j) {
      // en vol : la partie parcourue et la partie à venir, que le film fait avancer (usePaint)
      const l = a - 0.5 + ga;
      const r = b - 0.5 - gb;
      out.push(
        <span key={key} className={`ln live ${walk ? 'walk' : ''}`} data-l={l} data-r={r} style={{ left: l, width: Math.max(0, r - l) }}>
          <i className="was" />
          <i className="will" />
        </span>,
      );
      return;
    }
    if (!walk && flying == null && j === stop) {
      // le coup à jouer : son club écrit sur le trait, si la place y est
      const club = pick(NEXT[j].club, lang);
      const room = b - a - g.ball - gb;
      if (label && room >= armRoom(club))
        return line(
          key,
          a,
          b,
          g.ball,
          gb,
          'armed',
          <>
            <i />
            <b>{club}</b>
            <i />
            <Tip />
          </>,
        );
      return line(key, a, b, g.ball, gb, 'next');
    }
    return line(key, a, b, ga, gb, `${walk ? 'walk' : ''} ${(walk ? at >= TEE2 : j < at) ? 'done' : ''}`);
  };
  for (let j = 0; j < LAST; j++) {
    if (j === TEE2 - 1) {
      piece('putt', c[j], cup, j, { gb: hole1 ? 13 : 8 });
      piece('walk', cup, c[j + 1], j, { walk: true, ga: hole1 ? 13 : 10 });
    } else piece(`l${j}`, c[j], c[j + 1], j, j === LAST - 1 ? { gb: hole2 ? 15 : 8 } : undefined);
  }
  for (let i = 0; i < LAST; i++) {
    if (flying == null && i === stop) continue; // la balle y est
    out.push(<i key={`g${i}`} className={`g ${TEES.includes(i) ? 'g-tee' : 'g-dot'} ${i <= at ? 'done' : ''}`} style={{ left: c[i] }} />);
  }
  // Le putt rentré, le drapeau laisse la place au score du trou, entouré comme sur une carte.
  out.push(
    hole1 ? (
      <i key="cup1" className="g g-score" style={{ left: cup }}>
        {HOLES[0].score}
      </i>
    ) : (
      <FlagMark key="cup1" x={cup} />
    ),
  );
  if (hole2)
    out.push(
      <i key="cup2" className="g g-score here" style={{ left: c[LAST] }}>
        {HOLES[1].score}
      </i>,
    );
  else out.push(<FlagMark key="cup2" x={c[LAST]} />, <i key="ball" className="g g-ball" style={{ left: c[at] }} />);
  if (label) {
    if (hole1)
      out.push(
        <span key="s1" className="score" style={{ left: cup - 0.5 }}>
          {pick(HOLES[0].scoreName, lang)}
        </span>,
      );
    if (hole2)
      out.push(
        <span key="s2" className="score" style={{ left: c[LAST] - 0.5 }}>
          {pick(HOLES[1].scoreName, lang)}
        </span>,
      );
    if (hole2 && total)
      out.push(
        <span key="total" className="total">
          {STOPS[LAST].golf.card.strokes} {t.strokes} · <b>{toParAfter(STOPS[LAST].hole)}</b>
        </span>,
      );
  }
  return out;
}

// La balle avance sur le trait avec les images du film : écriture directe dans le DOM.
function usePaint(ref, c, cup) {
  const geo = useRef(null);
  geo.current = c ? { c, cup } : null;
  const paint = (s) => {
    const box = ref.current;
    const k = s.leg;
    if (!box || !geo.current || k == null) return;
    const at = geo.current.c;
    const hole = geo.current.cup;
    // un coup : de son arrêt au suivant ; le dernier putt d'un trou : jusqu'au trou, puis à pied au départ
    const x = k === TEE2 - 1 ? (s.t < 1 ? at[k] + (hole - at[k]) * s.t : hole + (at[k + 1] - hole) * s.roll) : at[k] + (at[k + 1] - at[k]) * ratio(NEXT[k], s);
    const ball = box.querySelector('.g-ball');
    if (ball) ball.style.left = `${x}px`;
    for (const el of box.querySelectorAll('.ln.live')) {
      const l = Number(el.dataset.l);
      const r = Number(el.dataset.r);
      const from = clamp(x + 14, l, r);
      el.firstChild.style.width = `${clamp(x - 14 - l, 0, r - l)}px`;
      el.lastChild.style.left = `${from - l}px`;
      el.lastChild.style.width = `${r - from}px`;
    }
  };
  useFlight(paint);
  useLayoutEffect(() => paint(store.state)); // après chaque rendu : le dessin repart de l'endroit où en est le film
}

// L'aperçu d'un arrêt : son rang, son nom, son concept, son résultat, le coup qui y mène.
function Preview({ k, x, lang, t }) {
  const s = STOPS[k];
  const project = s.kind === 'project';
  const head = project ? projectOf(s, t) : s.kind === 'intro' ? tourLine(t) : pick(s.label, lang);
  const name = project ? s.name : s.kind === 'intro' ? SITE.meta.name : t.contact;
  const concept = project ? pick(s.concept, lang) : s.kind === 'intro' ? pick(s.title, lang) : s.email;
  const foot = s.kind === 'intro' ? pick(s.label, lang) : shotInto(k, lang, t);
  return (
    <div className={`pv ${x.shifted ? 'shifted' : ''} ${s.kind}`} style={{ left: x.left }} aria-hidden>
      <p className="pv-head mono">
        <b>{head}</b>
        <kbd>{k + 1}</kbd>
      </p>
      <p className="pv-name">{name}</p>
      <p className="pv-concept">{concept}</p>
      {project && (
        <p className="pv-result">
          <span className="mono">{t.result}</span>
          <strong>
            <Txt>{pick(s.result, lang)}</Txt>
          </strong>
        </p>
      )}
      <p className="pv-foot mono">{foot}</p>
    </div>
  );
}

// Ce que lit un lecteur d'écran sur le lien d'un arrêt.
function say(k, lang, t) {
  const s = STOPS[k];
  if (s.kind === 'project') return `${projectOf(s, t)}${colon(lang)}${s.name}, ${pick(s.concept, lang)}. ${t.result}${colon(lang)}${pick(s.result, lang)}.`;
  if (s.kind === 'intro') return `${t.tee}${colon(lang)}${SITE.meta.name}, ${pick(s.title, lang)}.`;
  return `${t.contact}${colon(lang)}${s.email}`;
}

export default function Rail({ stop, flight, lang, t, onSub }) {
  const flying = flight?.shot ?? null; // le coup en vol (0 à 5), sinon null
  const cue = useCue();
  const holed = flying != null && cue.holed;
  const nav = useRef(null);
  const art = useRef(null);
  const list = useRef(null);
  const W = useWidth(nav);
  const [fonts, setFonts] = useState(0);
  const [lay, setLay] = useState(null);
  const [tip, setTip] = useState(null);
  const [slot, setSlot] = useState(0); // où commence la place libre à droite de la pastille du coup

  // Les noms sont mesurés une fois les polices arrivées.
  useEffect(() => {
    let on = true;
    document.fonts?.ready.then(() => on && setFonts((n) => n + 1));
    return () => {
      on = false;
    };
  }, []);
  // La place de chaque arrêt, d'après la largeur de la ligne et celle des noms. Les concepts
  // s'affichent s'ils tiennent tous ; sinon ceux des cinq projets ; sinon aucun.
  useLayoutEffect(() => {
    if (!W || !list.current) return;
    const names = [...list.current.querySelectorAll('.st-name')].map((el) => el.offsetWidth);
    const subs = [...list.current.querySelectorAll('.st-sub')].map((el) => el.offsetWidth);
    // ce qu'il faut à chaque arrêt : son nom, son concept s'il s'écrit, et de quoi écrire le club sur son trait
    const needs = (mode, arm) =>
      names.map((n, i) => {
        const text = Math.max(n, mode === 'all' || (mode === 'projects' && STOPS[i].kind === 'project') ? subs[i] : 0) + (i === LAST ? 4 : GAP);
        return arm && i < LAST && i !== TEE2 - 1 ? Math.max(text, armRoom(pick(NEXT[i].club, lang)) + FULL.ball + FULL.gap + 2) : text;
      });
    let sub = 'none';
    let widths = null;
    for (const [mode, arm] of [['all', true], ['projects', true], ['projects', false], ['none', true], ['none', false]]) {
      widths = slots(W, needs(mode, arm));
      sub = mode;
      if (widths) break;
    }
    if (!widths) widths = names.map(() => W / names.length);
    const x = [];
    let sum = 0;
    for (const w of widths) {
      x.push(Math.round(sum));
      sum += w;
    }
    const key = `${W}|${sub}|${x.join(',')}`;
    setLay((old) => (old?.key === key ? old : { key, W, x, sub }));
  }, [W, lang, fonts]);
  const sub = lay?.sub ?? 'none';
  useEffect(() => {
    onSub?.(sub !== 'none');
  }, [sub, onSub]);
  useEffect(() => setTip(null), [stop, flying]);
  // L'aperçu ne recouvre jamais la pastille du coup, posée juste au-dessus de la ligne et partant de
  // la même marge : sa place commence 16 px après elle.
  useLayoutEffect(() => {
    if (tip == null || !nav.current) return;
    const shot = parseFloat(getComputedStyle(nav.current).getPropertyValue('--shot-h')) || 58;
    setSlot(shot + 10 + 452 + 16);
  }, [tip, W]);

  const x = lay?.W === W ? lay.x : STOPS.map((_, i) => Math.round((i * W) / STOPS.length));
  const c = x.map((v) => v + 4.5);
  const cup = (c[TEE2 - 1] + c[TEE2]) / 2;
  usePaint(art, W ? c : null, cup);

  const show = tip != null && !(flying == null && tip === stop) ? tip : null;
  // L'aperçu s'écrit au-dessus de son arrêt quand il y tient ; sinon à la place libre la plus proche,
  // entre la pastille et le bout de la ligne (une ligne trop courte pour cela : il se cale au bout).
  const place = (k) => {
    const own = x[k] - 19;
    const max = Math.max(-19, W - PV);
    const min = slot ? Math.min(slot, max) : -19;
    const left = clamp(own, min, max);
    return { left, shifted: left !== own };
  };
  return (
    <nav className={`rail sub-${sub}`} ref={nav} aria-label={fill(t.tourStops, { n: STOPS.length })}>
      <div className={`rail-art ${flying != null ? 'flying' : ''}`} ref={art} aria-hidden>
        {W > 0 && <Art c={c} cup={cup} stop={stop} flying={flying} holed={holed} g={FULL} label total={W - x[LAST] >= 150} lang={lang} t={t} />}
      </div>
      <ol className="rail-stops" ref={list}>
        {STOPS.map((s, i) => {
          const here = flying == null && i === stop;
          const cls = [here ? 'here' : '', flying == null && i === stop + 1 ? 'next' : '', flying != null && i === flying + 1 ? 'target' : ''].join(' ');
          const hole = TEES.includes(i) ? HOLES[s.hole - 1] : null;
          const rank = s.kind === 'project' ? STOPS.filter((o, j) => o.kind === 'project' && j <= i).length : 0;
          return (
            <li key={s.id} className={`st ${cls}`} style={{ left: x[i], width: (i < LAST ? x[i + 1] : W) - x[i] }}>
              <a href={`#${s.id}`} aria-current={here ? 'step' : undefined} aria-label={say(i, lang, t)} onMouseEnter={() => setTip(i)} onMouseLeave={() => setTip(null)} onFocus={() => setTip(i)} onBlur={() => setTip(null)}>
                {hole && (
                  <span className="st-top mono">
                    {t.hole} {hole.n} · {t.par} {hole.par} · {hole.length} {t.metres}
                  </span>
                )}
                <span className="st-name">{shortName(s, lang, t)}</span>
                <span className="st-sub mono">
                  {rank > 0 && <b>{rank}</b>}
                  {s.kind === 'project' ? pick(s.concept, lang) : s.kind === 'intro' ? pick(s.title, lang) : s.email}
                </span>
              </a>
            </li>
          );
        })}
      </ol>
      {show != null && <Preview k={show} x={place(show)} lang={lang} t={t} />}
    </nav>
  );
}

const ChevUp = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d="M3.5 10 8 5.5 12.5 10" />
  </svg>
);

// La ligne du tour en petit (téléphone, petite fenêtre) : sept points, deux drapeaux, la balle.
// Elle ouvre la liste des arrêts.
export function Strip({ stop, flight, lang, t, onOpen }) {
  const flying = flight?.shot ?? null;
  const cue = useCue();
  const box = useRef(null);
  const W = useWidth(box);
  const c = STOPS.map((_, i) => (i / LAST) * W + 0.5);
  const cup = ((TEE2 - 0.5) / LAST) * W + 0.5;
  usePaint(box, W ? c : null, cup);
  return (
    <button type="button" className="strip" onClick={onOpen} aria-haspopup="dialog" aria-label={fill(t.tourAt, { n: STOPS.length, name: stopName(STOPS[stop], lang, t) })}>
      <span className={`strip-art ${flying != null ? 'flying' : ''}`} ref={box} aria-hidden>
        {W > 0 && <Art c={c} cup={cup} stop={stop} flying={flying} holed={flying != null && cue.holed} g={SMALL} lang={lang} t={t} />}
      </span>
      <span className="strip-label">
        {t.tour}
        <ChevUp />
      </span>
    </button>
  );
}
