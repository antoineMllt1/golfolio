// Le plan du trou, vu du dessus : départ, fairway, bunkers, green, eau. La balle y occupe la place de
// l'arrêt courant et avance coup après coup ; chaque point mène à son arrêt.
import { COURSE, VIEW } from '../lib/course.js';
import { STOPS, holeOf, stopName, strokeLine } from '../lib/content.js';

function Hole({ c, on, stop, lang, t }) {
  const ids = Object.keys(c.spots).map(Number);
  const first = ids[0];
  const last = ids[ids.length - 1];
  // La balle : à sa place sur ce trou ; avant, au départ ; après, au fond du trou.
  const ball = stop < first ? c.spots[first] : stop > last ? c.pin : c.spots[stop];
  // Les coups, un segment par coup : d'un point au suivant, puis jusqu'au trou.
  const points = [...ids.map((k) => c.spots[k]), ...(c.spots[last][0] === c.pin[0] && c.spots[last][1] === c.pin[1] ? [] : [c.pin])];
  const { green, tee, pin } = c;
  return (
    <svg className={`hole ${on ? 'on' : ''}`} viewBox={`0 0 ${VIEW.w} ${VIEW.h}`} aria-hidden={!on}>
      <path className="rough" d={c.rough} />
      {c.water && <path className="water" d={c.water} />}
      {c.waves?.map((d) => <path key={d} className="wave" d={d} />)}
      <path className="fairway" d={c.fairway} />
      <ellipse className="green" cx={green.cx} cy={green.cy} rx={green.rx} ry={green.ry} transform={`rotate(${green.rot} ${green.cx} ${green.cy})`} />
      {c.bunkers.map((d) => (
        <path key={d} className="bunker" d={d} />
      ))}
      <rect className="tee" x={tee.x} y={tee.y} width={tee.w} height={tee.h} rx="1.5" transform={`rotate(${tee.rot} ${tee.x + tee.w / 2} ${tee.y + tee.h / 2})`} />
      {points.slice(1).map((p, i) => (
        <path key={`${p[0]}-${p[1]}`} className={`shot ${stop > first + i ? 'on' : ''}`} d={`M${points[i][0]} ${points[i][1]}L${p[0]} ${p[1]}`} pathLength="1" />
      ))}
      <path className="flag" d={`M${pin[0]} ${pin[1]}v-15l8 3.2-8 3.2`} />
      <circle className="cup" cx={pin[0]} cy={pin[1]} r="1.5" />
      {ids.map((k) => (
        <a key={k} href={`#${STOPS[k].id}`} aria-label={`${t.goTo} ${stopName(STOPS[k], lang, t)}`} aria-current={k === stop ? 'true' : undefined} tabIndex={on ? undefined : -1}>
          <circle className="hit" cx={c.spots[k][0]} cy={c.spots[k][1]} r="9" />
          <circle className={`spot ${k <= stop ? 'done' : ''}`} cx={c.spots[k][0]} cy={c.spots[k][1]} r="1.9" />
        </a>
      ))}
      <g className="ball" style={{ transform: `translate(${ball[0]}px, ${ball[1]}px)` }}>
        <circle className="ring" r="6.2" />
        <circle className="dot" r="2.9" />
      </g>
    </svg>
  );
}

export default function HoleMap({ stop, flight, lang, t }) {
  const current = STOPS[stop];
  const hole = holeOf(current);
  return (
    <nav className="map" aria-label={`${t.holeMap} · ${t.stops}`} style={{ '--move': flight?.shot != null ? '1.5s' : '0.5s' }}>
      <p className="map-head mono">
        <b>
          {t.hole}&nbsp;{hole.n}
        </b>
        <span>
          {t.par}&nbsp;{hole.par}
          <i>
            {' · '}
            {hole.length}&nbsp;{t.metres}
          </i>
        </span>
      </p>
      <div className="map-art">
        {COURSE.map((c) => (
          <Hole key={c.n} c={c} on={c.n === hole.n} stop={stop} lang={lang} t={t} />
        ))}
      </div>
      <p className="map-foot mono">{strokeLine(current.stroke, t, lang)}</p>
    </nav>
  );
}
