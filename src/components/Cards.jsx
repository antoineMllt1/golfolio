// Les fiches posées sur le film : l'accueil, un projet par arrêt, le contact. Une seule est visible à
// la fois ; elle monte bloc après bloc une fois l'image posée.
import { useState } from 'react';
import { SITE, pick, projectOf, tourLine } from '../lib/content.js';
import { ArrowDown, ArrowOut, R, Txt } from './Icons.jsx';

const Card = ({ stop, on, kind, children }) => (
  <section className={`card ${kind} ${on ? 'on' : ''}`} data-card={stop.id} inert={!on} aria-hidden={!on}>
    <div className="copy">{children}</div>
  </section>
);

export function IntroCard({ stop, on, lang, t, reduce, onPlay, onProjects }) {
  return (
    <Card stop={stop} on={on} kind="intro">
      <R i={0} as="p" className="kicker mono">
        <span>{tourLine(t)}</span>
        <i className="sep" aria-hidden />
        <span className="golf">{pick(stop.label, lang)}</span>
      </R>
      <h1 data-focus tabIndex={-1}>
        <R i={1} as="span" className="name">
          {SITE.meta.name}
        </R>
        <R i={2} as="span" className="role">
          {pick(stop.title, lang)}
        </R>
      </h1>
      <R i={3} as="p" className="lede">
        {pick(stop.body, lang)}
      </R>
      <R i={4} className="row">
        <button type="button" className="btn primary" onClick={onPlay}>
          {t.play}
          <ArrowDown />
        </button>
        <button type="button" className="btn" onClick={onProjects}>
          {t.seeProjects}
        </button>
      </R>
      <R i={5} as="p" className="hint mono">
        {reduce ? t.reducedMotion : t.hint}
      </R>
    </Card>
  );
}

export function ProjectCard({ stop, on, lang, t, onCase }) {
  const { code, demo } = stop.links || {};
  return (
    <Card stop={stop} on={on} kind="project">
      <R i={0} as="p" className="kicker mono">
        <span>{projectOf(stop, t)}</span>
        <i className="sep" aria-hidden />
        <span className="golf">{pick(stop.label, lang)}</span>
      </R>
      <R i={1} as="h2" data-focus tabIndex={-1}>
        {stop.name}
      </R>
      <R i={2} as="p" className="concept">
        {pick(stop.concept, lang)}
      </R>
      <R i={3} as="p" className="lede">
        {pick(stop.sentence, lang)}
      </R>
      <R i={4} className="result">
        <span className="mono">{t.result}</span>
        <strong>
          <Txt>{pick(stop.result, lang)}</Txt>
        </strong>
      </R>
      <R i={5} as="ul" className="tools mono" aria-label={t.tools}>
        {stop.tools.map((tool) => (
          <li key={tool}>{tool}</li>
        ))}
      </R>
      <R i={6} className="row">
        <button type="button" className="btn primary" onClick={onCase} aria-haspopup="dialog">
          {t.caseStudy}
        </button>
        {code && (
          <a className="btn" href={code} target="_blank" rel="noreferrer" aria-label={`${t.viewCode} (${t.newTab})`}>
            {t.code}
            <ArrowOut />
          </a>
        )}
        {demo && (
          <a className="btn" href={demo} target="_blank" rel="noreferrer" aria-label={`${t.viewDemo} (${t.newTab})`}>
            {t.demo}
            <ArrowOut />
          </a>
        )}
      </R>
    </Card>
  );
}

// « https://github.com/quelquun » → « github.com/quelquun »
export const shortUrl = (url) => {
  try {
    const u = new URL(url);
    return (u.hostname.replace(/^www\./, '') + u.pathname).replace(/\/$/, '');
  } catch {
    return url;
  }
};
export const linkLabel = (link, t) => (link.id === 'portfolio' ? t.fullPortfolio : link.label);

export function ContactLinks({ links, t }) {
  return (
    <ul className="links">
      {links.map((l) => (
        <li key={l.url}>
          <a href={l.url} target="_blank" rel="noreferrer" aria-label={`${linkLabel(l, t)} (${t.newTab})`}>
            <span>{linkLabel(l, t)}</span>
            <span className="mono">
              {shortUrl(l.url)}
              <ArrowOut />
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

export function EmailRow({ email, t }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(email);
      setCopied(true);
      setTimeout(() => setCopied(false), 2400);
    } catch {
      /* presse-papiers indisponible : le lien e-mail reste là */
    }
  };
  return (
    <>
      <a className="btn primary" href={`mailto:${email}`} aria-label={`${t.writeEmail} : ${email}`}>
        {email}
      </a>
      <button type="button" className="btn btn-copy" onClick={copy}>
        <span aria-live="polite">{copied ? t.copied : t.copyEmail}</span>
      </button>
    </>
  );
}

export function ContactCard({ stop, on, lang, t }) {
  return (
    <Card stop={stop} on={on} kind="contact">
      <R i={0} as="p" className="kicker mono">
        {pick(stop.label, lang)}
      </R>
      <R i={1} as="h2" data-focus tabIndex={-1}>
        {pick(stop.title, lang)}
      </R>
      <R i={2} as="p" className="lede">
        {pick(stop.body, lang)}
      </R>
      <R i={3} className="row">
        <EmailRow email={stop.email} t={t} />
      </R>
      <R i={4}>
        <ContactLinks links={stop.links} t={t} />
      </R>
      <R i={5} as="p" className="credits mono">
        {t.credits}
      </R>
    </Card>
  );
}
