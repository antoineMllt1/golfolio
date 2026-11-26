// Le bouton « Coup suivant », toujours visible : il annonce le coup à venir (club et intention),
// avec à côté de quoi revenir d'un coup en arrière. Pendant un vol, il sert à sauter à l'arrivée.
import { LAST, NEXT, STOPS, TOTAL_STROKES, pick } from '../lib/content.js';
import { ArrowDown, ArrowUp, Replay } from './Icons.jsx';

export default function NextShot({ stop, flight, lang, t, onNext, onPrev, onReplay, onSkip }) {
  const flying = flight?.shot != null;
  const last = stop === LAST;
  const next = NEXT[stop];
  let kicker;
  let line;
  let action = onNext;
  if (flying) {
    kicker = t.inFlight;
    line = t.skipFlight;
    action = onSkip;
  } else if (last) {
    kicker = t.backToStart;
    line = t.replay;
    action = onReplay;
  } else {
    kicker = `${t.next} · ${STOPS[stop].stroke + 1}/${TOTAL_STROKES}`;
    line = `${pick(next.club, lang)} — ${pick(next.shot, lang)}`;
  }
  return (
    <div className={`shots ${flying ? 'flying' : ''}`}>
      <button type="button" className="shot-prev" onClick={onPrev} disabled={stop === 0 || !!flight} aria-label={t.prev} title={t.prev}>
        <ArrowUp />
      </button>
      <button type="button" className="shot-next" onClick={action}>
        <span className="shot-text">
          <span className="mono">{kicker}</span>
          <span className="shot-line">{line}</span>
        </span>
        <span className="shot-icon">{last && !flying ? <Replay /> : <ArrowDown />}</span>
      </button>
    </div>
  );
}

// Pendant le vol, le coup joué s'affiche en bas à gauche, comme un titre de film.
export function Flight({ flight, lang, t }) {
  const k = flight?.shot;
  const shot = k != null ? NEXT[k] : null;
  return (
    <div className={`flight ${shot ? 'on' : ''}`} aria-hidden>
      {shot && (
        <>
          <p className="mono">
            {t.stroke}&nbsp;{k + 1}/{TOTAL_STROKES}
          </p>
          <p className="flight-club">{pick(shot.club, lang)}</p>
          <p className="flight-shot">{pick(shot.shot, lang)}</p>
        </>
      )}
    </div>
  );
}
