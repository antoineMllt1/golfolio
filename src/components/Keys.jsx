// Les raccourcis clavier : un petit « ? » posé au bout de la pastille du coup, dans le prolongement
// des deux commandes, ouvre leur légende, qui s'écrit à sa droite en colonnes alignées. La touche
// « ? » fait de même ; Échap la referme.
import { LAST } from '../lib/content.js';
import { ArrowDown, ArrowUp } from './Icons.jsx';

export default function Keys({ open, onToggle, t }) {
  return (
    <div className={`keys ${open ? 'open' : ''}`}>
      <button type="button" className="help mono" onClick={onToggle} aria-expanded={open} aria-controls="keys-legend" aria-label={t.shortcuts} title={t.shortcuts}>
        ?
      </button>
      {open && (
        <ul className="keys-legend mono" id="keys-legend" aria-label={t.shortcuts}>
          <li>
            <kbd>
              <ArrowDown />
              <span className="sr-only">↓</span>
            </kbd>
            {t.next}
          </li>
          <li>
            <kbd>
              <ArrowUp />
              <span className="sr-only">↑</span>
            </kbd>
            {t.keyBack}
          </li>
          <li>
            <kbd>1</kbd>
            <i aria-hidden>–</i>
            <kbd>{LAST + 1}</kbd>
            {t.keyStop}
          </li>
          <li>
            <kbd>E</kbd>
            {t.caseStudy}
          </li>
          <li>
            <kbd>C</kbd>
            {t.book}
          </li>
          <li>
            <kbd>{t.keyEsc}</kbd>
            {t.close}
          </li>
        </ul>
      )}
    </div>
  );
}
