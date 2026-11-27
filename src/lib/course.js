// La géométrie des deux trous, en mètres : la seule source de toutes les cotes du site.
// Repère d'un trou : x vers la droite, y vers le haut (le départ en bas). Rien n'est écrit à la main
// dans les composants : les distances imprimées sont mesurées ici (measures) ou lues dans
// content/site.json, et « npm run check » (content/check-golf.mjs) vérifie que les deux se recoupent.
//
// Ce fichier ne lit pas le texte du site : makeCourse(site) marie la géométrie aux données
// (longueur, par, green, drapeau, portée et total de chaque coup). src/lib/content.js en garde
// l'instance du site : COURSE.

export const rad = (d) => (d * Math.PI) / 180;
export const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
export const add = (a, b, k = 1) => [a[0] + b[0] * k, a[1] + b[1] * k];
export const lerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];

// ---------- courbes
// Courbe passant par les points (Catmull-Rom → Bézier), fermée ou non : le tracé SVG.
const f = (n) => (Math.round(n * 100) / 100).toString();
const P = (p) => `${f(p[0])} ${f(p[1])}`;
export function spline(pts, closed = true) {
  const n = pts.length;
  const at = (i) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  let d = `M${P(pts[0])}`;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${P(c1)} ${P(c2)} ${P(p2)}`;
  }
  return closed ? `${d}Z` : d;
}
// Les mêmes courbes, échantillonnées (pour décaler, festonner, tester un point).
export function sample(pts, per = 10, closed = true) {
  const n = pts.length;
  const at = (i) => (closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))]);
  const out = [];
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const p0 = at(i - 1), p1 = at(i), p2 = at(i + 1), p3 = at(i + 2);
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    for (let k = 0; k < per; k++) {
      const t = k / per, u = 1 - t;
      out.push([
        u * u * u * p1[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t * t * t * p2[0],
        u * u * u * p1[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t * t * t * p2[1],
      ]);
    }
  }
  if (!closed) out.push(pts[n - 1]);
  return out;
}
export const area = (poly) => poly.reduce((s, p, i) => { const q = poly[(i + 1) % poly.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0) / 2;
export function inside(pt, poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i], b = poly[j];
    if (a[1] > pt[1] !== b[1] > pt[1] && pt[0] < ((b[0] - a[0]) * (pt[1] - a[1])) / (b[1] - a[1]) + a[0]) c = !c;
  }
  return c;
}
// Contour décalé vers l'extérieur de k (mêmes unités que le polygone).
export function offset(poly, k) {
  const s = Math.sign(area(poly)) || 1;
  const n = poly.length;
  return poly.map((p, i) => {
    const a = poly[(i - 1 + n) % n], b = poly[(i + 1) % n];
    const tx = b[0] - a[0], ty = b[1] - a[1];
    const l = Math.hypot(tx, ty) || 1;
    return [p[0] + (ty / l) * k * s, p[1] - (tx / l) * k * s];
  });
}
// Lisière d'arbres : des festons le long d'une ligne, tournés du côté « side » (1 : à droite du sens de marche).
export function treeline(pts, step, side = 1) {
  const dense = sample(pts, 12, false);
  const out = [dense[0]];
  let need = step;
  for (let i = 0; i < dense.length - 1; i++) {
    let a = dense[i];
    const b = dense[i + 1];
    let seg = dist(a, b);
    while (seg >= need) { a = lerp(a, b, need / seg); out.push(a); seg -= need; need = step; }
    need -= seg;
  }
  let d = `M${P(out[0])}`;
  for (let i = 1; i < out.length; i++) {
    const r = dist(out[i - 1], out[i]) * 0.6;
    d += `A${f(r)} ${f(r)} 0 0 ${side > 0 ? 1 : 0} ${P(out[i])}`;
  }
  return d;
}

// ---------- les deux trous (mètres)
// Trou 1 : par 5 en dog-leg droit. Mise en jeu au bois 3, fer long, approche roulée, putt.
const H1 = (() => {
  const tee = [60, 0];
  const s1 = [54, 250]; // la balle après la mise en jeu : fairway, centre gauche
  const pin = [190, 433]; // le drapeau du jour
  const u = [(pin[0] - s1[0]) / dist(pin, s1), (pin[1] - s1[1]) / dist(pin, s1)]; // la ligne de jeu vers le drapeau
  const r = [u[1], -u[0]]; // à droite de la ligne de jeu
  const G = add(pin, r, -7); // le centre du green : le drapeau est 7 m à sa droite
  const L = (d, l) => add(add(G, u, d), r, l); // repère du green : d en profondeur, l vers la droite
  return {
    theta: 14, pivot: [58, 250],
    tee, pin, G, u, r, L,
    box: [8, -14, 192, 500], // le cadre « tout le trou », en mètres tournés de theta
    // le cadrage du coup vers le green : depuis quel point du trou, combien de mètres en avant sont centrés, combien tiennent en hauteur
    approach: { from: 1, ahead: 124, span: 296 },
    teeBoxes: [{ c: [60, -3], w: 11, h: 15, ours: true }, { c: [61, 33], w: 9, h: 10 }, { c: [59.5, 60], w: 8, h: 8 }],
    fairway: [
      [48, 97], [45, 130], [43, 170], [41, 210], [40, 240], [41, 262], [47, 282], [60, 301], [76, 323], [97, 351], [120, 382], [140, 405],
      [153, 415], [162, 421], [171, 419], [177, 410],
      [168, 394], [150, 371], [129, 342], [108, 312], [92, 289], [82, 271], [76, 253], [74, 235], [74, 200], [73, 160], [72, 126], [69, 99], [59, 90],
    ],
    green: [[-17, 0], [-16.6, 7], [-13, 11.5], [-5, 13.2], [4, 14], [11, 12.5], [16, 7], [17, 0], [15, -7], [10, -12.5], [2, -14], [-6, -12.5], [-12, -10], [-16, -6]],
    bunkers: [
      { id: 'fairway-droite', pts: [[84, 229], [90, 228], [94, 236], [93, 245], [88, 248], [83, 242], [82, 234]] }, // dans le coude
      { id: 'fairway-gauche', pts: [[27, 261], [33, 258], [37, 265], [36, 275], [30, 279], [25, 273], [24, 266]] }, // au bout du coude
      { id: 'green-avant-droit', local: true, pts: [[-22, 14], [-16, 14.5], [-10, 18], [-8, 24], [-13, 27], [-20, 23]] },
      { id: 'green-gauche', local: true, pts: [[-3, -17.5], [5, -18], [11, -21.5], [10, -26.5], [2, -28], [-5, -24]] },
      { id: 'green-fond', local: true, pts: [[20.5, -6], [20.8, 0], [22.5, 5], [26, 4.5], [26.5, -2], [24, -7.5]] },
    ],
    lines: [
      { pts: [[31, 36], [27, 80], [28, 125], [27, 170], [25, 215], [19, 247]], side: 1 },
      { pts: [[27, 297], [42, 315], [58, 337], [79, 365], [102, 396], [122, 419], [137, 440]], side: 1 },
      { pts: [[100, 148], [101, 190], [103, 222], [110, 262], [130, 296], [156, 332], [180, 362], [200, 386], [213, 409]], side: -1 },
      { local: true, pts: [[-6, 41], [10, 40], [24, 34], [34, 21], [38, 4], [36, -12], [28, -29], [13, -40]], side: -1 },
    ],
    trees: [[90, 62], [97, 104], [34, 12], [87, 22]],
    arcs: [250, 200, 150, 100, 50], // repères de distance vers l'entrée du green
    // la balle : après 0, 1, 2, 3 coups, puis dans le trou
    balls: [tee, s1, add(pin, u, -19), add(pin, u, -3), pin],
    // la forme de chaque coup sur le plan : « bend » (m) courbe la ligne (léger fade : part à gauche, revient) ;
    // « aim: zone » : la ligne de jeu vise la zone de chute, pas le drapeau ; « brk » : la courbe du putt (m)
    shots: [{ bend: -4, aim: 'zone' }, {}, {}, { brk: -1.1 }],
    // pentes du green : où (d, l), vers où ça descend (180 = vers l'entrée, 90 = vers la droite), pourcentage
    slopes: [
      { at: [9.5, -6], to: 195, pct: 2 }, { at: [10, 4], to: 165, pct: 3 }, { at: [1, -8], to: 190, pct: 2 }, { at: [3, -0.5], to: 168, pct: 2 },
      { at: [-7, -6], to: 185, pct: 1 }, { at: [-9, 1.5], to: 162, pct: 2 }, { at: [-13, -2], to: 178, pct: 1 }, { at: [6, 10.5], to: 140, pct: 3 },
    ],
    crest: [[13, -9], [11, -2], [12, 5], [14.5, 9]], // la crête du fond
    sprinklers: [[57, 150], [57, 194], [58.5, 242], [74, 266], [95, 297], [116, 327], [136, 356], [154, 383]],
    north: 52,
  };
})();

// Trou 2 : par 3 tout en portée au-dessus de l'eau. Fer 7 à hauteur du drapeau, putt.
const H2 = (() => {
  const tee = [62, 0];
  const G = [58, 152];
  const u = [(G[0] - tee[0]) / dist(G, tee), (G[1] - tee[1]) / dist(G, tee)];
  const r = [u[1], -u[0]];
  const L = (d, l) => add(add(G, u, d), r, l);
  const pin = L(0, -7); // drapeau à gauche, à mi-profondeur
  return {
    theta: 0, pivot: [58, 80],
    tee, pin, G, u, r, L,
    box: [-30, -14, 122, 206],
    pageBox: [-30, -14, 112, 206], // sur la page du carnet, plus étroite : la lisière de droite est rognée
    teeBoxes: [{ c: [62, -3], w: 10, h: 13, ours: true }, { c: [70, 21], w: 8, h: 8 }],
    fairway: null,
    green: [[-14, 1], [-13, 7], [-8, 11], [0, 12], [8, 11], [13, 6], [14, -1], [11.5, -8], [5, -12], [-3, -12], [-9, -10.5], [-13, -6]],
    bunkers: [
      { id: 'green-droite', local: true, pts: [[-6, 15], [1, 15.5], [8, 15], [10, 20], [4, 23], [-4, 22], [-8, 19]] },
      { id: 'green-fond', local: true, pts: [[17, -7], [17.5, 0], [19.5, 6], [23.5, 4], [24, -4], [21.5, -9]] },
    ],
    water: [[32, 41], [55, 33], [79, 37], [96, 53], [102, 80], [95, 105], [79, 121], [61, 128.5], [47, 131.5], [39, 140], [35.5, 153], [31.5, 166], [21, 173], [10, 163], [5, 138], [11, 106], [9, 74], [17, 52]],
    lines: [
      { local: true, pts: [[23, -23], [31, -7], [32, 10], [27, 26], [15, 38], [-2, 44], [-21, 46]], side: -1 },
      { pts: [[104, 132], [112, 114], [116, 90], [117, 62], [112, 38], [104, 16], [98, -4]], side: 1 },
    ],
    trees: [[30, 10], [18, 24], [86, 6]],
    arcs: [],
    balls: [tee, L(0, -5.5), pin], // au départ, à droite du drapeau et à sa hauteur, dans le trou
    shots: [{}, { brk: 0.5 }],
    slopes: [
      { at: [8, 5], to: 200, pct: 1 }, { at: [8, -4], to: 215, pct: 2 }, { at: [0, 7], to: 205, pct: 1 }, { at: [4.5, 0.5], to: 225, pct: 1 },
      { at: [-8, 4], to: 190, pct: 2 }, { at: [-6, -6], to: 220, pct: 2 }, { at: [5.5, -8.5], to: 240, pct: 3 }, { at: [-11.5, -1], to: 185, pct: 3 },
    ],
    crest: null,
    north: -30,
  };
})();
export const GEOMETRY = [H1, H2];

// ---------- la géométrie mariée aux données de content/site.json
// Chaque trou reçoit : n, par, len ; depth, width, pinOn, pinSide (le green et le drapeau du jour) ;
// first (numéro de son premier arrêt) ; et pour chaque coup : k (numéro du coup dans le site, 0 à 5),
// len (total), carry (portée, 0 pour un putt), putt.
export function makeCourse(site) {
  return GEOMETRY.map((g, i) => {
    const data = site.holes[i];
    const first = site.stops.findIndex((s) => s.hole === data.n);
    const local = (p) => { const v = [p[0] - g.G[0], p[1] - g.G[1]]; return [v[0] * g.u[0] + v[1] * g.u[1], v[0] * g.r[0] + v[1] * g.r[1]]; };
    return {
      ...g,
      n: data.n, par: data.par, len: data.length,
      depth: data.green.depth, width: data.green.width, pinOn: data.pin.on, pinSide: data.pin.side,
      pinRight: local(g.pin)[1] > 0, // le drapeau est du côté droit du green : sa cote se prend du bord droit
      first, local,
      shots: g.shots.map((s, j) => {
        const next = site.next[first + j];
        return { ...s, k: first + j, len: next.total, carry: next.carry ?? 0, putt: next.carry == null };
      }),
    };
  });
}

// ---------- mesures (elles nourrissent les étiquettes du plan et la vérification des données)
// bunkers : distance du départ pour l'atteindre et pour le passer ; balls : distance au drapeau, au
// centre et à l'entrée du green ; shots : longueur de chaque coup ; sprinklers : distance à l'entrée
// du green ; water : portée pour passer l'eau sur la ligne départ → drapeau.
export function measures(h) {
  const world = (b) => (b.local ? b.pts.map(([d, l]) => h.L(d, l)) : b.pts);
  const front = h.L(-h.depth / 2, 0);
  const out = { bunkers: {} };
  for (const b of h.bunkers) {
    const poly = sample(world(b), 8);
    const ds = poly.map((p) => dist(p, h.tee));
    out.bunkers[b.id] = { reach: Math.round(Math.min(...ds)), carry: Math.round(Math.max(...ds)) };
  }
  out.balls = h.balls.map((b) => ({ toPin: dist(b, h.pin), toCentre: dist(b, h.G), toFront: dist(b, front), toBack: dist(b, h.L(h.depth / 2, 0)) }));
  out.shots = h.balls.slice(1).map((b, i) => dist(b, h.balls[i]));
  out.sprinklers = (h.sprinklers || []).map((s) => Math.round(dist(s, front)));
  if (h.water) {
    const poly = sample(h.water, 10);
    let far = 0;
    for (let t = 0; t <= 1; t += 0.001) {
      const p = lerp(h.tee, h.pin, t);
      if (inside(p, poly)) far = t;
    }
    out.water = far * dist(h.tee, h.pin);
  }
  return out;
}

// ---------- cadrages
// Le plan d'un trou se cadre de deux façons : une boîte à faire tenir (o.box, en mètres tournés de
// h.theta), ou une vue (o.view : { theta, at, to, k }) : le point « at » du trou est posé au point
// « to » de la page (px), à k px par mètre, le trou tourné de theta. M : mètres → px de la page.
export function frame(h, o) {
  if (o.view) {
    const { at, to, k, theta } = o.view;
    const c = Math.cos(rad(theta)), s = Math.sin(rad(theta));
    return { M: (p) => { const x = p[0] - at[0], y = p[1] - at[1]; return [to[0] + (x * c - y * s) * k, to[1] - (x * s + y * c) * k]; }, k, theta };
  }
  const pad = o.pad || [0, 0, 0, 0];
  const th = rad(h.theta);
  const c = Math.cos(th), s = Math.sin(th);
  const turn = (p) => [h.pivot[0] + (p[0] - h.pivot[0]) * c - (p[1] - h.pivot[1]) * s, h.pivot[1] + (p[0] - h.pivot[0]) * s + (p[1] - h.pivot[1]) * c];
  const [x0, y0, x1, y1] = o.box;
  const k = Math.min((o.w - pad[1] - pad[3]) / (x1 - x0), (o.h - pad[0] - pad[2]) / (y1 - y0));
  const ox = pad[3] + (o.w - pad[1] - pad[3] - (x1 - x0) * k) / 2;
  const oy = pad[0] + (o.h - pad[0] - pad[2] - (y1 - y0) * k) / 2;
  return { M: (p) => { const q = turn(p); return [ox + (q[0] - x0) * k, oy + (y1 - q[1]) * k]; }, k, theta: h.theta };
}

// Les trois cadrages de la page du carnet, pour une zone de dessin de w × hh px : tout le trou au
// départ ; le coup vers le green, la ligne de jeu à la verticale ; l'encart du green (la ligne de jeu
// monte dans la page, cx et cy : le centre du green). La maquette est réglée pour 250 × 464.
export const FRAMES = {
  hole: (h, w, hh) => ({ w, h: hh, box: h.pageBox || h.box }),
  approach: (h, w, hh) => {
    const a = h.approach;
    return { w, h: hh, view: { theta: (Math.atan2(h.u[0], h.u[1]) * 180) / Math.PI, at: add(h.balls[a.from], h.u, a.ahead), to: [w / 2 + 4, hh / 2], k: hh / a.span } };
  },
  green: (h, w, hh) => {
    // la hauteur de la page porte le green, l'avant-green où la balle attend et le bunker du fond
    const scale = Math.min(((7.4 * hh) / 464) * (34 / h.depth), (w - 43) / h.width);
    return { w, h: hh, scale, cx: w / 2 + 14, cy: (222 * hh) / 464 };
  },
};
// Le même repère pour l'encart du green : mètres du trou → px de la page.
export function greenFrame(h, o) {
  const k = o.scale;
  const cx = o.cx ?? o.w / 2, cy = o.cy ?? o.h / 2;
  const Lp = ([d, l]) => [cx + l * k, cy - d * k];
  return { Lp, M: (p) => Lp(h.local(p)), k };
}
