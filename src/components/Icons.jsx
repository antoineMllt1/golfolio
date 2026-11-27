// Les quelques pictogrammes du site, dessinés au trait (ils prennent la couleur du texte).
const base = { viewBox: '0 0 16 16', fill: 'none', stroke: 'currentColor', strokeWidth: 1.4, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true };

export const ArrowDown = (p) => (
  <svg {...base} {...p}>
    <path d="M8 2.5v11M3.5 9 8 13.5 12.5 9" />
  </svg>
);
export const ArrowUp = (p) => (
  <svg {...base} {...p}>
    <path d="M8 13.5v-11M3.5 7 8 2.5 12.5 7" />
  </svg>
);
export const ArrowRight = (p) => (
  <svg {...base} {...p}>
    <path d="M2.5 8h11M9 3.5 13.5 8 9 12.5" />
  </svg>
);
export const ArrowOut = (p) => (
  <svg {...base} {...p}>
    <path d="M4.5 11.5l7-7M5.5 4.5h6v6" />
  </svg>
);
export const Close = (p) => (
  <svg {...base} {...p}>
    <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" />
  </svg>
);
export const Replay = (p) => (
  <svg {...base} {...p}>
    <path d="M3 8a5 5 0 1 0 1.6-3.7M3 2.5v2.6h2.6" />
  </svg>
);
// Un carnet ouvert : le bouton du carnet de parcours, le sommaire du site.
export const Book = (p) => (
  <svg {...base} strokeWidth={1.2} {...p}>
    <path d="M8 3.6C6.6 2.7 4.6 2.4 2.5 2.6v9.6c2.1-.2 4.1.1 5.5 1 1.4-.9 3.4-1.2 5.5-1V2.6c-2.1-.2-4.1.1-5.5 1ZM8 3.6v9.6" />
  </svg>
);
// Un chevron : replier la page du carnet vers le bord.
export const Fold = (p) => (
  <svg {...base} {...p}>
    <path d="M6 3.5 10.5 8 6 12.5" />
  </svg>
);
// Le drapeau du trou : la pastille du contact.
export const Flag = (p) => (
  <svg viewBox="0 0 10 12" fill="currentColor" stroke="currentColor" strokeWidth={1} strokeLinejoin="round" strokeLinecap="round" aria-hidden {...p}>
    <path d="M2 11V1.2l6 2.4-6 2.4" />
  </svg>
);

// Dans un texte, « → » devient une flèche dessinée (le caractère manque aux polices du site) ;
// les lecteurs d'écran gardent le caractère.
export function Txt({ children }) {
  return String(children)
    .split('→')
    .map((part, i) => (
      <span key={`${i}-${part}`}>
        {i > 0 && (
          <>
            <span className="sr-only">→</span>
            <ArrowRight className="inline-arrow" />
          </>
        )}
        {part}
      </span>
    ));
}

// Un bloc qui monte à son tour quand la fiche apparaît (--i : son rang).
export const R = ({ i = 0, as: Tag = 'div', className = '', ...rest }) => <Tag className={`r ${className}`} style={{ '--i': i }} {...rest} />;
