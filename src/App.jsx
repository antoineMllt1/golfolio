// La page : sept arrêts posés sur un film pré-rendu. Un geste (molette, balayage, flèche, bouton)
// joue un coup : le film suit la balle jusqu'à l'arrêt suivant, puis la fiche monte. Deux panneaux
// s'ouvrent par-dessus : l'étude de cas du projet courant, et la carte de score (le sommaire).
import { useCallback, useEffect, useRef, useState } from 'react';
import { LAST, SITE, STOPS, indexOfId, initialLang, pick, saveLang, stopName } from './lib/content.js';
import { Film, pickSizes, savesData } from './lib/film.js';
import { useShotInput } from './lib/input.js';
import CaseStudy from './components/CaseStudy.jsx';
import { ContactCard, IntroCard, ProjectCard } from './components/Cards.jsx';
import HoleMap from './components/HoleMap.jsx';
import { Card as CardIcon } from './components/Icons.jsx';
import NextShot, { Flight } from './components/NextShot.jsx';
import Scorecard from './components/Scorecard.jsx';

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const startIndex = () => Math.max(0, indexOfId(location.hash.slice(1)));

export default function App() {
  const [lang, setLangState] = useState(initialLang);
  const t = SITE.ui[lang];
  const [reduce] = useState(() => matchMedia('(prefers-reduced-motion: reduce)').matches);
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const [stop, setStop] = useState(startIndex); // l'arrêt courant, ou visé pendant un déplacement
  const [flight, setFlight] = useState(null); // null au repos ; { shot } pendant un déplacement (shot : le coup joué, ou null pour un fondu)
  const [panel, setPanel] = useState(null); // null, 'case' ou 'card'
  const [caseStop, setCaseStop] = useState(null);

  const canvasRef = useRef(null);
  const filmRef = useRef(null);
  const stopRef = useRef(stop);
  const flightRef = useRef(null);
  const panelRef = useRef(null);
  const moveRef = useRef(0);
  panelRef.current = panel;

  const setLang = (next) => {
    setLangState(next);
    saveLang(next);
  };
  const current = STOPS[stop];

  // Langue et titre de la page : un titre par arrêt.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = current.kind === 'intro' ? pick(SITE.meta.title, lang) : `${stopName(current, lang, t)} · ${SITE.meta.name}`;
  }, [lang, current, t]);

  // ---- le film
  useEffect(() => {
    let cancelled = false;
    let film;
    fetch('/frames/manifest.json')
      .then((r) => r.json())
      .then((manifest) => {
        if (cancelled) return;
        film = new Film(canvasRef.current, {
          manifest,
          sizes: pickSizes(manifest),
          reduce,
          still: reduce || savesData(),
          start: stopRef.current,
          onReady: () => setReady(true),
          onProgress: setProgress,
        });
        filmRef.current = film;
      })
      .catch(() => {
        // Sans film, le site reste lisible : les fiches, sur le fond.
        setReady(true);
        setProgress(1);
      });
    return () => {
      cancelled = true;
      film?.dispose();
      filmRef.current = null;
    };
  }, [reduce]);

  // ---- déplacements
  const setFlying = (value) => {
    flightRef.current = value;
    setFlight(value);
  };

  // Aller à un arrêt. Un geste pendant qu'un trajet joue saute à son arrivée ; un choix explicite
  // (carte de score, plan du trou, lien direct) remplace le déplacement en cours.
  const go = useCallback((to, gesture = false) => {
    const target = clamp(to, 0, LAST);
    const film = filmRef.current;
    if (flightRef.current && gesture) {
      film?.skip();
      return;
    }
    const from = stopRef.current;
    if (target === from && !flightRef.current) return;
    moveRef.current += 1;
    const id = moveRef.current;
    stopRef.current = target;
    setStop(target);
    history.replaceState(null, '', target ? `#${STOPS[target].id}` : location.pathname + location.search);
    const land = () => {
      if (moveRef.current === id) setFlying(null);
    };
    if (!film) return;
    setFlying({ shot: null });
    if (film.go(target, land)) setFlying({ shot: from });
  }, []);

  useShotInput({
    blocked: () => !!panelRef.current,
    step: (d) => go(stopRef.current + d, true),
    jump: (where) => go(where === 'first' ? 0 : LAST),
  });

  // Un lien direct (#payfit), tapé dans la barre d'adresse ou cliqué dans la page, mène à son arrêt.
  useEffect(() => {
    const onHash = () => {
      const i = location.hash.length > 1 ? indexOfId(location.hash.slice(1)) : 0;
      if (i < 0) return;
      setPanel(null);
      go(i);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, [go]);

  // ---- panneaux
  const openCase = () => {
    setCaseStop(current);
    setPanel('case');
  };
  const closePanel = useCallback(() => setPanel(null), []);
  // Une ligne de la carte de score : on ferme la carte, puis on va à l'arrêt.
  const goFromCard = (e, k) => {
    e.preventDefault();
    setPanel(null);
    go(k);
  };

  // ---- focus : quand la fiche arrive et que le focus n'est plus nulle part (le bouton cliqué a
  // disparu avec l'ancienne fiche), il va sur le titre de la nouvelle. Sinon il reste où il est.
  const settled = !flight;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    if (!settled || panelRef.current) return;
    const active = document.activeElement;
    if (active && active !== document.body && !active.closest('[inert]')) return;
    document.querySelector(`[data-card="${STOPS[stop].id}"] [data-focus]`)?.focus({ preventScroll: true });
  }, [settled, stop]);

  const skipToContent = (e) => {
    e.preventDefault();
    document.querySelector(`[data-card="${current.id}"] [data-focus]`)?.focus({ preventScroll: true });
  };

  const loading = progress < 0.999;
  return (
    <div className={`app at-${current.kind} ${ready ? 'ready' : ''} ${flight ? 'moving' : ''} ${flight?.shot != null ? 'flying' : ''}`}>
      <a href="#main" className="skip" onClick={skipToContent}>
        {t.skip}
      </a>
      <div className="backdrop" aria-hidden>
        <img className="poster" src="/frames/poster.webp" alt="" />
        <canvas ref={canvasRef} className="stage" />
        <div className="scrim" />
      </div>
      {loading && (
        <div
          className="progress"
          role="progressbar"
          aria-label={t.loadingFilm}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          style={{ transform: `scaleX(${progress})` }}
        />
      )}

      <div className="shell" inert={!!panel}>
        <header className="top">
          <a className="brand" href="#depart" aria-label={`${SITE.meta.name} · ${t.home}`}>
            {SITE.meta.name}
          </a>
          <div className="top-right">
            <button type="button" className="top-card mono" onClick={() => setPanel('card')} aria-haspopup="dialog">
              <CardIcon />
              {t.scorecard}
            </button>
            <button type="button" className="top-lang mono" onClick={() => setLang(lang === 'fr' ? 'en' : 'fr')} aria-label={t.langSwitch} title={t.langSwitch}>
              <span className={lang === 'fr' ? 'on' : ''}>FR</span>
              <i aria-hidden>/</i>
              <span className={lang === 'en' ? 'on' : ''}>EN</span>
            </button>
          </div>
        </header>

        <main id="main">
          {STOPS.map((s, k) => {
            const on = k === stop && settled;
            if (s.kind === 'intro') return <IntroCard key={s.id} stop={s} on={on} lang={lang} t={t} reduce={reduce} onPlay={() => go(1)} onProjects={() => setPanel('card')} />;
            if (s.kind === 'contact') return <ContactCard key={s.id} stop={s} on={on} lang={lang} t={t} />;
            return <ProjectCard key={s.id} stop={s} on={on} lang={lang} t={t} onCase={openCase} />;
          })}
        </main>

        <Flight flight={flight} lang={lang} t={t} />
        <NextShot
          stop={stop}
          flight={flight}
          lang={lang}
          t={t}
          onNext={() => go(stopRef.current + 1)}
          onPrev={() => go(stopRef.current - 1)}
          onReplay={() => go(0)}
          onSkip={() => filmRef.current?.skip()}
        />
        <HoleMap stop={stop} flight={flight} lang={lang} t={t} />
        <p className="sr-only" aria-live="polite">
          {settled ? `${pick(current.label, lang)} — ${stopName(current, lang, t)}` : ''}
        </p>
      </div>

      <CaseStudy stop={caseStop} open={panel === 'case'} lang={lang} t={t} onClose={closePanel} />
      <Scorecard open={panel === 'card'} stop={stop} lang={lang} t={t} onClose={closePanel} onGo={goFromCard} />
    </div>
  );
}
