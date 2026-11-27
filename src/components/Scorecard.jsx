// Le carnet de parcours ouvert : le sommaire du site, et sa version sans animation. Une double page
// sur papier (une page par trou) : le plan, l'encart du green, les six coups tracés et cotés, et la
// liste des coups, dont chaque ligne mène à son arrêt et dit le projet et son résultat. Sur la page de
// droite, la carte de score signée et l'invitation au contact. Dessous : le parcours, les
// savoir-faire, les certifications et le contact.
import { useEffect, useMemo, useRef, useState } from 'react';
import { COURSE, HOLES, LAST, NEXT, SITE, STOPS, num, pick, planCtx, shotInHole } from '../lib/content.js';
import { useDialog } from '../lib/dialog.js';
import { spreadViews } from '../lib/plan.js';
import { ContactLinks, EmailRow } from './Cards.jsx';
import { ArrowRight, Close, Flag, Txt } from './Icons.jsx';

const NARROW = '(max-width: 699px)'; // téléphone : une page par trou, dessins plus petits
const signed = (n) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : 'E');
const Art = ({ d, label }) => <svg viewBox={`0 0 ${d.w} ${d.h}`} width={d.w} height={d.h} role="group" aria-label={label} dangerouslySetInnerHTML={{ __html: d.svg }} />;

// Une ligne de la liste : le coup joué depuis l'arrêt k, le projet qu'on y lit et son résultat ; puis
// le club, le concept, et où la balle s'est posée (ou le score, quand elle tombe dans le trou).
function Stroke({ k, here, lang, t, onGo }) {
  const s = STOPS[k];
  const shot = NEXT[k];
  const project = s.kind === 'project';
  return (
    <li>
      <a className={`stroke ${here ? 'here' : ''}`} href={`#${s.id}`} onClick={(e) => onGo(e, k)} aria-current={here ? 'step' : undefined}>
        <span className="d">{shotInHole(k)}</span>
        <b className="name">{project ? s.name : SITE.meta.name}</b>
        <b className="dist">
          {num(shot.total, lang)} <small>{t.metres}</small>
        </b>
        <span className="res">{project ? <Txt>{pick(s.result, lang)}</Txt> : pick(s.title, lang)}</span>
        <span className="meta mono">
          <span>
            {pick(shot.club, lang)} · {project ? pick(s.concept, lang) : pick(shot.shot, lang)}
          </span>
          <i>{here ? t.youAreHere : shot.leaves ? pick(shot.lie, lang) : pick(HOLES[s.hole - 1].scoreName, lang)}</i>
        </span>
      </a>
    </li>
  );
}

function Leaf({ hole, stop, narrow, lang, t, onGo, children, extra, pager }) {
  const h = COURSE[hole.n - 1];
  const count = h.shots.length;
  const mark = stop >= h.first && stop < h.first + count ? stop - h.first : undefined;
  const art = useMemo(() => spreadViews(h, narrow ? 'narrow' : 'wide', mark, planCtx(h, lang, t)), [h, narrow, mark, lang, t]);
  const pin = `${hole.pin.on} · ${hole.pin.side} ${pick(hole.pin.from, lang)}`;
  // l'en-tête de la page : le tracé, puis la lumière si la ligne est assez courte, et le vent
  const shape = pick(hole.shape, lang);
  const light = pick(hole.light, lang);
  const wind = pick(hole.wind.label, lang);
  const roomy = !narrow && shape.length + light.length + wind.length <= 45;
  return (
    <section className="leaf" aria-label={`${t.hole} ${hole.n}`}>
      {pager}
      <header className="leaf-head">
        <span className="leaf-n">{hole.n}</span>
        <p className="leaf-t">
          <b>
            {t.par} {hole.par} · {hole.length} {t.metres}
          </b>
          <span>
            {narrow ? pick(hole.brief, lang) : shape}. {roomy ? `${light}, ${wind.toLowerCase()}` : wind}.
          </span>
        </p>
        <p className="leaf-s">
          <b>{hole.score}</b>
          <span>{pick(hole.scoreName, lang)}</span>
        </p>
      </header>
      <div className="leaf-body">
        <div className="leaf-plan">
          <div className="ink paper">
            <Art d={art.plan} label={`${t.holeMap} ${hole.n}`} />
          </div>
          {extra}
        </div>
        <div className="leaf-side">
          <div className="leaf-green">
            <p className="cap-line">
              <span>
                {t.green} ·{' '}
                <b>
                  {hole.green.depth} × {hole.green.width} {t.metres}
                </b>
              </span>
              <span>
                {t.pin} <b>{pin}</b>
              </span>
            </p>
            <div className="inset ink paper">
              <Art d={art.green} label={`${t.green} ${hole.n}`} />
            </div>
          </div>
          <div className="leaf-list">
            <ol className="strokes">
              {h.shots.map((s) => (
                <Stroke key={s.k} k={s.k} here={s.k === stop} lang={lang} t={t} onGo={onGo} />
              ))}
              {h.first + count === LAST && (
                <li>
                  <a className={`stroke last ${stop === LAST ? 'here' : ''}`} href={`#${STOPS[LAST].id}`} onClick={(e) => onGo(e, LAST)} aria-current={stop === LAST ? 'step' : undefined}>
                    <span className="d flagd">
                      <Flag />
                    </span>
                    <b className="name">{t.contact}</b>
                    <b className="dist">
                      {STOPS[LAST].golf.card.strokes} <small>{t.strokes.toLowerCase()}</small>
                    </b>
                    <span className="meta mono">
                      <span>
                        {t.holed} · {HOLES.filter((x) => x.score === x.par - 1).length} {t.birdies}
                      </span>
                      <i>{stop === LAST ? t.youAreHere : `${-STOPS[LAST].golf.card.toPar} ${t.underPar}`}</i>
                    </span>
                  </a>
                </li>
              )}
            </ol>
            {children}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function Scorecard({ open, stop, lang, t, onClose, onGo }) {
  const ref = useRef(null);
  const leaves = useRef(null);
  useDialog(ref, open, onClose);
  const [seen, setSeen] = useState(open); // les plans ne sont dessinés qu'à la première ouverture
  const [narrow, setNarrow] = useState(() => matchMedia(NARROW).matches);
  useEffect(() => {
    if (open) setSeen(true);
  }, [open]);
  useEffect(() => {
    const mq = matchMedia(NARROW);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  // Sur téléphone, le carnet s'ouvre à la page du trou où est la balle.
  useEffect(() => {
    const box = leaves.current;
    if (open && box && narrow) box.scrollTo({ left: STOPS[stop].hole > 1 ? box.scrollWidth : 0, behavior: 'instant' });
  }, [open, narrow, seen]); // eslint-disable-line react-hooks/exhaustive-deps
  // Un point de chute des plans : comme une ligne de la liste, il ferme le carnet et mène à son arrêt.
  const goPoint = (e) => {
    const a = e.target.closest?.('a.pt');
    if (a) onGo(e, Number(a.dataset.k));
  };
  const turn = (i) => leaves.current?.scrollTo({ left: i * leaves.current.clientWidth, behavior: 'smooth' });

  const par = HOLES.reduce((sum, h) => sum + h.par, 0);
  const contact = STOPS[LAST];
  const card = contact.golf.card;
  const { journey, skills, certifications } = SITE.about;
  const bunker = HOLES[0].bunkers?.find((b) => b.carry);
  const pager = (on) => (
    <p className="pager">
      {HOLES.map((h, i) => (
        <button key={h.n} type="button" className={i === on ? 'on' : ''} onClick={() => turn(i)} aria-label={`${t.flipTo} ${h.n}`} aria-pressed={i === on} />
      ))}
    </p>
  );
  return (
    <div className={`sheet-wrap full ${open ? 'open' : ''}`} inert={!open}>
      <section ref={ref} className="sheet card-sheet" role="dialog" aria-modal="true" aria-labelledby="card-title" tabIndex={-1}>
        <header className="sheet-head">
          <p className="kicker mono">{SITE.meta.name}</p>
          <h2 id="card-title" className="book-title">
            {t.yardageBook}
          </h2>
          <p className="book-hint mono" aria-hidden>
            {t.yardageBook} · {t.bookHint}
          </p>
          <a className="head-link mono" href={`#${contact.id}`} onClick={(e) => onGo(e, LAST)}>
            {t.contact}
            <ArrowRight />
          </a>
          <button type="button" className="close" onClick={onClose} aria-label={t.closeBook} data-autofocus>
            <Close />
          </button>
        </header>
        <div className="sheet-body" data-scroll>
          {seen && (
            <div className="book" ref={leaves} onClick={goPoint}>
              <Leaf
                hole={HOLES[0]}
                stop={stop}
                narrow={narrow}
                lang={lang}
                t={t}
                onGo={onGo}
                pager={pager(0)}
              >
                <p className="legend mono">
                  <span>
                    <svg width="9" height="9" viewBox="0 0 9 9" aria-hidden>
                      <circle cx="4.5" cy="4.5" r="3.4" fill="none" stroke="currentColor" />
                      <circle cx="4.5" cy="4.5" r="1" fill="currentColor" />
                    </svg>
                    {t.legendSprinkler}
                  </span>
                  {bunker && (
                    <span>
                      <b>
                        {bunker.reach} · {bunker.carry}
                      </b>{' '}
                      {t.legendBunker}
                    </span>
                  )}
                  <span>
                    <b>
                      {HOLES[0].pin.on} · {HOLES[0].pin.side} {pick(HOLES[0].pin.from, lang)}
                    </b>{' '}
                    {t.legendPin}
                  </span>
                </p>
              </Leaf>
              <Leaf
                hole={HOLES[1]}
                stop={stop}
                narrow={narrow}
                lang={lang}
                t={t}
                onGo={onGo}
                pager={pager(1)}
                extra={
                  <>
                    <table className="sc mono" aria-label={t.scorecard}>
                      <tbody>
                        <tr>
                          <th scope="row">{t.hole}</th>
                          {HOLES.map((h) => (
                            <td key={h.n}>{h.n}</td>
                          ))}
                          <td className="lab">{t.total}</td>
                        </tr>
                        <tr>
                          <th scope="row">{t.par}</th>
                          {HOLES.map((h) => (
                            <td key={h.n}>{h.par}</td>
                          ))}
                          <td>{par}</td>
                        </tr>
                        <tr className="score">
                          <th scope="row">{t.score}</th>
                          {HOLES.map((h) => (
                            <td key={h.n}>
                              <b>{h.score}</b>
                            </td>
                          ))}
                          <td className="tot">
                            {card.strokes}
                            <small>{signed(card.toPar)}</small>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                    <p className="sign">
                      <b>{SITE.meta.name}</b>
                      <span className="mono">{pick(card.label, lang)}</span>
                    </p>
                  </>
                }
              >
                <p className="invite">
                  {pick(contact.title, lang)}
                  <a className="mono" href={`#${contact.id}`} onClick={(e) => onGo(e, LAST)}>
                    {contact.email} <ArrowRight />
                  </a>
                </p>
                <p className="legend mono">
                  <span>
                    <svg width="12" height="9" viewBox="0 0 12 9" aria-hidden>
                      <path d="M1 7.5 10 2M6.5 1.6 10 2 8.6 5.3" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    {t.legendSlope}
                  </span>
                  <span>
                    <b>×</b> {t.legendLand}
                  </span>
                </p>
              </Leaf>
            </div>
          )}

          <div className="wide">
            <section className="about">
              <h3 className="mono">{t.journey}</h3>
              <ol className="journey">
                {journey.map((j) => (
                  <li key={j.id}>
                    <div>
                      <p className="j-org">
                        {pick(j.org, lang)}
                        {j.current && <span className="tag mono">{t.now}</span>}
                      </p>
                      <p className="j-role">{pick(j.role, lang)}</p>
                      <p className="j-text">{pick(j.text, lang)}</p>
                    </div>
                    <p className="j-when mono">{pick(j.period, lang)}</p>
                  </li>
                ))}
              </ol>
            </section>

            <section className="about">
              <h3 className="mono">{t.skills}</h3>
              <ul className="skills">
                {skills.map((s) => (
                  <li key={s.id}>
                    <p className="s-name">{pick(s.name, lang)}</p>
                    <p className="s-text">{pick(s.text, lang)}</p>
                    <p className="s-items mono">{s.items.join(' · ')}</p>
                  </li>
                ))}
              </ul>
            </section>

            <section className="about">
              <h3 className="mono">{t.certifications}</h3>
              <ul className="certs">
                {certifications.map((c) => (
                  <li key={c.id}>
                    <span>{pick(c.title, lang)}</span>
                    <span className="mono">{pick(c.issuer, lang)}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="about">
              <h3 className="mono">{t.contact}</h3>
              <div>
                <p className="about-lede">{pick(contact.body, lang)}</p>
                <div className="row">
                  <EmailRow email={contact.email} t={t} />
                </div>
                <ContactLinks links={contact.links} t={t} />
              </div>
            </section>

            <p className="credits mono">{t.credits}</p>
          </div>
        </div>
      </section>
    </div>
  );
}
