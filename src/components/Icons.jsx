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
// Une petite carte de score : le bouton du sommaire.
export const Card = (p) => (
  <svg {...base} {...p}>
    <rect x="2.5" y="3" width="11" height="10" rx="1.2" />
    <path d="M2.5 6.5h11M6.5 6.5V13M10 6.5V13" />
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
