// La pastille du coup, toujours visible en bas à gauche. Ligne du haut : le club et ce que la balle a
// devant elle (« Coup suivant · Fer long · 234 m » ; au putter « Putter · 3 m pour birdie »). Ligne du
// bas : le nom du projet où le coup mène, puis son concept en plus clair. Pendant un vol elle sert à
// sauter à l'arrivée ; au contact, à rejouer le parcours. À côté, de quoi revenir d'un coup en arrière.
import { LAST, NEXT, STOPS, facing, isPutt, pick, shortName, stopName, toParAfter } from '../lib/content.js';
import { ArrowDown, ArrowUp, Replay, Skip } from './Icons.jsx';

export default function NextShot({ stop, flight, lang, t, onNext, onPrev, onReplay, onSkip }) {
  const flying = flight?.shot != null;
  const last = stop === LAST;
  let lead = ''; // le début de l'étiquette, en gris
  let fact; // la suite, en clair
  let name; // le projet où le coup mène
  let brief = ''; // le même en court, quand la place manque
  let aside = ''; // son concept
  let action = onNext;
  let icon = <ArrowDown />;
  let say; // le libellé lu par les lecteurs d'écran
  if (flying) {
    // un putt ne vole pas : « En route », et rien n'« atterrit »
    const rolls = isPutt(NEXT[flight.shot]);
    lead = rolls ? t.rolling : t.inFlight;
    fact = pick(NEXT[flight.shot].club, lang);
    name = rolls ? t.skipRoll : t.skipFlight;
    action = onSkip;
    icon = <Skip />;
    say = `${lead}. ${name}`;
  } else if (last) {
    const card = STOPS[LAST].golf.card;
    lead = t.roundOver;
    fact = `${card.strokes} ${t.strokes}, ${toParAfter(STOPS[LAST].hole)}`;
    name = t.replay;
    action = onReplay;
    icon = <Replay />;
    say = `${t.roundOver}. ${t.replay}`;
  } else {
    const shot = NEXT[stop];
    const to = STOPS[stop + 1];
    const club = pick(shot.club, lang);
    const ahead = facing(stop, lang, t);
    lead = isPutt(shot) ? '' : t.next;
    fact = `${club} · ${ahead}`;
    name = stopName(to, lang, t);
    brief = shortName(to, lang, t);
    aside = to.kind === 'project' ? pick(to.concept, lang) : pick(shot.shot, lang);
    say = `${t.next}${lang === 'fr' ? ' :' : ':'} ${club}, ${ahead}. ${name} — ${aside}`;
  }
  const long = lead.length + fact.length > 28; // sur téléphone, « Coup suivant » cède alors la place
  const before = stop > 0 && !flight ? stopName(STOPS[stop - 1], lang, t) : '';
  const prev = before ? `${t.prev}${lang === 'fr' ? ' :' : ':'} ${before}` : t.prev;
  return (
    <div className={`shots ${flying ? 'flying' : ''}`}>
      <button type="button" className="shot-prev" onClick={onPrev} disabled={stop === 0 || !!flight} aria-label={prev} title={prev}>
        <ArrowUp />
      </button>
      <button type="button" className="shot-next" onClick={action} aria-label={say}>
        <span className="shot-text">
          <span className={`mono ${long ? 'long' : ''} ${flying ? 'live' : ''}`}>
            {lead && (
              <span className="lead">
                {lead}
                <i> · </i>
              </span>
            )}
            <b>{fact}</b>
          </span>
          <span className="shot-line">
            <b>
              {brief && brief !== name ? (
                <>
                  <span className="full">{name}</span>
                  <span className="brief">{brief}</span>
                </>
              ) : (
                name
              )}
            </b>
            {aside && <i>{aside}</i>}
          </span>
        </span>
        <span className="shot-icon">{icon}</span>
      </button>
    </div>
  );
}
