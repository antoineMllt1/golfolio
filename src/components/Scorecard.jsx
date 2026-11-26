// La carte de score : le sommaire du site, et sa version sans animation. Une vraie carte (trou, par,
// coup, club, projet, résultat) dont chaque ligne mène à son arrêt, puis le parcours, les savoir-faire,
// les certifications et le contact.
import { useRef } from 'react';
import { HOLES, LAST, NEXT, SITE, STOPS, STROKES_BY_HOLE, TOTAL_STROKES, pick } from '../lib/content.js';
import { useDialog } from '../lib/dialog.js';
import { ContactLinks, EmailRow } from './Cards.jsx';
import { ArrowRight, Close, Txt } from './Icons.jsx';

const signed = (n) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : 'E');

export default function Scorecard({ open, stop, lang, t, onClose, onGo }) {
  const ref = useRef(null);
  useDialog(ref, open, onClose);
  const par = HOLES.reduce((sum, h) => sum + h.par, 0);
  const contact = STOPS[LAST];
  const { journey, skills, certifications } = SITE.about;
  // Une ligne par coup : l'arrêt d'où il part, son club, et le projet qu'on y lit.
  // Comme sur une vraie carte, les coups se comptent par trou : le par 3 se joue en 1 puis 2.
  const row = (s, k) => (
    <li key={s.id}>
      <a className={`score-row ${k === stop ? 'here' : ''}`} href={`#${s.id}`} onClick={(e) => onGo(e, k)} aria-current={k === stop ? 'true' : undefined}>
        <span className="c-shot mono">{STOPS.slice(0, k).filter((x) => x.hole === s.hole).length + 1}</span>
        <span className="c-club mono">{pick(NEXT[k].club, lang)}</span>
        <span className="c-name">
          {s.kind === 'project' ? s.name : SITE.meta.name}
          <small>{s.kind === 'project' ? pick(s.concept, lang) : pick(s.title, lang)}</small>
        </span>
        <span className="c-result">{s.kind === 'project' ? <Txt>{pick(s.result, lang)}</Txt> : pick(NEXT[k].shot, lang)}</span>
        <ArrowRight className="c-go" />
      </a>
    </li>
  );
  return (
    <div className={`sheet-wrap full ${open ? 'open' : ''}`} inert={!open}>
      <section ref={ref} className="sheet card-sheet" role="dialog" aria-modal="true" aria-labelledby="card-title" tabIndex={-1}>
        <header className="sheet-head">
          <p className="kicker mono">{SITE.meta.name}</p>
          <a className="head-link mono" href={`#${contact.id}`} onClick={(e) => onGo(e, LAST)}>
            {t.contact}
            <ArrowRight />
          </a>
          <button type="button" className="close" onClick={onClose} aria-label={`${t.close} : ${t.scorecard}`} data-autofocus>
            <Close />
          </button>
        </header>
        <div className="sheet-body" data-scroll>
          <div className="wide">
            <h2 id="card-title">{t.scorecard}</h2>
            <p className="case-lede">{t.scorecardIntro}</p>

            <div className="paper">
              <div className="paper-head mono">
                <span>{pick(SITE.stops[0].title, lang)}</span>
                <span>{pick(contact.label, lang)}</span>
              </div>
              <div className="score-cols mono" aria-hidden>
                <span>{t.hole}</span>
                <span>{t.par}</span>
                <span>{t.stroke}</span>
                <span>{t.club}</span>
                <span>{t.project}</span>
                <span>{t.result}</span>
              </div>
              {HOLES.map((h, i) => {
                const diff = STROKES_BY_HOLE[i] - h.par;
                return (
                  <div className="score-hole" key={h.n}>
                    <p className="score-id">
                      <span className="sr-only">
                        {t.hole} {h.n}, {t.par} {h.par}, {h.length} {t.metres}
                      </span>
                      <span className="c-hole" aria-hidden>
                        {h.n}
                      </span>
                      <span className="c-par" aria-hidden>
                        {h.par}
                      </span>
                      <span className="c-len mono" aria-hidden>
                        {h.length}&nbsp;{t.metres}
                      </span>
                    </p>
                    <ol className="score-rows">{STOPS.map((s, k) => (s.hole === h.n && k < LAST ? row(s, k) : null))}</ol>
                    <p className="score-sum mono">
                      <span>
                        {t.hole}&nbsp;{h.n} · {t.par}&nbsp;{h.par}
                      </span>
                      <span className="score-mark">
                        <b className={diff < 0 ? 'under' : ''}>{STROKES_BY_HOLE[i]}</b>
                        {diff === -1 ? t.birdie : signed(diff)}
                      </span>
                    </p>
                  </div>
                );
              })}
              <a className="score-total" href={`#${contact.id}`} onClick={(e) => onGo(e, LAST)}>
                <span className="mono">
                  {t.total} · {t.par}&nbsp;{par}
                </span>
                <span className="score-big">
                  {TOTAL_STROKES}&nbsp;{t.strokes.toLowerCase()} <i>{signed(TOTAL_STROKES - par)}</i>
                </span>
                <span className="score-contact">
                  {t.contact}
                  <ArrowRight />
                </span>
              </a>
            </div>

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
