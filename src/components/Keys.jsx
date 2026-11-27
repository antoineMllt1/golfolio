// Les raccourcis clavier : un petit « ? » au bout de la ligne du tour ouvre leur légende, posée à
// côté de la pastille du coup. La touche « ? » fait de même ; Échap la referme.
import { LAST } from '../lib/content.js';
import { ArrowDown, ArrowUp } from './Icons.jsx';

export default function Keys({ open, onToggle, t }) {
  return (
    <div className={`keys ${open ? 'open' : ''}`}>
      {open && (
        <ul className="legend mono" id="legend" aria-label={t.shortcuts}>
          <li>
            <kbd>
              <ArrowDown />
              <span className="sr-only">↓</span>
            </kbd>
            <kbd>{t.keySpace}</kbd>
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
      <button type="button" className="help mono" onClick={onToggle} aria-expanded={open} aria-controls="legend" aria-label={t.shortcuts} title={t.shortcuts}>
        ?
      </button>
    </div>
  );
}
