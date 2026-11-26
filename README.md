# Golfolio — portfolio d'Antoine Millot

Portfolio IA & data sur le thème du golf. On suit une balle sur deux trous : chaque coup ouvre un
projet, le dernier putt est le contact. Le film est pré-rendu dans Blender puis rejoué par la page,
image par image : un geste (molette, balayage, flèche, bouton) joue un coup.

Le plan complet est dans [`PLAN.md`](PLAN.md).

## Comment c'est fait

- **Le texte** : `content/site.json`, en français et en anglais. Le site n'écrit aucun texte lui-même.
- **Le film** : `public/frames/` (WebP) et son `manifest.json` — sept images d'arrêt nettes
  (`h_00` … `h_06`) et six trajets de 44 images (`l<k>_<nnnn>`), en trois tailles (`s`, `m`, `l`).
- **La page** (`src/`, Vite + React 19) :
  - `lib/film.js` lit le film sur un canvas : chargement dans l'ordre (affiche, arrêt courant,
    prochain trajet du grossier au fin, puis le reste), trajet à 27 images par seconde, image nette
    en fondu à l'arrivée, dérive lente à l'arrêt, fondu quand un trajet manque, recadrage autour de
    la balle sur téléphone ;
  - `lib/input.js` transforme molette, trackpad, tactile et clavier en « un geste = un coup » ;
  - `components/` : les fiches, l'étude de cas, la carte de score (le sommaire, et la version sans
    animation), le plan du trou, le bouton « Coup suivant » ;
  - `App.jsx` tient l'état : l'arrêt courant suit l'adresse (`#spendmap`), et un panneau ouvert
    (étude de cas, carte de score) ajoute une entrée d'historique, pour que le retour arrière du
    navigateur le ferme au lieu de quitter le site.
- **Les mises en page** (`src/styles.css`) : ordinateur ; écrans bas ; grands écrans (texte et
  commandes agrandis à partir de 1800 px de large) ; téléphone debout (film en haut recadré autour
  de la balle, fiche en bas) ; téléphone couché ou fenêtre de moins de 540 px de haut (fiche à
  gauche, « Coup suivant » en bas à droite).
- **Le serveur** (`server/index.js`, Express 5) sert `dist/`, répond à `/api/health` et écrit dans
  la page une version texte du site (projets, parcours, contact), le titre, la description, les
  balises de partage et les données structurées : tout est lisible sans JavaScript.

Animations réduites ou économiseur de données : pas de trajet ni de dérive, les arrêts
s'enchaînent en fondus courts.

## Lancer

```bash
npm install
npm run build
npm start              # http://localhost:3003  (PORT pour changer de port)
```

En développement : `npm run dev` (Vite sert tout ; la version texte du serveur n'y est pas).

Variables facultatives du serveur : `PORT`, `PUBLIC_URL` (adresse publique utilisée dans les balises
de partage ; sur Railway elle est déduite de `RAILWAY_PUBLIC_DOMAIN`).

## Régénérer le film factice

Tant que le vrai rendu n'est pas là, `public/frames/` contient un film factice : des dégradés
étiquetés (arrêt ou trajet, numéro d'image) et un disque clair à la place de la balle.

```bash
pip install numpy pillow
npm run placeholder    # = python3 scripts/placeholder_frames.py
npm run build
```

Le script ne touche à rien si `public/frames/manifest.json` n'est pas celui d'un film factice
(`"placeholder": true`) : le vrai film, converti par `scripts/frames.py`, ne peut pas être écrasé.

## Crédits

Ciels et panoramas du film : Poly Haven, CC0. Polices : Instrument Serif, Inter et JetBrains Mono
(Google Fonts, licence SIL Open Font), servies depuis `public/fonts`.
