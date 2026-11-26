# Golfolio — plan d'action (version 3)

Portfolio IA & data d'Antoine Millot. On suit une balle de golf sur deux trous : chaque coup ouvre un
projet, le dernier putt est le contact. Film pré-rendu dans Blender, rejoué par la page, un geste =
un coup (méthode du guide et de `portfolio-3d`).

> **Deux trous, six coups, deux birdies.** Un par 5 puis un par 3. Sept arrêts : le départ, cinq
> projets, le contact.

Validé par Antoine le 26 novembre 2026 : « je me filmerai pas mais le reste fonce ».

---

## 1. Ce qui est décidé

| Sujet | Décision |
| --- | --- |
| Structure | Trou 1 : par 5 en 4 coups. Trou 2 : par 3 en 2 coups. 7 arrêts, 6 coups, 5 projets. |
| Image | Photoréaliste. La 3D ne montre que ce qu'elle réussit : gros plans de balle, de club, d'herbe, de sable, d'eau. Le décor et la lumière viennent de vrais panoramas photographiés (Poly Haven, CC0). Pas de parcours modélisé en plan large : les essais donnent un niveau simulateur de golf. |
| Le joueur | Pas de tournage, pas de personnage 3D (essayé jusqu'au swing capturé : mannequin). On voit la frappe en gros plan, puis Antoine de dos au finish, en silhouette à contre-jour tirée de sa photo de practice. Image à faire valider par lui avant toute mise en ligne. Droitier. |
| Suivre la balle | Chaque coup : frappe au ralenti en gros plan, la balle part, la caméra la suit dans le ciel, puis redescend là où elle se pose. Un plan du trou dessiné par la page montre où on en est. |
| Geste | Un geste = un coup. Un geste pendant le vol saute à l'arrivée. Retour en arrière : fondu. |
| Matériel | D'après ses références, sans logo de marque, monogramme « AM » : bois 3 noir à stries blanches (fait), fers en acier satiné à dos creusé et insert noir, wedge brossé, putter. Balle blanche « AM ». |
| Projets | SpendMap, BDD Licter × Fnac Darty, Hackathon PayFit, Revenue Engine Hackathon, Estimia. Le plus fort pour un poste en IA d'abord, la démo en ligne juste avant le contact. |
| Titre | « AI Engineer & Data Analyst » (un mot d'Antoine suffit pour inverser). |
| Langues | Français et anglais. |
| Mise en ligne | Railway, service `golfolio` du projet `Portfolio-Pro`, domaine `golfolio-production.up.railway.app`. |

---

## 2. Le parcours

| # | id | Où est la balle | Lumière | Ce qui s'affiche | Le geste joue |
| --- | --- | --- | --- | --- | --- |
| 0 | `depart` | Trou 1, par 5, sur le tee | Aube, brume | Qui est Antoine | Coup 1 : mise en jeu au bois 3 |
| 1 | `spendmap` | Fairway, dans la rosée | Matin | Projet 1, SpendMap | Coup 2 : fer long vers le green |
| 2 | `fnac-darty` | Bord du green | Matin | Projet 2, Licter × Fnac Darty | Coup 3 : approche roulée au wedge |
| 3 | `payfit` | Green, à 3 m du trou | Matin clair | Projet 3, Hackathon PayFit | Coup 4 : putt pour birdie, la balle tombe |
| 4 | `revenue-engine` | Trou 2, par 3, sur le tee au bord de l'eau | Fin d'après-midi | Projet 4, Revenue Engine | Coup 5 : fer 7 au-dessus de l'eau |
| 5 | `estimia` | Green, à 1,5 m du trou | Heure dorée | Projet 5, Estimia | Coup 6 : le dernier putt |
| 6 | `contact` | Au fond du trou | Heure dorée | Contact | |

Les six coups (un « trajet » = les images de mouvement entre deux arrêts) :

| Trajet | Coup | Vue de la frappe | Ce qu'on voit ensuite |
| --- | --- | --- | --- |
| 0 → 1 | Bois 3 depuis le tee | De devant, au ras du sol, à contre-jour | La balle part ; Antoine de dos au finish, en silhouette ; ciel ; la balle se pose sur le fairway |
| 1 → 2 | Fer long | Trois quarts avant, au ras de la rosée, la motte s'envole | Ciel ; la balle retombe au bord du green |
| 2 → 3 | Wedge, approche roulée | De côté, au ras de l'herbe | Sans coupe : la balle saute, roule sur le green et s'arrête à 3 m du trou |
| 3 → 4 | Putt | Derrière le trou, la balle vient vers nous | Elle tombe ; noir du trou ; on redescend du ciel sur le tee du par 3 |
| 4 → 5 | Fer 7 | Dans l'axe, derrière la balle, l'eau devant | La balle survole l'eau, se pose sur le green et roule à 1,5 m du trou |
| 5 → 6 | Putter | De côté, au ras du green | La balle roule, tombe ; la caméra vient à l'aplomb du trou |

Règles d'image valables partout :

- Le sujet (la balle) est dans la bande centrale droite de l'image, autour de x = 0,62 : il survit au
  recadrage vertical du téléphone, et la gauche reste calme et sombre pour le texte.
- À l'arrêt : la balle au repos, la tête du club posée derrière (sauf arrêt 6), décor en flou.
- Jamais de joueur calculé. Jamais de logo de marque.

---

## 3. Qui possède quoi dans le dépôt

| Chemin | Rôle |
| --- | --- |
| `content/site.json` | Tout le texte du site, français et anglais (schéma en section 4). |
| `src/`, `index.html`, `vite.config.js`, `package.json` | Le site (Vite + React 19). |
| `server/index.js`, `server/snapshot.json` | Serveur Express 5 : fichiers, santé, texte écrit dans la page pour les robots. |
| `public/frames/` | Le film converti (WebP) et `manifest.json`. |
| `scripts/placeholder_frames.py` | Film factice étiqueté, pour tester le site sans rendu. |
| `scripts/frames.py` | Conversion des PNG de `render/out` vers `public/frames`. |
| `render/parts.py` | Briques : balle, tee, bois 3, herbe, rosée, ciel, soleil, halo. |
| `render/clubs.py` | Fer (long, 7, wedge) et putter. |
| `render/scene.py` | Les 7 arrêts et les 6 trajets. |
| `render/assets/` | Ciels téléchargés et fichiers personnels : jamais versionné. |
| `render/human.py`, `render/golfer.py` | Essais de joueur 3D, abandonnés. Ne pas y toucher. |

---

## 4. Formats communs

### `public/frames/manifest.json`

```json
{
  "width": 1920, "height": 1080, "fps": 27,
  "sizes": { "l": { "motion": 1920, "hold": 3840 }, "m": { "motion": 1920, "hold": 2560 }, "s": { "motion": 1280, "hold": 1600 } },
  "stops": [ { "id": "depart", "focus": [0.62, 0.55] } ],
  "legs":  [ { "from": 0, "to": 1, "frames": 44 } ]
}
```

- Image nette de l'arrêt *k* : `public/frames/<taille>/h_<kk>.webp` (`h_00` … `h_06`).
- Image *n* (à partir de 1) du trajet *k* → *k+1* : `public/frames/<taille>/l<k>_<nnnn>.webp`.
- `focus` : position de la balle dans l'image à l'arrêt (0 à 1), pour le recadrage du téléphone.
- Un trajet absent ou incomplet : la page fait un fondu entre les deux arrêts.
- `public/frames/poster.webp` : première image en très petit (moins de 30 Ko).

### `content/site.json`

```json
{
  "meta": { "name": "Antoine Millot", "title": { "fr": "", "en": "" }, "description": { "fr": "", "en": "" } },
  "ui": { "fr": { "next": "Coup suivant" }, "en": { "next": "Next shot" } },
  "holes": [ { "n": 1, "par": 5, "length": 478 }, { "n": 2, "par": 3, "length": 152 } ],
  "stops": [
    { "id": "depart", "kind": "intro", "hole": 1, "stroke": 0,
      "label": { "fr": "", "en": "" }, "title": { "fr": "", "en": "" }, "body": { "fr": "", "en": "" } },
    { "id": "spendmap", "kind": "project", "slug": "spendmap", "hole": 1, "stroke": 1,
      "label": { "fr": "", "en": "" }, "club": { "fr": "", "en": "" },
      "concept": { "fr": "", "en": "" }, "name": "SpendMap",
      "sentence": { "fr": "", "en": "" }, "result": { "fr": "", "en": "" },
      "tools": [], "links": { "code": null, "demo": null },
      "case": { "problem": { "fr": "", "en": "" }, "built": [ { "fr": "", "en": "" } ],
                "flow": [ { "fr": "", "en": "" } ], "outcome": { "fr": "", "en": "" }, "role": { "fr": "", "en": "" } } },
    { "id": "contact", "kind": "contact", "hole": 2, "stroke": 6,
      "title": { "fr": "", "en": "" }, "body": { "fr": "", "en": "" },
      "email": "", "links": [ { "label": "", "url": "" } ] }
  ],
  "next": [ { "club": { "fr": "", "en": "" }, "shot": { "fr": "", "en": "" } } ],
  "about": { "journey": [], "skills": [], "certifications": [] }
}
```

- `stroke` : nombre de coups joués quand on arrive à cet arrêt (0 au départ, 6 au contact).
- `next[k]` : le coup que le geste va jouer en quittant l'arrêt *k* (six entrées).
- Fiche projet : une phrase de 18 mots au plus, un résultat, 3 à 5 outils. Tout vient de
  `server/snapshot.json` : aucun chiffre inventé.

---

## 5. Le site

- **Accueil** : nom, titre, une phrase, deux boutons : « Jouer » et « Voir les projets ».
- **Un geste = un coup** : molette, trackpad (seul le début du geste compte), balayage tactile,
  flèches, et un bouton « Coup suivant » toujours visible.
- **À l'arrivée** : l'image nette remplace la dernière image du trajet par un fondu, dérive très
  lentement, puis la fiche monte.
- **Fiche projet** : étiquette de golf (« TROU 1 · COUP 2 · FER LONG »), nom, concept, une phrase,
  résultat en gros, outils, boutons « Étude de cas » et « Code » ou « Démo » s'ils existent.
- **Étude de cas** : panneau qui glisse par-dessus le film, dans la page : problème, ce qui a été
  construit, schéma source → traitement → sortie, résultat, rôle, liens. Fermeture par Échap.
- **Carte de score** : le sommaire, toujours accessible. Une ligne par coup avec le projet ; puis
  parcours, savoir-faire, certifications, contact. C'est aussi la version sans animation.
- **Plan du trou** : petit dessin vu du dessus, la balle y avance coup après coup.
- **Téléphone** : même film recadré autour de la balle, fiche en bas sur fond sombre.
- **Pour tout le monde** : clavier, lien direct par arrêt (`#spendmap`), animations réduites en
  fondus, vrai texte dans la page pour les lecteurs d'écran et les robots.
- **Charte** : titres en Instrument Serif, texte en Inter, étiquettes en JetBrains Mono ; fond vert
  très sombre `#0a1410`, texte crème `#f2efe8`, une seule touche ambre `#f2a93b`.

---

## 6. Le film

| Élément | Images |
| --- | --- |
| Six trajets | 6 × 44 = 264 |
| Images d'arrêt | 7 |

- Mouvement : 1920×1080, 16 échantillons, flou de mouvement, jouées à 27 images par seconde.
- Arrêts : 3840×2160, 96 à 128 échantillons.
- Animatique d'abord : tout le film en 480×270 pour régler le rythme en ligne.
- Budget de calcul mesuré ici : 63 s par image de mouvement, 12 min par arrêt 4K. Compter 11 à 12 h,
  15 à 18 h avec une série de retouches, par lots de 2 h poussés au fur et à mesure.

`render/scene.py` : `--stop N`, `--leg N`, `--frames a-b`, `--scale`, `--samples`, `--out`,
`--view` pour les vues de contrôle. Il saute les images déjà calculées.

---

## 7. Étapes

| Étape | Livré à Antoine |
| --- | --- |
| 1. Site jouable avec un film factice, textes réels, en ligne | Un lien |
| 2. Planche des 7 arrêts en basse résolution, ordinateur et téléphone | Une planche à valider |
| 3. Animatique des 6 coups en ligne | Le même lien, rythme à valider |
| 4. Image du finish en silhouette | Une image à valider avant publication |
| 5. Rendu final par lots | Le site s'affine lot après lot |
| 6. Finition : poids, téléphone réel, partage, captures de preuve | Site final |

---

## 8. Risques

| Risque | Réponse |
| --- | --- |
| Six frappes qui semblent mécaniques. | Une seule routine de frappe mise au point une fois ; ralenti, cadrage serré, flou. |
| Le film accroche mais ne prouve rien. | Étude de cas dans la page, liens code et démo, carte de score. Trois projets n'ont aucun lien public : à compléter par Antoine. |
| Raccord entre deux lieux. | Il se fait dans le ciel ou dans le noir du trou, pendant un mouvement flou. |
| Conteneur éphémère. | Rendus par lots, reprise automatique, poussée après chaque lot. |

## 9. Crédits

Ciels et panoramas : Poly Haven, CC0. Fichiers téléchargés par `render/fetch_assets.py`.
