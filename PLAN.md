# Golfolio — plan d'action

Portfolio IA & data d'Antoine Millot, raconté par un seul coup de golf. Même méthode que
`portfolio-3d` (film pré-rendu dans Blender, rejoué par la page, un geste = un arrêt), nouveau sujet.

> **Un coup de bois 3 au lever du soleil. Six secondes de vol, étirées en neuf arrêts.**
> On voit la tête du bois 3 traverser la balle, puis on suit la balle : chaque arrêt du vol est un
> projet. Elle se pose à 40 cm du trou. Le dernier putt, c'est le contact.

Rien n'est construit tant que ce plan n'est pas validé. Les décisions marquées **Défaut** sont celles
que j'applique sans réponse contraire.

---

## 1. Ce qui est vérifié

| Sujet | Constat |
| --- | --- |
| Méthode | Celle du guide PDF et du dépôt `portfolio-3d` (lu en entier : `render/scene.py`, `scripts/frames.py`, `src/lib/film.js`, `src/lib/input.js`, `server/index.js`). Le lecteur et la gestion des gestes sont repris, pas réinventés. |
| Contenu réel | 12 projets publiés, 7 certifications, contact et liens (copie du 11/11 dans `portfolio-3d/server/snapshot.json`) ; parcours et « Golf, niveau international » dans `Portfolio-Pro/src/lib/content.js`. |
| Blender ici | `pip install bpy` installe Blender 5.3.0 ; Cycles tourne sur les 4 cœurs, sans carte graphique, avec le débruiteur. |
| Rendu d'essai | Balle sur tee, 900 000 brins d'herbe réels, ciel physique, **aucun fichier téléchargé** : voir `render/probe.py`. |
| Temps mesurés | 63 s pour une image de mouvement (1920×1080, 16 échantillons, flou de mouvement). 177 s pour une image nette en 1920×1080 à 96 échantillons, soit environ 12 min en 3840×2160. |
| Réseau de la session | PyPI, npm et Google Fonts passent. **Poly Haven et tous les `*.up.railway.app` sont refusés** par la politique réseau : il faut les autoriser (voir phase 0). |
| Railway | Projet `Portfolio-Pro` : services `portfolio`, `portfolio-3d`, `Postgres`. Les deux sites se déploient depuis GitHub avec Railpack. |

---

## 2. L'histoire : neuf arrêts, quatre chapitres

Le trou : un par 4 court de 245 m, attaqué au bois 3 depuis le départ, étang à survoler, green gardé
par deux bunkers, club-house derrière. Lumière unique : soleil rasant du matin. Tout le film dure
environ dix secondes de temps réel.

La balle est toujours le sujet net, au même endroit de l'écran ; le parcours est le décor, en flou
d'arrière-plan. C'est ce qui rend l'image photoréaliste et lisible, sur ordinateur comme sur téléphone.

| # | Chapitre | Arrêt (ancre) | Ce qu'on voit | Ce que ça raconte |
| --- | --- | --- | --- | --- |
| 0 | Départ | L'adresse (`#depart`) | Ras du sol : la balle sur un tee bas, la tête du bois 3 posée derrière, fairway et drapeau flous au fond. | Qui je suis : nom, titre, une phrase, deux boutons. |
| → | | *La frappe* | Ralenti : la tête arrive, impact, la balle s'écrase un instant, le tee saute, la balle part et la caméra s'élance derrière elle. | |
| 1 | Le vol | Décollage (`#revenue-engine`) | La balle figée à 2 m du tee, brins d'herbe et tee en l'air, la tête du club floue en fin de geste. | Projet 1 : **orchestration**. |
| 2 | Le vol | Montée (`#fnac-darty`) | Derrière la balle, au-dessus de l'étang : reflets du soleil en flou. | Projet 2 : **pipeline de données**. |
| 3 | Le vol | Sommet (`#spendmap`) | À hauteur de balle, 28 m au-dessus du trou : la balle sur le ciel, tout le parcours en dessous. | Projet 3 : **RAG + graphe**, la vue d'ensemble. |
| 4 | Le vol | Descente (`#payfit`) | Au-dessus de la balle qui plonge : bunkers, green et drapeau flous en contrebas. | Projet 4 : **évaluation**, le contrôle de trajectoire. |
| 5 | Le vol | Atterrissage (`#riskscope`) | Ras du green : la balle figée à l'instant du premier rebond, gouttes de rosée, drapeau au fond. | Projet 5 : **agents + sources**, se poser sur un verdict. |
| → | | *Le roulement* | Deux rebonds, la balle roule et s'arrête à 40 cm du trou. | |
| 6 | Le green | Le chemin parcouru (`#parcours`) | Derrière le trou, on regarde vers le départ : la balle au premier plan, toute la trajectoire tracée jusqu'au tee. | Parcours : 4 étapes posées sur la trajectoire. |
| 7 | Le green | Le sac (`#sac`) | Gros plan sur le sac posé au bord du green : têtes de clubs, serviette, étiquettes de sac. | Savoir-faire (3 familles) et 7 certifications. |
| 8 | Le putt | Le dernier putt (`#contact`) | Plan large au ras du green : la balle, le trou, le drapeau, le club-house au fond. | « Il reste un putt pour l'eagle. On le joue ensemble ? » |

Le rail de navigation montre **quatre chapitres** (Départ · Le vol · Le green · Le putt) avec un trait
par arrêt : neuf arrêts, mais jamais plus de quatre lignes de texte par arrêt.

Bonus si le temps le permet : un clic sur « Me contacter » rentre le putt (20 images de plus).

### Sans golfeur à l'image

Seuls la tête et le bas du manche du bois 3 sont dans le cadre, comme dans un plan d'impact de
publicité. Une silhouette invisible à la caméra projette l'ombre du joueur au sol. Pas de personnage
à animer : c'est ce qui rend le plan faisable et propre.

### La donnée à l'écran

Un tracé de balle façon retransmission télé (dessiné par la page, pas dans l'image) relie le départ
à la balle, et un bandeau discret affiche les vraies valeurs du vol calculé : distance, hauteur,
vitesse. Cible : 225 m de portée, 28 m de sommet, environ 6 s de vol (trajectoire simulée avec
traînée et portance, pas dessinée à la main). À l'arrêt 6, les quatre étapes du parcours sont des
points sur ce tracé.

---

## 3. Les projets retenus

Lecture d'un recruteur Applied AI / AI Architect / AI Engineer : il cherche des systèmes LLM complets
(RAG, agents, évaluation), des choix d'architecture, un résultat mesurable, un vrai contexte, du code.
Cinq projets, un concept chacun, pour couvrir toute la chaîne sans redite.

| Vol | Projet | Concept | Pourquoi lui | Résultat affiché |
| --- | --- | --- | --- | --- |
| Décollage | Revenue Engine Hackathon | Orchestration | Construit en une journée avec l'équipe Sage, quatre outils qui travaillent ensemble (Clay, lemlist, HubSpot, OpenAI). Récent, en équipe, orienté métier. | 100 profils → 10 leads qualifiés |
| Montée | BDD Licter × Fnac Darty | Pipeline de données | Du scraping au tableau de bord COMEX en 5 jours : collecte, sentiment GPT-4o, clustering, Supabase. Code public. | Pipeline 100 % automatisé |
| Sommet | SpendMap | RAG + graphe | Le plus architecturé : extraction IA des PDF, embeddings, clustering, graphe Neo4j, agent qui traduit une question en SQL. | Les dépenses du groupe, interrogées en langage naturel |
| Descente | Hackathon PayFit | Évaluation | Une IA rédige, une seconde note, et tout repart sous 70/100 : la boucle de qualité que les équipes IA attendent. | Publication automatique, qualité contrôlée |
| Atterrissage | RiskScope | Agents + sources | Application complète : 5 angles d'analyse, des centaines de sources, chaque affirmation sourcée, un verdict. Code public. | Mémo IC en 3 min |

Chaque arrêt projet affiche : le concept, **l'obstacle** (le problème, une phrase), **le coup joué**
(la solution, une phrase, avec un schéma source → traitement → sortie), **le score** (le résultat),
les outils, et les liens vers l'étude de cas et le code.

Laissés hors du vol, et pourquoi :

- **Meridian** : très proche de RiskScope (recherche sourcée par IA) ; un seul des deux suffit.
- **Hackathon 3M** (finaliste) et **IKORY** (−4 h de travail par jour en stage) : placés dans le
  parcours, à l'arrêt 6, là où un prix et un résultat en entreprise pèsent le plus.
- **LVMH, Carrefour, Estimia, Devis Traiteur, SEO/GEO Control Room** : peu ou pas d'IA à montrer, ou
  contenu confidentiel. Ils restent accessibles par le lien « Portfolio complet ».

---

## 4. Direction artistique

- **Image** : macrophotographie d'une balle de golf en vol. Longue focale, faible profondeur de
  champ, soleil rasant, rosée. Balle personnalisée « AM », bois 3 sans marque avec « 3 · 15° » gravé
  sur la semelle et son capuchon « 3 » posé près du départ.
- **Interface** : même charte que les deux portfolios (Inter, JetBrains Mono, une seule touche ambre
  `#f2a93b`, texte crème `#f2efe8`), fond vert très sombre `#0a1410` à la place du marine. Le tracé
  de balle est ambre.
- **Lisibilité** : le sujet est toujours à droite, le texte à gauche sur un dégradé sombre ; sur
  téléphone, le texte est en bas sur un fond sombre. Jamais de texte sur une zone claire.
- **Langues** : français et anglais, comme les deux autres sites.

---

## 5. La scène Blender (`render/`)

Tout est décrit en Python, à l'échelle réelle, comme pour la platine.

| Élément | Comment |
| --- | --- |
| Terrain | Maillage calculé (butte du départ, couloir du fairway, cuvette de l'étang, plateau du green, bunkers creusés) avec des zones peintes : départ, fairway tondu en bandes, rough, green, avant-green, sable. |
| Herbe | Vrais brins (maillage numpy, technique de `probe.py`) seulement dans trois zones proches de la caméra : départ, zone d'atterrissage et de roulement, bord du green. Ailleurs, une matière. Hauteurs par zone : 3 à 4 mm sur le green, 12 mm sur le fairway, 5 à 8 cm dans le rough. |
| Balle | Vraies alvéoles en relief (environ 350), tampon « AM », rotation arrière visible dans le flou. |
| Bois 3 | Tête compacte modélisée (face striée, semelle gravée, couronne vernie), manche graphite. |
| Vol | Trajectoire simulée, une clé par image ; le temps ralentit en douceur vers chaque arrêt. |
| Frappe | Arc de la tête au ralenti, balle écrasée sur une ou deux images, tee et brins projetés. |
| Eau, sable | Surface réfléchissante à vaguelettes ; sable à grain et traces de râteau. |
| Décor | Drapeau et trou, marques de départ, sac avec ses clubs, serviette et étiquettes, club-house simple au loin. |
| Ciel, arbres, bois, cuir | **Poly Haven (CC0)** si l'accès est accordé : ciel de lever de soleil avec nuages, arbres scannés, textures. Sinon : ciel physique intégré et arbres générés par code, toujours gardés dans le flou. |
| Impressions | Tampon de balle, gravures, drapeau, étiquettes de sac, capuchon : dessinés en HTML et imprimés en textures (`scripts/prints/`, même principe que les pochettes de disques). |

`render/scene.py` garde les mêmes options que l'ancien : `--still N`, `--holds`, `--seq`,
`--frames a-b`, `--scale`, `--samples`, `--out`. Il saute les images déjà calculées et écrit
`anchors.json` : position de la balle à l'écran pour chaque image, points du tracé, distance, hauteur,
vitesse, et le point de recadrage pour le téléphone.

---

## 6. Le film

| Tronçon | Images | Durée à l'écran |
| --- | --- | --- |
| La frappe (0 → 1) | 40 | 1,55 s |
| Vol, quatre tronçons (1 → 5) | 4 × 30 | 1,15 s chacun |
| Le roulement (5 → 6) | 36 | 1,4 s |
| Green → sac → putt (6 → 8) | 2 × 30 | 1,15 s chacun |
| **Total mouvement** | **256** | |
| Images d'arrêt | 9 | |

- **Mouvement** : 1920×1080, 16 échantillons, flou de mouvement.
- **Arrêts** : **3840×2160 (4K)**, 96 à 128 échantillons, parfaitement nets. Neuf arrêts au lieu de
  dix-sept : le 4K partout devient abordable.
- **Budget de calcul** : mouvement environ 4 h 30, arrêts environ 2 h, essais et animatique 1 h. La
  scène finale étant plus lourde que l'essai, compter **8 à 9 h de machine**, en lots de 2 h au plus.
- **Sécurité** : le conteneur est éphémère. Les images sont converties et poussées sur la branche
  après chaque lot ; un lot interrompu reprend à l'image suivante.

Conversion (`scripts/frames.py`) : WebP, trois tailles d'arrêt (3840, 2560, 1600) et deux de
mouvement (1920, 1280), une affiche de moins de 30 Ko, `manifest.json`. Objectif de poids : 30 Mo au
plus pour les grands écrans, 14 Mo pour les autres, chargés dans l'ordre du guide.

---

## 7. Le site (`src/`, `server/`)

Vite + React 19, Express 5, comme `portfolio-3d`.

```
render/     scene.py  parts.py  course.py  flight.py  probe.py
scripts/    frames.py  prints/prints.cjs
src/        App.jsx  main.jsx  styles.css
            lib/film.js  lib/input.js  lib/overlay.js  lib/copy.js
server/     index.js  snapshot.json
public/     frames/…  favicon.svg
railway.json  package.json  vite.config.js  index.html
```

- **Un geste = un arrêt** : molette, balayage du trackpad (seul le début du geste compte), balayage
  tactile, flèches. La caméra fait le trajet seule, à vitesse constante.
- **Arrivée** : l'image 4K remplace la dernière image du trajet par un fondu d'un tiers de seconde,
  puis dérive très lentement. Le texte monte bloc par bloc une fois la caméra posée.
- **Tracé et bandeau de données** (`lib/overlay.js`) : dessinés par-dessus l'image à partir de
  `anchors.json`, avec la même dérive que l'image. Les chiffres défilent pendant le trajet.
- **Chargement** : affiche, puis l'arrêt 0 net, puis les tronçons du grossier au fin en commençant
  par les plus proches, puis les autres arrêts. Tronçon pas encore chargé : fondu vers l'arrêt suivant.
- **Téléphone** : même film, recadré autour de la balle (le point de recadrage suit la balle image
  par image), texte en bas sur fond sombre, bandeau compact.
- **Pour tout le monde** : clavier complet, lien direct vers chaque arrêt, animations réduites
  respectées (fondus, pas de dérive, tracé fixe), texte réel dans la page pour les lecteurs d'écran.
- **Contenu** : `/api/content` relayé depuis le portfolio principal, avec une copie de secours. Titres,
  résultats, outils et liens viennent de l'admin ; les phrases « obstacle / coup / score » et les
  schémas sont dans `lib/copy.js`, en français et en anglais.

---

## 8. Mise en ligne (Railway)

- Nouveau service **`golfolio`** dans le projet `Portfolio-Pro`, relié au dépôt GitHub
  `antoineMllt1/golfolio` sur la branche de travail. Les services `portfolio`, `portfolio-3d` et
  `Postgres` ne sont pas touchés.
- `railway.json` : Railpack, `npm run build`, `node server/index.js`, contrôle de santé `/api/health`.
- Variable `MAIN_URL` vers le portfolio principal, puis génération d'un domaine.
- Preuve avant chaque mise en ligne : captures de chaque arrêt en 1920×1080, 1440×900 et 390×844,
  et zéro erreur dans la console.

---

## 9. Les phases, dans l'ordre

Chaque phase se termine par quelque chose à regarder. Je ne lance pas le rendu long sans validation
des cadrages.

| Phase | Travail | Ce que tu reçois |
| --- | --- | --- |
| 0. Mise en place | Demande d'accès réseau (une fenêtre d'approbation) pour `api.polyhaven.com`, `dl.polyhaven.org`, `antoine-millot.up.railway.app`, `portfolio-3d-production-a53c.up.railway.app`. Squelette du dépôt. Copie à jour du contenu. | Dépôt prêt, liste exacte des projets publiés. |
| 1. Le héros | Balle à alvéoles, tee, bois 3, herbe du départ, lumière. | **Une image** de l'arrêt 0 en 1920×1080. Tu valides la balle, le club, la lumière. |
| 2. Les cadrages | Le trou entier en volumes simples, la trajectoire simulée, les 9 caméras. | **Planche des 9 cadrages** en basse résolution, version ordinateur et version téléphone. Tu valides avant d'aller plus loin. |
| 3. L'animatique en ligne | Le film complet en 480×270, le site jouable (gestes, textes, tracé, bandeau, téléphone), premier déploiement Railway. | **Un lien** : tu testes le rythme et les textes en vrai. |
| 4. Le détail | Matières, eau, sable, arbres, sac, club-house, impressions. | **Trois images de référence** en pleine qualité (frappe, sommet, green). |
| 5. Le rendu final | Les 9 arrêts en 4K, puis les 256 images de mouvement, par lots, poussés au fur et à mesure. | Le site s'affine lot après lot sur le même lien. |
| 6. La finition | Poids, ordre de chargement, liste de contrôle du guide, captures de preuve. | Site final, captures ordinateur et téléphone, console propre. |

---

## 10. Risques et plans B

| Risque | Réponse |
| --- | --- |
| Un extérieur est plus difficile à rendre crédible qu'une platine dans une pièce sombre. Les arbres et le ciel sont les points faibles. | La balle est le seul sujet net ; le décor reste dans le flou. Ciel et arbres Poly Haven si l'accès est accordé. Images d'essai validées avant tout rendu long. |
| La frappe peut sembler mécanique. | Ralenti, cadrage serré, flou de mouvement ; c'est le premier plan que je montre en phase 4. Plan B : commencer le plan à l'impact. |
| Le conteneur peut être repris pendant 8 à 9 h de calcul. | Lots de 2 h, reprise automatique, poussée après chaque lot. |
| Accès réseau refusé. | Scène entièrement générée par code (prouvé par l'essai) ; vérification du site en local, et de la mise en ligne par les journaux Railway. |
| L'application GitHub de Railway ne voit pas le dépôt `golfolio`. | Tu l'autorises en un clic côté Railway ; je te le signale dès la phase 3. |
| Un projet retenu disparaît de l'admin. | La copie de secours garde l'arrêt ; je te le signale. |

---

## 11. Décisions à confirmer

1. **Droitier ou gaucher ?** Cela fixe le côté du club et de la caméra. **Défaut : droitier.**
2. **Titre de l'arrêt 0.** Pour des postes IA, je mettrais « AI Engineer & Data Analyst » plutôt que
   l'ordre actuel. **Défaut : AI Engineer & Data Analyst.**
3. **Les cinq projets** du tableau, dans cet ordre. **Défaut : oui.**
4. **Tes vrais repères de golf** (index, club, palmarès) : je ne les invente pas. Si tu me les donnes,
   ils vont à l'arrêt 0 ou 6. **Défaut : aucun chiffre de golf personnel.**
5. **Le dépôt `TeeTime`** : si c'est un projet data ou IA montrable, il a sa place ici. **Défaut : non inclus.**
