// L'étude de cas d'un projet : un panneau qui glisse par-dessus le film (à droite sur ordinateur,
// plein écran sur téléphone) et défile normalement. Problème, ce qui a été construit, schéma de
// fonctionnement, résultat, rôle, liens. Fermeture : Échap, la croix, ou un clic à côté.
import { useRef } from 'react';
import { pick } from '../lib/content.js';
import { useDialog } from '../lib/dialog.js';
import { ArrowOut, Close, Txt } from './Icons.jsx';

const two = (n) => String(n).padStart(2, '0');

// Le schéma : les étapes dans l'ordre, reliées par des flèches (de la source à la sortie).
function Flow({ steps, lang }) {
  return (
    <ol className="flow">
      {steps.map((step, i) => (
        <li key={pick(step, 'fr')} className={i === steps.length - 1 ? 'out' : ''}>
          {i > 0 && (
            <svg className="flow-arrow" viewBox="0 0 40 12" aria-hidden>
              <path d="M0 6h37M32 1.5 37.5 6 32 10.5" />
            </svg>
          )}
          <div className="flow-step">
            <span className="mono">{two(i + 1)}</span>
            <span>{pick(step, lang)}</span>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function CaseStudy({ stop, open, lang, t, onClose }) {
  const ref = useRef(null);
  useDialog(ref, open, onClose);
  const c = stop?.case;
  const { code, demo } = stop?.links || {};
  return (
    <div className={`sheet-wrap ${open ? 'open' : ''}`} inert={!open}>
      <div className="sheet-shade" onClick={onClose} aria-hidden />
      <aside ref={ref} className="sheet case" role="dialog" aria-modal="true" aria-labelledby="case-title" tabIndex={-1}>
        {stop && c && (
          <>
            <header className="sheet-head">
              <p className="kicker mono">
                {t.caseStudy}
                <span className="extra"> · {pick(stop.label, lang)}</span>
              </p>
              <button type="button" className="close" onClick={onClose} aria-label={t.closeCase} data-autofocus>
                <Close />
              </button>
            </header>
            <div className="sheet-body" data-scroll>
              <h2 id="case-title">{stop.name}</h2>
              <p className="case-lede">{pick(stop.sentence, lang)}</p>
              <dl className="case-facts">
                <div>
                  <dt className="mono">{t.concept}</dt>
                  <dd>{pick(stop.concept, lang)}</dd>
                </div>
                <div>
                  <dt className="mono">{t.result}</dt>
                  <dd>
                    <Txt>{pick(stop.result, lang)}</Txt>
                  </dd>
                </div>
                <div>
                  <dt className="mono">{t.tools}</dt>
                  <dd>{stop.tools.join(' · ')}</dd>
                </div>
              </dl>
              <section>
                <h3 className="mono">{t.problem}</h3>
                <p>{pick(c.problem, lang)}</p>
              </section>
              <section>
                <h3 className="mono">{t.built}</h3>
                <ol className="built">
                  {c.built.map((item, i) => (
                    <li key={pick(item, 'fr')}>
                      <span className="mono">{two(i + 1)}</span>
                      <p>{pick(item, lang)}</p>
                    </li>
                  ))}
                </ol>
              </section>
              <section>
                <h3 className="mono">{t.flow}</h3>
                <Flow steps={c.flow} lang={lang} />
              </section>
              <section>
                <h3 className="mono">{t.outcome}</h3>
                <p className="case-outcome">{pick(c.outcome, lang)}</p>
              </section>
              <section>
                <h3 className="mono">{t.role}</h3>
                <p>{pick(c.role, lang)}</p>
              </section>
              <section>
                <h3 className="mono">{t.links}</h3>
                {code || demo ? (
                  <div className="row">
                    {demo && (
                      <a className="btn primary" href={demo} target="_blank" rel="noreferrer" aria-label={`${t.viewDemo} (${t.newTab})`}>
                        {t.viewDemo}
                        <ArrowOut />
                      </a>
                    )}
                    {code && (
                      <a className={`btn ${demo ? '' : 'primary'}`} href={code} target="_blank" rel="noreferrer" aria-label={`${t.viewCode} (${t.newTab})`}>
                        {t.viewCode}
                        <ArrowOut />
                      </a>
                    )}
                  </div>
                ) : (
                  <p className="muted">{t.noLink}</p>
                )}
              </section>
              <button type="button" className="btn back" onClick={onClose}>
                {t.resume}
              </button>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
