// Le carnet de parcours : tout ce qui est golf vit ici. Sur un écran d'ordinateur c'est une page posée
// à droite du film : les onglets des deux trous (une pastille par coup : la carte de score et le fil
// des arrêts), le plan du trou à trois cadrages (tout le trou, le coup à jouer, l'encart du green) et
// les notes du caddie. Pendant un vol la ligne du coup s'y écrit avec la balle, image par image, sans
// rendu React (flight.js). Sur téléphone, dans une petite fenêtre ou une fois repliée, la page se
// réduit à une languette : le trou en petit, la balle, six points.
import { Fragment, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { COURSE, HOLES, LAST, NEXT, SITE, STOPS, metres, num, pick, planCtx, shortName, shotInHole, stopLabel } from '../lib/content.js';
import { ballAt } from '../lib/film.js';
import { flight as flightStore, ratio, useFlight } from '../lib/flight.js';
import { between, miniView, pageView, paintFlight } from '../lib/plan.js';
import { Flag, Fold } from './Icons.jsx';

const PW = 250; // largeur de la zone de dessin de la page
// La page entière demande un écran d'ordinateur (au moins 1180 × 700) et ne doit jamais recouvrir la
// balle : son bord gauche (poignée comprise) reste à droite de la balle, dont le rayon au premier plan
// fait environ 12 % de la hauteur. Sinon : la languette.
function hasRoom() {
  const w = window.innerWidth;
  const h = window.innerHeight;
  if (w < 1180 || h < 700) return false;
  const zoom = w >= 3000 && h >= 1600 ? 1.8 : w >= 2200 && h >= 1200 ? 1.36 : w >= 1800 && h >= 960 ? 1.12 : 1; // l'agrandissement des grands écrans (styles.css)
  const gutter = Math.min(80, Math.max(20, w * 0.05));
  const left = w - (gutter + 284 + 24) * zoom;
  return left - (w * ballAt() + h * 0.12) >= 12;
}
const first = (n) => STOPS.findIndex((s) => s.hole === n);
const lower = (s) => s.charAt(0).toLowerCase() + s.slice(1);
const colon = (lang) => (lang === 'fr' ? ' : ' : ': ');

function readFolded() {
  try {
    return localStorage.getItem('carnet') === 'folded';
  } catch {
    return false;
  }
}

// ---------- les onglets : un par trou. Une pastille par coup (un lien vers son arrêt), le drapeau pour
// le contact ; le trou fini, son score entouré. Le chiffre du trou feuillette la page sans bouger la balle.
function Tabs({ at, flying, holed, shown, lang, t, onFlip }) {
  return (
    <div className="tabs">
      {HOLES.map((h) => {
        const f = first(h.n);
        const count = h.score;
        const on = shown === h.n;
        const done = (k) => (flying != null ? k < flying || (k === flying && holed) : k < at);
        const finished = done(f + count - 1);
        return (
          <div key={h.n} className={`tab ${on ? 'on' : ''}`}>
            <button type="button" className="tab-n" onClick={() => onFlip(h.n)} aria-pressed={on} aria-label={`${t.flipTo} ${h.n}, ${t.par.toLowerCase()} ${h.par}, ${h.length} ${t.metres}`}>
              {h.n}
            </button>
            <div className="tab-meta">
              <span className={`mono ${finished ? 'fin' : ''}`}>
                {t.par} {h.par}{' '}
                {finished ? (
                  <>
                    <b className="circ">{h.score}</b> <span>{pick(h.scoreName, lang)}</span>
                  </>
                ) : (
                  <span>
                    · {h.length} {t.metres}
                  </span>
                )}
              </span>
              <ol className="pips">
                {Array.from({ length: count }, (_, i) => {
                  const k = f + i;
                  const st = done(k) ? 'done' : flying === k ? 'fly' : flying == null && k === at ? 'cur' : '';
                  return (
                    <li key={k}>
                      <a className={`pip ${st}`} href={`#${STOPS[k].id}`} aria-label={stopLabel(k, lang, t)} aria-current={st === 'cur' ? 'step' : undefined}>
                        {i + 1}
                      </a>
                    </li>
                  );
                })}
                {f + count === LAST && (
                  <li>
                    <a className={`pip flagpip ${at === LAST && flying == null ? 'cur' : ''}`} href={`#${STOPS[LAST].id}`} aria-label={stopLabel(LAST, lang, t)} aria-current={at === LAST && flying == null ? 'step' : undefined}>
                      <Flag />
                    </a>
                  </li>
                )}
              </ol>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------- le plan : le dessin courant, et l'ancien le temps du recadrage. Deux vues du même trou
// s'enchaînent par un mouvement de caméra (les deux calques restent superposés au pixel) ; sinon un fondu.
function Plan({ drawing, reduce, names }) {
  const box = useRef(null);
  const [layers, setLayers] = useState({ cur: drawing, old: null, n: 0 });
  const [tip, setTip] = useState(null);
  if (layers.cur.key !== drawing.key) {
    const same = layers.cur.w === drawing.w && layers.cur.h === drawing.h && layers.cur.lang === drawing.lang;
    setLayers({ cur: drawing, old: same ? layers.cur : null, n: layers.n + 1 }); // animations réduites : l'ancien dessin reste le temps d'un fondu court, sans mouvement
    if (tip) setTip(null);
  }
  const { cur, old, n } = layers;
  const move = !reduce && old ? between(old, cur, COURSE[cur.hole - 1]) : null;
  const ms = reduce ? 160 : move ? 700 : 260;
  // Le calque agrandi par le mouvement (l'ancien quand on se rapproche, le nouveau quand on s'éloigne)
  // montre un trait grossi : c'est lui qui s'efface le plus vite, ou paraît le plus tard.
  const kind = !move ? '' : move.s > 1.15 ? 'move closer' : move.s < 0.87 ? 'move farther' : 'move';
  useEffect(() => {
    if (!old) return undefined;
    const id = setTimeout(() => setLayers((l) => (l.n === n ? { ...l, old: null } : l)), ms + 60);
    return () => clearTimeout(id);
  }, [n, old, ms]);
  // Le coup en vol est dessiné à son point de départ : on le met tout de suite où en est le film.
  useLayoutEffect(() => {
    const s = flightStore.state;
    if (s.leg != null) paintFlight(box.current, ratio(NEXT[s.leg], s));
  }, [cur.key]);
  useFlight((s) => {
    if (s.leg != null) paintFlight(box.current, ratio(NEXT[s.leg], s));
  });

  // Au survol ou au focus d'un point de chute : le nom du projet.
  const show = (e) => {
    const a = e.target.closest?.('a.pt');
    if (!a || !box.current) return;
    const hit = a.querySelector('.hit').getBoundingClientRect();
    const frame = box.current.getBoundingClientRect();
    const zoom = frame.width / box.current.offsetWidth || 1; // la page est agrandie sur les très grands écrans
    setTip({ k: Number(a.dataset.k), x: (hit.left + hit.width / 2 - frame.left) / zoom, y: (hit.top - frame.top) / zoom });
  };
  const hide = () => setTip(null);
  const vars = (m, enter) => {
    if (!m) return { '--ms': `${ms}ms` };
    if (!enter) return { '--ms': `${ms}ms`, '--r': `${m.r}deg`, '--s': m.s, '--x': `${m.x}px`, '--y': `${m.y}px` };
    // le calque qui arrive part de l'inverse : il est déjà à sa place, vu depuis l'ancien cadrage
    const a = (m.r * Math.PI) / 180;
    return { '--ms': `${ms}ms`, '--r': `${-m.r}deg`, '--s': 1 / m.s, '--x': `${-m.s * (m.x * Math.cos(a) - m.y * Math.sin(a))}px`, '--y': `${-m.s * (m.x * Math.sin(a) + m.y * Math.cos(a))}px` };
  };
  const layer = (d, cls, style) => (
    <svg key={d.key} className={`layer ${cls}`} style={style} viewBox={`0 0 ${d.w} ${d.h}`} width={d.w} height={d.h} role="group" aria-label={d.label} dangerouslySetInnerHTML={{ __html: d.svg }} />
  );
  return (
    <div className="plan-art ink" ref={box} style={{ width: cur.w, height: cur.h }} onMouseOver={show} onMouseOut={hide} onFocus={show} onBlur={hide}>
      {old && layer(old, `out ${kind}`, vars(move, false))}
      {layer(cur, old ? `in ${kind}` : '', vars(move, true))}
      {tip && (
        <span className={`plan-tip ${tip.x > cur.w * 0.62 ? 'left' : tip.x < cur.w * 0.38 ? 'right' : ''}`} style={{ left: tip.x, top: tip.y }} aria-hidden>
          {names[tip.k]}
        </span>
      )}
    </div>
  );
}

// ---------- les notes du caddie
const Head = ({ left, right }) => (
  <p className="notes-head">
    <span>{left}</span>
    <b>{right}</b>
  </p>
);
const Side = ({ rows }) => (
  <dl className="yard-side">
    {rows.map(([a, b]) => (
      <div key={a}>
        <dt>{a}</dt>
        <dd>{b}</dd>
      </div>
    ))}
  </dl>
);
const Facts = ({ rows }) => (
  <dl className="facts">
    {rows.map(([a, b]) => (
      <Fragment key={a}>
        <dt>{a}</dt>
        <dd>{b}</dd>
      </Fragment>
    ))}
  </dl>
);

// À l'arrêt : la distance en grand, deux cotes, deux faits, une phrase.
function StopNotes({ k, lang, t }) {
  const g = STOPS[k].golf;
  return (
    <div className="notes">
      <Head left={t.caddieNotes} right={`${t.stroke} ${shotInHole(k)} · ${pick(NEXT[k].club, lang)}`} />
      <div className="yard">
        <p className="yard-n">
          <strong>{num(g.toPin, lang)}</strong>
          <span>{pick(g.what, lang)}</span>
        </p>
        <Side rows={g.side.map(([a, b]) => [pick(a, lang), pick(b, lang)])} />
      </div>
      <Facts rows={g.facts.map(([a, b]) => [pick(a, lang), pick(b, lang)])} />
      <p className="say">«&nbsp;{pick(g.say, lang)}&nbsp;»</p>
    </div>
  );
}
// En vol : la réglette portée / roule / total, calée sur les images du film, et la zone visée. Pas de
// grand compteur ici : il est à gauche, dans le traceur. Un putt : sa ligne, puis « dans le trou ».
function LiveNotes({ k, holed, lang, t }) {
  const shot = NEXT[k];
  const g = STOPS[k].golf;
  const bar = useRef(null);
  useFlight((s) => {
    if (s.leg === k) bar.current?.style.setProperty('--p', ratio(shot, s).toFixed(4));
  });
  const putt = shot.carry == null;
  // un coup : portée, roule, total ; un putt : sa pente, sa ligne, sa longueur
  const cells = putt ? [...g.side.map(([a, b]) => [pick(a, lang), pick(b, lang)]), ['', metres(shot.total, lang, t)]] : [[t.carry, num(shot.carry, lang)], [t.roll, num(shot.roll, lang)], [t.total, num(shot.total, lang)]];
  return (
    <div className="notes live">
      <Head left={putt ? t.rolling : t.inFlight} right={`${t.stroke} ${shotInHole(k)} · ${pick(shot.club, lang)}`} />
      <div className="gauge" ref={bar} aria-hidden>
        <span className="fill" />
        <i style={{ left: 0 }} />
        {!putt && <i style={{ left: `${(shot.carry / shot.total) * 100}%` }} />}
        <i style={{ left: '100%' }} />
        <span className="dot" />
      </div>
      <dl className="gauge-l">
        {cells.map(([a, b]) => (
          <div key={a}>
            {a ? <dt>{a}</dt> : <dt className="sr-only">{t.total}</dt>}
            <dd>{b}</dd>
          </div>
        ))}
      </dl>
      {putt ? (
        <p className={`say ${holed ? '' : 'dim'}`}>{holed ? `${pick(shot.lands, lang)}.` : `« ${pick(g.say, lang)} »`}</p>
      ) : (
        <p className="say dim">
          {t.target}
          {colon(lang)}
          {lower(pick(shot.lands, lang))}.
        </p>
      )}
    </div>
  );
}
// Au contact : la carte signée.
function CardNotes({ lang, t }) {
  const stop = STOPS[LAST];
  const card = stop.golf.card;
  const par = HOLES.reduce((sum, h) => sum + h.par, 0);
  return (
    <div className="notes">
      <Head left={t.scorecard} right={`${t.par} ${par}`} />
      <div className="yard">
        <p className="yard-n">
          <strong>{card.strokes}</strong>
          <span>
            {t.strokes.toLowerCase()}, {-card.toPar}&nbsp;{t.underPar}
          </span>
        </p>
      </div>
      <dl className="facts">
        {HOLES.map((h) => (
          <Fragment key={h.n}>
            <dt>
              {t.hole} {h.n}
            </dt>
            <dd>
              {t.par} {h.par} · <b className="circ">{h.score}</b> {pick(h.scoreName, lang)}
            </dd>
          </Fragment>
        ))}
      </dl>
      <p className="say signed">
        {SITE.meta.name}
        <span>{pick(card.label, lang)}</span>
      </p>
    </div>
  );
}
// On feuillette l'autre trou : sa fiche, et de quoi revenir à la balle.
function HoleNotes({ hole, lang, t, onBack }) {
  return (
    <div className="notes">
      <Head left={`${t.hole} ${hole.n}`} right={`${t.par} ${hole.par}`} />
      <div className="yard">
        <p className="yard-n">
          <strong>{hole.length}</strong>
          <span>
            {t.metres}, {t.par.toLowerCase()} {hole.par}
          </span>
        </p>
        <Side rows={[[t.green, `${hole.green.depth} × ${hole.green.width}`], [t.pin, `${hole.pin.on} · ${hole.pin.side} ${pick(hole.pin.from, lang)}`]]} />
      </div>
      <Facts rows={[[t.layout, pick(hole.shape, lang)], [t.wind, pick(hole.wind.label, lang)]]} />
      <p className="say">
        <button type="button" className="back-ball" onClick={onBack}>
          {t.backToBall}
        </button>
      </p>
    </div>
  );
}

// ---------- la languette : la page en petit. Elle ouvre le carnet (ou déplie la page).
function Tag({ at, flying, turned, lang, t, onClick, label }) {
  // en vol : la ligne du coup s'écrit ici aussi ; la page tournée, c'est déjà le trou suivant
  const inAir = flying != null && !turned;
  const ball = turned ? at + 1 : at;
  const hole = HOLES[STOPS[ball].hole - 1];
  const art = useRef(null);
  const mini = useMemo(() => {
    const h = COURSE[hole.n - 1];
    return miniView(h, 56, 142, ball, inAir ? { shot: ball - h.first } : null);
  }, [hole.n, ball, inAir]);
  useLayoutEffect(() => {
    const s = flightStore.state;
    if (inAir && s.leg != null) paintFlight(art.current, ratio(NEXT[s.leg], s));
  }, [mini, inAir]);
  useFlight((s) => {
    if (s.leg != null) paintFlight(art.current, ratio(NEXT[s.leg], s));
  });
  return (
    <button type="button" className="languette ink" onClick={onClick} aria-label={`${label}. ${t.hole} ${hole.n}, ${t.par.toLowerCase()} ${hole.par}, ${stopLabel(at, lang, t)}`}>
      <span className="lang-h">
        <b>{hole.n}</b>
        {t.par} {hole.par}
      </span>
      <svg ref={art} key={mini.svg.length + (inAir ? 'v' : 'p') + ball} viewBox={`0 0 ${mini.w} ${mini.h}`} aria-hidden dangerouslySetInnerHTML={{ __html: mini.svg }} />
      <span className="lang-pips" aria-hidden>
        {STOPS.slice(0, LAST).map((s, k) => (
          <i key={s.id} className={`${k > 0 && s.hole !== STOPS[k - 1].hole ? 'gap' : ''} ${k < at || (k === at && flying != null) ? 'done' : k === at ? 'cur' : ''}`} />
        ))}
      </span>
    </button>
  );
}

export default function Carnet({ stop, flight, lang, t, reduce, onOpen, onPage }) {
  const flying = flight?.shot ?? null; // le coup en vol (0 à 5), sinon null
  const at = flying ?? stop; // l'arrêt où repose la balle, ou d'où elle vient de partir
  const [roomy, setRoomy] = useState(hasRoom);
  const [folded, setFolded] = useState(readFolded);
  const [peek, setPeek] = useState(null); // le trou qu'on feuillette, s'il n'est pas celui de la balle
  const [cue, setCue] = useState({ holed: false, turned: false }); // pendant un putt : la balle est tombée ; la page a tourné
  const [height, setHeight] = useState(0);
  const planBox = useRef(null);

  useEffect(() => {
    const on = () => setRoomy(hasRoom());
    window.addEventListener('resize', on);
    return () => window.removeEventListener('resize', on);
  }, []);
  const fold = (value) => {
    setFolded(value);
    try {
      localStorage.setItem('carnet', value ? 'folded' : 'open');
    } catch {
      /* stockage indisponible */
    }
  };
  // La balle bouge : on revient à elle.
  useEffect(() => setPeek(null), [stop, flying]);
  useEffect(() => {
    if (flying == null) setCue({ holed: false, turned: false });
  }, [flying]);
  // Les deux seuls rendus React d'un vol : la balle tombe dans le trou ; la page tourne vers le trou suivant.
  const cueRef = useRef(cue);
  cueRef.current = cue;
  useFlight((s) => {
    if (s.leg == null) return;
    const shot = NEXT[s.leg];
    const holed = shot.leaves === 0 && s.t >= 1;
    const turned = STOPS[s.leg + 1].hole !== STOPS[s.leg].hole && (s.done || (shot.sync?.pageTurn != null && s.frame >= shot.sync.pageTurn));
    if (cueRef.current.holed !== holed || cueRef.current.turned !== turned) {
      cueRef.current = { holed, turned };
      setCue(cueRef.current);
    }
  });

  const holed = flying != null && cue.holed;
  const turned = flying != null && cue.turned;
  const page = roomy && !folded;
  // La page sait si le carnet est déplié : la ligne du tour s'arrête avant lui.
  useLayoutEffect(() => {
    onPage?.(page);
  }, [page, onPage]);
  // La zone de dessin prend la hauteur que la fenêtre laisse à la page.
  useLayoutEffect(() => {
    const el = planBox.current;
    if (!page || !el) return undefined;
    const read = () => setHeight(Math.max(200, Math.round(el.clientHeight)));
    read();
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, [page]);

  const ballHole = STOPS[turned ? stop : at].hole; // le trou où est la balle (la page tourne avant l'arrivée)
  const shown = peek ?? ballHole;
  const names = useMemo(() => STOPS.map((s) => shortName(s, lang, t)), [lang, t]);

  // Ce que la page dessine : en vol, le cadrage de l'arrêt quitté, la ligne du coup en train de s'écrire ;
  // à l'arrêt, le cadrage de l'arrêt (tout le trou, le coup à jouer, le green).
  const drawing = useMemo(() => {
    if (!page || !height) return null;
    const h = COURSE[shown - 1];
    const ctx = planCtx(h, lang, t);
    let name;
    let state;
    if (peek != null && peek !== ballHole) {
      name = 'hole';
      state = { stop: at };
    } else if (flying != null && !turned) {
      name = STOPS[flying].golf.view;
      state = { stop: flying, flight: { shot: flying - h.first } };
    } else {
      name = STOPS[stop].golf.view;
      state = { stop };
    }
    const d = pageView(h, name, PW, height, state, ctx);
    return { ...d, lang, label: `${t.holeMap} ${h.n}`, key: `${h.n}-${name}-${state.stop}-${state.flight ? 'vol' : 'pose'}-${lang}-${height}` };
  }, [page, height, shown, peek, ballHole, flying, turned, stop, at, lang, t]);

  if (!page) {
    const unfold = roomy && folded;
    return (
      <nav className={`carnet-tag ${unfold ? 'folded' : ''}`} aria-label={t.yardageBook}>
        <Tag at={at} flying={flying} turned={turned} lang={lang} t={t} onClick={unfold ? () => fold(false) : onOpen} label={unfold ? t.unfold : t.openBook} />
      </nav>
    );
  }

  const hole = HOLES[shown - 1];
  const greenView = peek == null && STOPS[flying != null && !turned ? flying : stop].golf.view === 'green';
  const brief = pick(hole.brief, lang);
  const light = pick(hole.light, lang);
  const wind = pick(hole.wind.label, lang);
  return (
    <nav className="carnet" aria-label={t.yardageBook}>
      <button type="button" className="carnet-fold" onClick={() => fold(true)} aria-label={t.fold} title={t.fold}>
        <Fold />
      </button>
      <div className="carnet-in">
      <Tabs at={at} flying={flying} holed={holed} shown={shown} lang={lang} t={t} onFlip={(n) => setPeek(n === ballHole ? null : n)} />
      {greenView ? (
        <p className="cond">
          <span>
            {t.green} · {hole.green.depth} × {hole.green.width} {t.metres}
          </span>
          <span>
            {t.pin}{' '}
            <b>
              {hole.pin.on} · {hole.pin.side} {pick(hole.pin.from, lang)}
            </b>
          </span>
        </p>
      ) : (
        <p className="cond">
          <span>{brief}</span>
          <span>
            {brief.length + light.length + wind.length <= 33 && `${light} · `}
            <b>{wind}</b>
          </span>
        </p>
      )}
      <div className="plan" ref={planBox}>
        {drawing && <Plan drawing={drawing} reduce={reduce} names={names} />}
      </div>
      {peek != null && peek !== ballHole ? (
        <HoleNotes key={`trou-${peek}`} hole={hole} lang={lang} t={t} onBack={() => setPeek(null)} />
      ) : flying != null ? (
        <LiveNotes key={`vol-${flying}`} k={flying} holed={holed} lang={lang} t={t} />
      ) : stop === LAST ? (
        <CardNotes key="carte" lang={lang} t={t} />
      ) : (
        <StopNotes key={`arret-${stop}`} k={stop} lang={lang} t={t} />
      )}
      </div>
    </nav>
  );
}
