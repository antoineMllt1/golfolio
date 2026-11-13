# Golfolio — plan d'action

Portfolio IA & data d'Antoine Millot, raconté par une partie de golf. Même méthode que
`portfolio-3d` (film pré-rendu dans Blender, rejoué par la page, un geste = un arrêt), nouveau sujet.

> **Une partie, huit coups.** Chaque swipe joue un coup de golf, filmé d'un angle différent.
> Chaque arrêt est un trou, une lumière, un projet. On part à l'aube du trou 1 ; le dernier putt,
> au crépuscule du 18, c'est le contact.

Plan validé le 12 novembre 2026, puis réorienté le même jour par Antoine : « chaque swipe est un coup
de golf d'une vue différente » et « un rendu aesthetic ». Décisions en section 11.

---

## 1. Ce qui est vérifié

| Sujet | Constat |
| --- | --- |
| Méthode | Celle du guide PDF et du dépôt `portfolio-3d` (lu en entier). Le lecteur d'images et la gestion des gestes sont repris, pas réinventés. |
| Contenu réel | 12 projets publiés, 7 certifications, contact et liens : lus en direct sur `antoine-millot.up.railway.app/api/content`. Parcours dans `Portfolio-Pro/src/lib/content.js`. |
| Blender ici | `pip install bpy` installe Blender 5.3.0 ; Cycles tourne sur les 4 cœurs, sans carte graphique, avec le débruiteur. |
| Temps mesurés | 63 s pour une image de mouvement (1920×1080, 16 échantillons, flou). 177 s pour une image nette en 1920×1080 à 96 échantillons, soit environ 12 min en 3840×2160. |
| Réseau | Environnement « Portfolios » créé : Poly Haven et les trois sites Railway sont joignables. |
| Railway | Service `golfolio` créé dans le projet `Portfolio-Pro`, domaine `golfolio-production.up.railway.app`. Pas encore de source reliée. |

---

## 2. L'histoire : huit arrêts, sept coups, un dernier putt

Une partie de 18 trous résumée en huit coups choisis. La journée avance avec les trous : aube,
matin, midi, fin d'après-midi, coucher de soleil, crépuscule. Chaque arrêt est une petite scène à
part, avec sa lumière.

**La règle d'un swipe** (environ 1,6 s) : le club traverse la balle au ralenti, vu sous l'angle propre
à l'arrêt ; la balle part, la caméra la suit et bascule vers le ciel ; elle redescend sur le trou
suivant, où une balle attend dans une autre lumière. Le changement de lieu se fait dans le ciel.

**La règle d'un arrêt** : une balle au repos, la tête du club posée derrière, un décor en flou.
Image nette en 4K, sujet toujours au même endroit de l'écran.

| # | Trou | Lumière | À l'arrêt | Coup joué au swipe | Vue | Contenu |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 1, départ | Aube, brume | Balle sur tee bas, face du bois 3 derrière elle | Mise en jeu au **bois 3** | De devant, au ras du sol, à contre-jour : la balle part au-dessus de nous | Qui je suis (`#depart`) |
| 1 | 4, fairway | Matin, rosée | Balle sur les bandes de tonte, fer | **Fer long**, la motte s'envole | Trois quarts avant, au ras de la rosée | Revenue Engine (`#revenue-engine`) |
| 2 | 7, par 3 | Matin clair | Balle sur tee au bord du lac | **Fer 7** au-dessus de l'eau | Dans l'axe, derrière la balle, le lac et le green au fond | Licter × Fnac Darty (`#fnac-darty`) |
| 3 | 10, fairway | Midi doux | Balle vue d'en haut, lignes de tonte | **Wedge**, approche levée | Plongée verticale | SpendMap (`#spendmap`) |
| 4 | 13, bunker | Fin d'après-midi | Balle dans le sable | **Sortie de bunker** | Depuis la lèvre, gerbe de sable | Hackathon PayFit (`#payfit`) |
| 5 | 16, green | Heure dorée | Balle sur le green, le trou au premier plan | **Putt** qui tombe | Derrière le trou, la balle vient vers nous | Estimia (`#estimia`) |
| 6 | 18, approche | Coucher de soleil | Balle devant le green, club-house au loin | **Approche au wedge**, suivie jusqu'au green | De côté, à contre-jour | Parcours et savoir-faire (`#parcours`) |
| 7 | 18, green | Crépuscule | Balle à 40 cm du trou, club-house allumé | Le **dernier putt**, joué au clic sur « Me contacter » | Au ras du green | Contact (`#contact`) |

Seul le coup du 6 vers le 7 est suivi d'un bout à l'autre (même trou) : c'est la fin de la partie.

### Le joueur ressemble à Antoine

Construit d'après ses photos (`render/player.py`) : silhouette fine, casquette marine, cheveux bruns
ondulés qui dépassent, haut blanc à manches longues, chino beige, baskets blanches, gant blanc à la
main gauche. C'est une silhouette stylisée, sans visage : il est montré de dos, à contre-jour ou
dans le flou, jamais net de face.

- **De dos, au finish**, découpé sur le ciel, comme sur sa photo de practice (étude : `--study finish`).
- **De face, en flou** : ses baskets et le bas du chino derrière la balle.
- **Dans les vues serrées** : seuls la tête du club et le bas du manche sont dans le cadre.

### Pourquoi ce coup pour ce projet

| Projet | Concept | Le coup | Le lien |
| --- | --- | --- | --- |
| Revenue Engine Hackathon | Orchestration | Fer long depuis le fairway | Quatre outils enchaînés en une journée, avec l'équipe Sage : avancer loin d'un seul coup. |
| BDD Licter × Fnac Darty | Pipeline de données | Fer 7 au-dessus de l'eau | Faire passer la donnée brute de l'autre côté : collecte, sentiment, clustering, tableau de bord. |
| SpendMap | RAG + graphe | Vue du ciel | La vue d'ensemble : les dépenses d'un groupe, interrogées en langage naturel. |
| Hackathon PayFit | Évaluation | Sortie de bunker | Une IA rédige, une autre note, et tout repart sous 70/100 : on rejoue jusqu'à en sortir. |
| Estimia | Produit data en ligne | Le putt | Lire la pente et tomber juste : un prix au m², un niveau de confiance. Démo publique. |

Chaque arrêt projet affiche : le trou et le club, le concept, **l'obstacle** (une phrase), **le coup
joué** (une phrase, avec un schéma source → traitement → sortie), **le score** (le résultat), les
outils, les liens vers l'étude de cas, la démo ou le code.

Hors de la partie : RiskScope (remplacé par Estimia à la demande d'Antoine), Meridian, Hackathon 3M
et IKORY (cités dans le parcours, arrêt 6), LVMH, Carrefour, Devis Traiteur, SEO/GEO Control Room.
Tous restent accessibles par « Portfolio complet ».

---

## 3. Direction artistique

- **Image** : série de natures mortes de golf. Longue focale, faible profondeur de champ, lumière
  rasante, rosée, brume. Une ambiance par arrêt, de l'aube au crépuscule.
- **Matériel** (d'après les références d'Antoine, sans logo de marque, monogramme « AM » à la place) :
  bois 3 tout noir, couronne mate à trois points ambre, face noire à stries blanches ; fers en acier
  satiné à dos creusé avec un insert noir à deux vis ; wedge brossé ; balle blanche tamponnée « AM ».
- **Le sac** : à l'arrêt 6, les fers dépassent du sac au premier plan, fairway flou derrière.
- **Compositions** : beaucoup de vide, un seul sujet net, le décor en flou. Jamais deux arrêts sous
  le même angle.
- **Interface** : éditoriale et discrète. Titres en grande serif (Instrument Serif), texte en Inter,
  étiquettes en JetBrains Mono (« TROU 07 · PAR 3 · FER 7 »). Texte crème `#f2efe8`, une seule touche
  ambre `#f2a93b`, fond vert très sombre `#0a1410`.
- **Lisibilité** : sujet à droite, texte à gauche sur un dégradé sombre ; sur téléphone, texte en bas
  sur fond sombre.
- **Langues** : français et anglais.

---

## 4. La scène Blender (`render/`)

Huit petites scènes qui partagent les mêmes objets. Tout est décrit en Python, à l'échelle réelle.

| Élément | Comment |
| --- | --- |
| Décor et lumière | Un ciel photographié Poly Haven (CC0) par arrêt : il éclaire la scène et sert de fond, flouté par la profondeur de champ. Vrais arbres, vrais nuages, sans les modéliser. |
| Sol proche | Maillage calculé autour de la balle : départ, fairway tondu en bandes, bord de lac, sable, green. |
| Herbe | Vrais brins (maillage numpy, technique de `probe.py`) dans les quelques mètres autour de la balle ; une matière au-delà. De 3 mm sur le green à 12 mm sur le fairway. |
| Balle | Vraies alvéoles en relief, tampon « AM », rotation visible dans le flou. |
| Clubs | Trois têtes modélisées : bois 3, fer (décliné en fer long, fer 7 et wedges par l'angle de face), putter. |
| Frappe | Une seule routine pour tous les coups : arc de la tête au ralenti, balle écrasée un instant, puis ce que le coup projette (tee, motte, sable, gouttes). |
| Eau, sable | Surface réfléchissante à vaguelettes ; sable à grain, traces de râteau, grains projetés. |
| Détails | Tee, trou et drapeau, club-house en silhouette avec fenêtres éclairées. |
| Impressions | Tampon de balle, gravures, drapeau : dessinés en HTML et imprimés en textures (`scripts/prints/`). |

`render/scene.py` : `--stop N` (image d'arrêt), `--leg N` (le coup qui quitte l'arrêt N), `--frames a-b`,
`--scale`, `--samples`, `--out`. Il saute les images déjà calculées et écrit `anchors.json` (position
de la balle à l'écran, point de recadrage pour le téléphone).

---

## 5. Le film

| Élément | Images |
| --- | --- |
| Sept coups (0 → 7) | 7 × 42 = 294 |
| Le dernier putt | 24 |
| **Total mouvement** | **318** |
| Images d'arrêt | 8 |

- **Mouvement** : 1920×1080, 16 échantillons, flou de mouvement. 42 images jouées en 1,6 s.
- **Arrêts** : **3840×2160 (4K)**, 96 à 128 échantillons, parfaitement nets.
- **Budget de calcul** : mouvement environ 5 h 30, arrêts environ 1 h 40, essais et animatique 1 h.
  Compter **8 à 9 h de machine**, en lots de 2 h au plus.
- **Sécurité** : le conteneur est éphémère. Les images sont converties et poussées sur la branche
  après chaque lot ; un lot interrompu reprend à l'image suivante.

Conversion (`scripts/frames.py`) : WebP, trois tailles d'arrêt (3840, 2560, 1600) et deux de
mouvement (1920, 1280), une affiche de moins de 30 Ko, `manifest.json`. Objectif : 30 Mo au plus pour
les grands écrans, 14 Mo pour les autres.

---

## 6. Le site (`src/`, `server/`)

Vite + React 19, Express 5, comme `portfolio-3d`.

```
render/     scene.py  parts.py  clubs.py  strike.py  fetch_assets.py  probe.py
scripts/    frames.py  prints/prints.cjs
src/        App.jsx  main.jsx  styles.css
            lib/film.js  lib/input.js  lib/copy.js
server/     index.js  snapshot.json
public/     frames/…  favicon.svg
railway.json  package.json  vite.config.js  index.html
```

- **Un geste = un coup** : molette, balayage du trackpad (seul le début du geste compte), balayage
  tactile, flèches. Le coup se joue seul, à vitesse constante. Retour en arrière : fondu.
- **Arrivée** : l'image 4K remplace la dernière image du trajet par un fondu d'un tiers de seconde,
  puis dérive très lentement. Le texte monte bloc par bloc une fois la caméra posée.
- **Rail** : huit repères numérotés par trou (1, 4, 7, 10, 13, 16, 18, 19e).
- **Chargement** : affiche, puis l'arrêt 0 net, puis les coups du grossier au fin en commençant par
  les plus proches, puis les autres arrêts. Coup pas encore chargé : fondu vers l'arrêt suivant.
- **Téléphone** : même film, recadré autour de la balle, texte en bas sur fond sombre.
- **Pour tout le monde** : clavier complet, lien direct vers chaque arrêt, animations réduites
  respectées (fondus, pas de dérive), texte réel dans la page pour les lecteurs d'écran.
- **Contenu** : `/api/content` relayé depuis le portfolio principal, avec une copie de secours. Titres,
  résultats, outils et liens viennent de l'admin ; les phrases « obstacle / coup / score » et les
  schémas sont dans `lib/copy.js`, en français et en anglais.

---

## 7. Mise en ligne (Railway)

- Service `golfolio` (déjà créé) relié au dépôt GitHub `antoineMllt1/golfolio` sur la branche de
  travail. Les services `portfolio`, `portfolio-3d` et `Postgres` ne sont pas touchés.
- `railway.json` : Railpack, `npm run build`, `node server/index.js`, contrôle de santé `/api/health`.
- Variable `MAIN_URL` vers le portfolio principal.
- Preuve avant chaque mise en ligne : captures de chaque arrêt en 1920×1080, 1440×900 et 390×844,
  et zéro erreur dans la console.

---

## 8. Les phases, dans l'ordre

| Phase | Travail | Ce qu'Antoine reçoit | État |
| --- | --- | --- | --- |
| 0. Mise en place | Accès réseau, service Railway, copie du contenu, squelette du dépôt. | Dépôt prêt. | Fait |
| 1. Le héros | Balle à alvéoles, tee, bois 3, herbe, lumière d'aube. | **Une image** de l'arrêt 0 en 1920×1080, à valider. | Image envoyée |
| 2. Les cadrages | Les huit scènes en volumes simples, les huit caméras, les huit lumières. | **Planche des 8 cadrages**, ordinateur et téléphone, à valider avant tout rendu long. | |
| 3. L'animatique en ligne | Le film complet en 480×270, le site jouable, premier déploiement. | **Un lien** pour tester le rythme et les textes. | |
| 4. Le détail | Fer, putter, sable, eau, club-house, impressions, routine de frappe. | **Trois images de référence** : frappe au bois 3, sortie de bunker, putt. | |
| 5. Le rendu final | Les 8 arrêts en 4K, puis les 318 images de mouvement, par lots. | Le site s'affine lot après lot sur le même lien. | |
| 6. La finition | Poids, ordre de chargement, liste de contrôle du guide, captures de preuve. | Site final, captures ordinateur et téléphone, console propre. | |

---

## 9. Risques et plans B

| Risque | Réponse |
| --- | --- |
| La frappe peut sembler mécanique, et il y en a sept. | Une seule routine, mise au point une fois puis déclinée. Ralenti, cadrage serré, flou de mouvement. Plan B : commencer chaque plan à l'impact. |
| Le raccord entre deux trous peut se voir. | Il se fait dans le ciel, pendant une bascule rapide et floue, avec quelques images fondues par la page. |
| Huit scènes au lieu d'une. | Elles partagent balle, clubs, herbe et routine de frappe ; seuls le sol proche, le ciel et la caméra changent. |
| Le conteneur peut être repris pendant 8 à 9 h de calcul. | Lots de 2 h, reprise automatique, poussée après chaque lot. |
| L'application GitHub de Railway ne voit pas le dépôt `golfolio`. | Antoine l'autorise en un clic côté Railway ; signalé dès la phase 3. |
| Un projet retenu disparaît de l'admin. | La copie de secours garde l'arrêt ; signalé. |

---

## 10. Crédits

Ciels, textures et modèles : Poly Haven, licence CC0. Les fichiers sont téléchargés par
`render/fetch_assets.py` dans `render/assets/` et ne sont pas versionnés.

---

## 11. Décisions prises

1. **Droitier.** Cible à droite quand on regarde le joueur de face ; le joueur n'est jamais dans le cadre.
2. **Cinq projets** : Revenue Engine, Licter × Fnac Darty, SpendMap, Hackathon PayFit, Estimia.
3. **Aucun repère de golf personnel** (index, club, palmarès) sur le site.
4. **`TeeTime`** n'est pas un projet à montrer.
5. **Chaque swipe est un coup de golf**, vu d'un angle différent ; rendu « aesthetic ».
6. **Titre de l'arrêt 0** : sans réponse, « AI Engineer & Data Analyst ». Un mot suffit pour revenir à
   « Data Analyst & AI Engineer ».
