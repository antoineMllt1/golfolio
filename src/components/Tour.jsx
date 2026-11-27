// « Le tour » : la liste des sept arrêts, pour le téléphone et les petites fenêtres. Une feuille qui
// monte du bas de l'écran, à portée de pouce : la ligne du tour, debout. Chaque ligne est un lien
// vers son arrêt ; en bas, de quoi ouvrir le carnet de parcours.
import { Fragment, useRef } from 'react';
import { HOLES, LAST, NEXT, PROJECTS, STOPS, TOTAL_STROKES, metres, pick, stopName } from '../lib/content.js';
import { useDialog } from '../lib/dialog.js';
import { ArrowRight, Close } from './Icons.jsx';

// Le drapeau du dernier arrêt, le même que sur la ligne du tour.
const FlagMark = () => (
  <svg className="tour-flag" viewBox="0 0 12 17" fill="none" aria-hidden>
    <path d="M2.5 15.5V1.5" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
    <path d="M2.5 1.6 10 4.3 2.5 7z" fill="currentColor" />
    <circle cx="2.5" cy="15.5" r="1.4" fill="#0c1713" stroke="currentColor" strokeWidth="1" />
  </svg>
);

export default function Tour({ open, stop, lang, t, onClose, onGo, onBook }) {
  const ref = useRef(null);
  useDialog(ref, open, onClose);
  // à droite de chaque ligne : où repose la balle à cet arrêt
  const lie = (s, k) => {
    if (k === stop) return t.youAreHere;
    if (k === LAST) return pick(s.golf.lie, lang);
    const first = STOPS.findIndex((o) => o.hole === s.hole) === k;
    if (first) return k === 0 ? metres(s.golf.toPin, lang, t) : `${t.tee} · ${metres(s.golf.toPin, lang, t)}`;
    return `${pick(NEXT[k - 1].lie, lang)} · ${metres(s.golf.toPin, lang, t)}`;
  };
  const row = (s, k, i, n) => {
    const here = k === stop;
    const rank = PROJECTS.indexOf(s) + 1;
    return (
      <li key={s.id}>
        <a className={`tour-row ${here ? 'here' : ''} ${k < stop ? 'done' : ''} ${k === stop + 1 ? 'next' : ''} ${i === 0 ? 'first' : ''} ${i === n - 1 ? 'last' : ''}`} href={`#${s.id}`} onClick={(e) => onGo(e, k)} aria-current={here ? 'step' : undefined}>
          <span className="tour-g" aria-hidden>
            {here ? <i className="g-ball" /> : k === LAST ? <FlagMark /> : <i className={`${i === 0 ? 'g-tee' : 'g-dot'} ${k < stop ? 'done' : ''}`} />}
          </span>
          <span className="tour-txt">
            <span className="tour-name">{stopName(s, lang, t)}</span>
            <span className="tour-sub">
              {rank > 0 && <b>{rank}</b>}
              {s.kind === 'project' ? pick(s.concept, lang) : s.kind === 'intro' ? pick(s.title, lang) : s.email}
            </span>
          </span>
          <span className="tour-lie">{lie(s, k)}</span>
        </a>
      </li>
    );
  };
  return (
    <div className={`sheet-wrap tour-wrap ${open ? 'open' : ''}`} inert={!open}>
      <div className="sheet-shade" onClick={onClose} aria-hidden />
      <section ref={ref} className="tour" role="dialog" aria-modal="true" aria-labelledby="tour-title" tabIndex={-1}>
        <div className="tour-grab" aria-hidden />
        <header className="tour-head">
          <h2 id="tour-title">{t.tour}</h2>
          <span className="mono">
            {HOLES.length} {t.holes} · {TOTAL_STROKES} {t.strokes} · {PROJECTS.length} {t.projects}
          </span>
          <button type="button" className="tour-close" onClick={onClose} aria-label={t.closeTour} data-autofocus>
            <Close />
          </button>
        </header>
        <div className="tour-body" data-scroll>
          {HOLES.map((h) => {
            const rows = STOPS.map((s, k) => [s, k]).filter(([s]) => s.hole === h.n);
            const after = STOPS.findIndex((s) => s.hole > h.n);
            const finished = stop >= (after < 0 ? LAST : after);
            return (
              <Fragment key={h.n}>
                <p className="tour-hole">
                  <span>
                    {t.hole} {h.n} · {t.par} {h.par} · {h.length} {t.metres}
                  </span>
                  {finished && (
                    <span className="tour-score">
                      <em>{h.score}</em>
                      {pick(h.scoreName, lang)}
                    </span>
                  )}
                </p>
                <ol>{rows.map(([s, k], i) => row(s, k, i, rows.length))}</ol>
              </Fragment>
            );
          })}
        </div>
        <footer className="tour-foot">
          <button type="button" onClick={onBook}>
            {t.yardageBook}
            <ArrowRight />
          </button>
        </footer>
      </section>
    </div>
  );
}
