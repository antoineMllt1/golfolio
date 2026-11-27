// Le traceur du vol : pendant qu'un coup joue, la fiche s'efface et, en bas à gauche au-dessus de la
// pastille, la distance compte en très grand à côté du profil du vol (axe gradué, hauteur maximale,
// green et drapeau à leur distance). Tout est calé sur les images du film par le magasin d'état du
// vol (flight.js) : zéro avant l'impact, le total à la dernière image, écrit directement dans le DOM.
// Un putt n'a pas de courbe : la distance au trou décompte, puis « Birdie ». Quand le film change de
// trou (le putt du 1), le carton du trou suivant prend la place, puis s'efface avant l'arrivée.
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { HOLES, NEXT, STOPS, fill, isPutt, metres, num, pick, shortName, shotInHole, toParAfter } from '../lib/content.js';
import { flight as store, travelled, useCue, useFlight } from '../lib/flight.js';

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
// La forme d'un vol : la balle monte vite, plafonne aux 58 % de la portée, retombe plus raide.
const UP = 1;
const DOWN = 0.72;
const S_TOP = UP / (UP + DOWN);
const TOP = S_TOP ** UP * (1 - S_TOP) ** DOWN;
// La hauteur de la balle (en mètres) à la distance d du coup.
const heightAt = (shot, d) => {
  if (!shot.carry || !shot.apex) return 0;
  const s = clamp(d / shot.carry, 0, 1);
  return (shot.apex * s ** UP * (1 - s) ** DOWN) / TOP;
};
const STEPS = [0.5, 1, 2, 5, 10, 25, 50, 100];
const r1 = (x) => Math.round(x * 10) / 10;

// Le profil du coup k dans une zone de w × h pixels : le dessin (une chaîne SVG) et de quoi faire
// avancer la balle (paint). L'axe va du coup jusqu'au fond du green s'il est à portée, sinon un peu
// plus loin que le point de chute.
function profile(k, w, h, small, lang, t) {
  const shot = NEXT[k];
  const stop = STOPS[k];
  const hole = HOLES[stop.hole - 1];
  const putt = isPutt(shot);
  const pin = stop.golf.toPin;
  const front = pin - hole.pin.on;
  const back = front + hole.green.depth;
  const near = pin <= shot.total * 1.5; // le drapeau est sur le dessin
  const far = putt ? shot.total * 1.14 : near ? Math.min(back + (back - front) * 0.1, pin * 1.2) : shot.total * 1.08;
  const x0 = small ? 6 : 24;
  const base = h - 30;
  const ppm = (w - x0 - (small ? 26 : 30)) / far;
  const pph = shot.apex ? Math.min(1.73 * ppm, (base - 32) / shot.apex) : 0;
  const X = (d) => r1(x0 + d * ppm);
  const Y = (m) => r1(base - m * pph);
  const step = STEPS.find((s) => far / s <= (small ? 3.4 : 6.5)) || 100;
  const unit = t.metres.toUpperCase();
  const out = [`<path class="axis" d="M${x0} ${base}H${w}"/>`];
  // ce qui s'écrit sous l'axe, pour ne rien superposer
  const taken = [];
  const free = (x, half) => taken.every(([a, b]) => x + half < a || x - half > b);
  const text = (x, s, cls = '', anchor = 'middle') => `<text${cls ? ` class="${cls}"` : ''} x="${x}" y="${base + 20}" text-anchor="${anchor}">${s}</text>`;
  if (near || putt) {
    const label = `${num(pin, lang)} ${unit}`;
    if (!putt) out.push(`<path class="green" d="M${X(front)} ${base}H${Math.min(w, X(back))}"/>`);
    out.push(`<path class="flagp" d="M${X(pin)} ${base}v-${small ? 16 : 20}l${small ? 8 : 10} ${small ? 3 : 3.8}-${small ? 8 : 10} ${small ? 3 : 3.8}"/>`, text(X(pin), label, 'soft'));
    taken.push([X(pin) - label.length * 3.6 - 26, X(pin) + label.length * 3.6 + 26]);
    if (!putt && !small && X(pin) - X(front) >= 44 && X(front) - x0 >= 30) {
      out.push(text(X(front), num(front, lang)));
      taken.push([X(front) - 40, X(front) + 40]);
    }
  } else {
    // le drapeau est plus loin : sa distance au bout de l'axe
    const label = `${t.pin} ${num(pin, lang)} ${unit}`.toUpperCase();
    out.push(`<path class="tickl" d="M${w - 4.5} ${base - 4}l4 4-4 4"/>`, text(w, label, 'soft', 'end'));
    taken.push([w - label.length * 7.2 - 10, w]);
  }
  for (let d = 0; d <= far + 1e-6; d += step) {
    out.push(`<path class="tickl" d="M${X(d)} ${base}v5"/>`);
    const s = num(r1(d), lang);
    if (free(X(d), s.length * 3.6 + 6)) out.push(text(X(d), s));
  }
  // la trajectoire : la portée en cloche, puis la roule au ras du sol
  const N = putt ? 1 : 96;
  const pts = [];
  const len = [0];
  for (let i = 0; i <= N; i++) {
    const d = putt ? 0 : (shot.carry * i) / N;
    const p = [x0 + d * ppm, base - heightAt(shot, d) * pph];
    if (i) len.push(len[i - 1] + Math.hypot(p[0] - pts[i - 1][0], p[1] - pts[i - 1][1]));
    pts.push(p);
  }
  const flown = len[N]; // la longueur du tracé jusqu'au point de chute
  const total = flown + (shot.total - (shot.carry || 0)) * ppm;
  const d = `${pts.map((p, i) => `${i ? 'L' : 'M'}${r1(p[0])} ${r1(p[1])}`).join('')}L${X(shot.total)} ${base}`;
  if (shot.apex) {
    const top = S_TOP * shot.carry;
    const label = `${small ? t.maxShort : t.maxHeight} ${num(shot.apex, lang)} ${unit}`.toUpperCase();
    out.push(`<path class="apex" d="M${X(top)} ${Y(shot.apex) + 5}V${base}"/>`, `<text class="soft" x="${clamp(X(top), label.length * 3.7, w - label.length * 3.7)}" y="${Y(shot.apex) - 11}" text-anchor="middle">${label}</text>`);
  }
  out.push(
    `<path class="glow" d="${d}" stroke-dasharray="${r1(total)}" stroke-dashoffset="${r1(total)}"/>`,
    `<path class="path" d="${d}" stroke-dasharray="${r1(total)}" stroke-dashoffset="${r1(total)}"/>`,
    `<circle class="halo" cx="${x0}" cy="${base}" r="7"/>`,
    `<circle class="head" cx="${x0}" cy="${base}" r="3.2"/>`,
  );
  // La balle a parcouru m mètres : le tracé s'allonge jusqu'à elle.
  const paint = (svg, m) => {
    let at;
    let x;
    let y = base;
    if (putt || m >= shot.carry) {
      at = flown + (m - (shot.carry || 0)) * ppm;
      x = x0 + m * ppm;
    } else {
      const f = (m / shot.carry) * N;
      const i = Math.min(N - 1, Math.floor(f));
      at = len[i] + (len[i + 1] - len[i]) * (f - i);
      x = x0 + m * ppm;
      y = base - heightAt(shot, m) * pph;
    }
    const off = Math.max(0, total - at).toFixed(1);
    const [glow, path, halo, head] = [svg.querySelector('.glow'), svg.querySelector('.path'), svg.querySelector('.halo'), svg.querySelector('.head')];
    if (!path) return;
    glow.setAttribute('stroke-dashoffset', off);
    path.setAttribute('stroke-dashoffset', off);
    for (const el of [halo, head]) {
      el.setAttribute('cx', x.toFixed(1));
      el.setAttribute('cy', y.toFixed(1));
    }
  };
  return { svg: out.join(''), paint };
}

// La taille d'une zone, suivie quand elle change.
function useSize(ref) {
  const [size, setSize] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const read = () => setSize((old) => (old.w === el.clientWidth && old.h === el.clientHeight ? old : { w: el.clientWidth, h: el.clientHeight }));
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [ref]);
  return size;
}

export default function Tracer({ flight, lang, t }) {
  const flying = flight?.shot ?? null;
  const cue = useCue();
  const [kept, setKept] = useState(flying); // le dernier coup joué : il reste dessiné le temps que le traceur s'efface
  if (flying != null && kept !== flying) setKept(flying);
  const k = flying ?? kept;
  const box = useRef(null);
  const svg = useRef(null);
  const big = useRef(null);
  const last = useRef('');
  const { w, h } = useSize(box);

  const shot = k != null ? NEXT[k] : null;
  const putt = shot ? isPutt(shot) : false;
  const small = w > 0 && w < 420;
  const drawing = useMemo(() => (k != null && w > 0 && h > 0 ? profile(k, w, h, small, lang, t) : null), [k, w, h, small, lang, t]);
  // Le putt rentré reste « Birdie » le temps que le traceur s'efface, une fois la balle posée.
  const [sunk, setSunk] = useState(null);
  if (flying != null && cue.holed !== (sunk === flying)) setSunk(cue.holed ? flying : null);
  const holed = flying != null ? cue.holed : sunk === k;
  const crossing = k != null && STOPS[k + 1].hole !== STOPS[k].hole; // ce coup finit un trou, le film passe au suivant
  const carton = flying != null && crossing && cue.turned && !cue.ending;
  const on = flying != null && !(crossing && cue.turned);

  // Le compteur et le profil quand la balle a parcouru m mètres.
  const mem = useRef({ k: null, m: 0 });
  const apply = (m) => {
    if (drawing && svg.current) drawing.paint(svg.current, m);
    if (!big.current) return;
    // un coup : les mètres parcourus ; un putt : ce qui reste jusqu'au trou, au décimètre
    const txt = putt ? num(Math.max(0, STOPS[k].golf.toPin - m).toFixed(1), lang) : String(Math.round(m));
    if (txt === last.current) return;
    last.current = txt;
    const cells = big.current.children;
    for (let i = 0; i < cells.length - 1; i++) {
      const ch = txt[i] ?? '';
      if (cells[i].textContent !== ch) cells[i].textContent = ch;
      // Les deux derniers chiffres changent à chaque image : des cases de même largeur, pour que la
      // ligne ne tremble pas. Devant, un « 1 » reprend sa largeur.
      cells[i].className = ch === '' ? 'off' : ch === ',' || ch === '.' ? 'sep' : ch === '1' && i < txt.length - 2 ? 'd one' : 'd';
    }
  };
  // À chaque image du film : où en est le coup.
  const paint = (s) => {
    if (s.leg == null || s.leg !== k) return;
    mem.current = { k, m: travelled(NEXT[k], s) };
    apply(mem.current.m);
  };
  useFlight(paint);
  // Après un rendu (le dessin a pu être refait) : on le remet où en est le film, ou là où le coup a fini.
  useLayoutEffect(() => {
    last.current = '';
    if (store.state.leg === k) paint(store.state);
    else if (k != null && mem.current.k === k) apply(mem.current.m);
  });

  // Avant le premier coup, la zone du profil est déjà là (vide) : sa taille est connue quand il part.
  if (k == null)
    return (
      <div className="trace" aria-hidden>
        <div className="trace-hero" />
        <div className="profile-box" ref={box} />
      </div>
    );
  const stop = STOPS[k];
  const to = STOPS[k + 1];
  const hole = HOLES[stop.hole - 1];
  const next = HOLES[to.hole - 1];
  const width = putt ? num(stop.golf.toPin.toFixed(1), lang).length : String(Math.round(shot.total)).length;
  return (
    <>
      <div className={`trace ${on ? 'on' : ''} ${putt ? 'putt' : ''}`} aria-hidden>
        <div className="trace-hero">
          <p className="trace-head mono">
            <b>
              {t.stroke} {shotInHole(k)} · {pick(shot.club, lang)}
            </b>
            <i />
            <span>
              {t.towards} {to.kind === 'project' ? shortName(to, lang, t) : t.contact}
            </span>
          </p>
          {putt && holed ? (
            <p className="big word">
              {pick(hole.scoreName, lang)}
              <em>{fill(t.holeIn, { n: hole.n, strokes: hole.score })}</em>
            </p>
          ) : (
            <p className="big" ref={big}>
              {Array.from({ length: width }, (_, i) => (
                <span key={i} className="off" />
              ))}
              <em>
                {t.metres}
                {putt && <small>{pick(stop.golf.what, lang).replace(/^\S+\s+/, '')}</small>}
              </em>
            </p>
          )}
          {!putt && (
            <dl className="pdata">
              <div>
                <dt>{t.carry}</dt>
                <dd>{metres(shot.carry, lang, t)}</dd>
              </div>
              <div>
                <dt>{t.roll}</dt>
                <dd>{metres(shot.roll, lang, t)}</dd>
              </div>
              <div>
                <dt>{t.maxHeight}</dt>
                <dd>{metres(shot.apex, lang, t)}</dd>
              </div>
            </dl>
          )}
        </div>
        <div className="profile-box" ref={box}>
          {drawing && <svg ref={svg} className="profile" width={w} height={h} viewBox={`0 0 ${w} ${h}`} dangerouslySetInnerHTML={{ __html: drawing.svg }} />}
        </div>
      </div>
      {crossing && (
        <section className={`carton ${carton ? 'on' : ''}`} aria-hidden>
          <p className="carton-prev mono">
            <span>
              {t.hole} {hole.n}
            </span>
            <span className="ring">{hole.score}</span>
            <b>{pick(hole.scoreName, lang)}</b>
            <i />
            <span>{t.score}</span>
            <b className="under">{toParAfter(hole.n)}</b>
          </p>
          <h2>
            {t.hole} <em>{next.n}</em>
          </h2>
          <p className="carton-sub">
            {t.par} {next.par}
            <i>·</i>
            {metres(next.length, lang, t)}
            <i>·</i>
            {pick(next.shape, lang)}
          </p>
        </section>
      )}
    </>
  );
}
