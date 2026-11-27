// Le dessin du carnet de parcours, en SVG : le plan d'un trou (plan) et l'encart de son green (green),
// tracés à partir de la géométrie en mètres de course.js. Les cotes imprimées sont mesurées, pas
// écrites. Les fonctions rendent le contenu d'un <svg> sous forme de texte : le terrain et ses cotes
// (décoratifs, aria-hidden), puis les points de chute, qui sont des liens vers leur arrêt, puis le coup
// en vol, que paintFlight fait avancer image par image sans repasser par React.
import { FRAMES, add, dist, frame, greenFrame, inside, lerp, measures, offset, rad, sample, spline, treeline } from './course.js';

const f = (n) => (Math.round(n * 100) / 100).toString();
const P = (p) => `${f(p[0])} ${f(p[1])}`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
let UID = 0;
const measured = new WeakMap();
const measure = (h) => {
  if (!measured.has(h)) measured.set(h, measures(h));
  return measured.get(h);
};

// Un point de chute : un lien vers son arrêt (o.links : { ids, labels } par numéro d'arrêt), avec une
// zone de clic plus large que le dessin. Sans o.links (languette, aperçu), le dessin seul.
function link(o, k, at, inner, cur) {
  if (!o.links) return inner;
  return `<a class="pt" href="#${o.links.ids[k]}" data-k="${k}" aria-label="${esc(o.links.labels[k])}"${cur ? ' aria-current="step"' : ''}><circle class="hit" cx="${f(at[0])}" cy="${f(at[1])}" r="${o.hit || 12}"/>${inner}</a>`;
}
// Le coup en vol : une ligne qui s'écrit de a vers b (courbée par c, ou en deux temps : portée en
// pointillé jusqu'à « carry », la croix de la chute, puis la roule) et la balle. Tout part de a.
// Rend la ligne (à glisser sous les points de chute) et la balle (par-dessus).
function flying(fly, r) {
  if (!fly) return { line: '', ball: '' };
  const { a, b, c, carry } = fly;
  const data = `data-a="${P(a)}" data-b="${P(b)}"${c ? ` data-c="${P(c)}"` : ''}${carry ? ` data-carry="${f(carry)}"` : ''}`;
  const land = carry ? lerp(a, b, carry) : null;
  return {
    line: `<g class="fly" aria-hidden="true" ${data}>${carry ? `<path class="shot air now fly-air" d="M${P(a)}"/><path class="land now fly-land" d="M${f(land[0] - 3)} ${f(land[1] - 3)}l6 6m0 -6l-6 6"/>` : ''}<path class="shot now fly-now" d="M${P(a)}"/></g>`,
    ball: `<g class="fly-ball" aria-hidden="true" transform="translate(${P(a)})"><circle class="ball-halo" r="${r[0]}"/><circle class="ball" r="${r[1]}"/></g>`,
  };
}
// Fait avancer le coup en vol dessiné dans « root » : r de 0 à 1, la part du coup parcourue.
export function paintFlight(root, r) {
  const g = root?.querySelector('.fly');
  if (!g) return;
  if (!g._fly) {
    const pt = (s) => (s ? s.split(' ').map(Number) : null);
    g._fly = { a: pt(g.dataset.a), b: pt(g.dataset.b), c: pt(g.dataset.c), carry: Number(g.dataset.carry) || 0, now: g.querySelector('.fly-now'), air: g.querySelector('.fly-air'), land: g.querySelector('.fly-land'), ball: g.parentNode.querySelector('.fly-ball') };
  }
  const { a, b, c, carry, now, air, land, ball } = g._fly;
  let p;
  if (c) {
    // une courbe : la part parcourue est elle-même une courbe, de a au point courant
    const q = lerp(a, c, r);
    p = lerp(q, lerp(c, b, r), r);
    now.setAttribute('d', `M${P(a)}Q${P(q)} ${P(p)}`);
  } else if (carry) {
    p = lerp(a, b, r);
    const l = lerp(a, b, carry);
    air.setAttribute('d', `M${P(a)}L${P(r < carry ? p : l)}`);
    now.setAttribute('d', r > carry ? `M${P(l)}L${P(p)}` : `M${P(a)}`);
    land.style.opacity = r >= carry ? 1 : 0;
  } else {
    p = lerp(a, b, r);
    now.setAttribute('d', `M${P(a)}L${P(p)}`);
  }
  ball.setAttribute('transform', `translate(${P(p)})`);
}

// ---------- le plan d'un trou
// o : w, h, box | view (cadrage), level ('mini' | 'page' | 'spread'), stop (arrêt courant du site),
// flight ({ shot } : le coup du trou en vol), every (tous les coups joués : la vue d'ensemble), mark
// (le point « vous êtes ici » de la vue d'ensemble), arcs ('green' | null), sprinklers ('num' | 'dot'),
// extras (cotes du carnet), fmt (écriture des nombres), links (les points sont des liens).
export function plan(h, o) {
  const id = `p${++UID}`;
  const { M, k, theta } = frame(h, o);
  const lvl = o.level || 'page';
  const mini = lvl === 'mini';
  const fmt = o.fmt || String;
  const world = (b) => (b.local ? b.pts.map(([d, l]) => h.L(d, l)) : b.pts);
  const px = (pts) => pts.map(M);
  const out = [];
  const pts = [];
  const m = measure(h);
  const defs = [
    `<pattern id="${id}s" width="3.6" height="3.6" patternUnits="userSpaceOnUse"><circle cx=".9" cy=".9" r=".45"/><circle cx="2.7" cy="2.7" r=".45"/></pattern>`,
    `<pattern id="${id}w" width="6" height="${mini ? 2.4 : 3.2}" patternUnits="userSpaceOnUse"><path d="M0 .5H6"/></pattern>`,
    `<clipPath id="${id}c"><rect x="0" y="0" width="${o.w}" height="${o.h}"/></clipPath>`,
  ];
  out.push(`<g clip-path="url(#${id}c)">`);
  // --- le terrain
  const step = lvl === 'spread' ? 8.5 : mini ? 4.6 : Math.max(7, Math.min(11, k * 7));
  if (!mini) for (const ln of h.lines.filter((_, i) => !o.skipLines?.includes(i))) out.push(`<path class="wood" d="${treeline(px(ln.local ? ln.pts.map(([d, l]) => h.L(d, l)) : ln.pts), step, ln.side)}"/>`);
  if (!mini) for (const t of h.trees) { const p = M(t); out.push(`<circle class="tree" cx="${f(p[0])}" cy="${f(p[1])}" r="${f(3.6 * k)}"/><circle class="tree-dot" cx="${f(p[0])}" cy="${f(p[1])}" r=".7"/>`); }
  const arcLabels = [];
  const greenPts = px(h.green.map(([d, l]) => h.L(d, l)));
  const collarD = `M${offset(sample(greenPts, 10), 2.4 * k).map(P).join('L')}Z`;
  defs.push(`<mask id="${id}m" maskUnits="userSpaceOnUse" x="-60" y="-60" width="${o.w + 120}" height="${o.h + 120}"><rect x="-60" y="-60" width="${o.w + 120}" height="${o.h + 120}" fill="#fff"/><path d="${collarD}" fill="#000"/></mask>`);
  if (h.fairway) {
    out.push(`<g mask="url(#${id}m)">`);
    const fw = sample(px(h.fairway), 10);
    if (!mini) out.push(`<path class="rough" d="M${offset(fw, 8 * k).map(P).join('L')}Z"/>`);
    // --- repères de distance : des arcs centrés sur l'entrée du green, tracés là où ils coupent le trou
    if (o.arcs && !mini) {
      const c = M(h.L(-h.depth / 2, 0));
      const wide = offset(fw, 12 * k);
      for (const R of h.arcs.filter((r) => !o.arcMax || r <= o.arcMax)) {
        const rr = R * k;
        let best = null, run = null;
        for (let a = 0; a <= 720; a += 0.5) {
          const p = [c[0] + rr * Math.cos(rad(a)), c[1] + rr * Math.sin(rad(a))];
          const ok = a < 720 && p[0] > 2 && p[0] < o.w - 2 && p[1] > 2 && p[1] < o.h - 2 && inside(p, wide);
          if (ok) { run = run || { a0: a }; run.a1 = a; } else if (run) { if (!best || run.a1 - run.a0 > best.a1 - best.a0) best = run; run = null; }
        }
        if (!best || (best.a1 - best.a0) * rad(1) * rr < 20) continue;
        const A = (a) => [c[0] + rr * Math.cos(rad(a)), c[1] + rr * Math.sin(rad(a))];
        const p0 = A(best.a0), p1 = A(best.a1);
        out.push(`<path class="arc" d="M${P(p0)}A${f(rr)} ${f(rr)} 0 0 1 ${P(p1)}"/>`);
        const useStart = p0[0] < p1[0];
        const e = A((useStart ? best.a0 : best.a1) + (useStart ? -1 : 1) * (9 / rr) * (180 / Math.PI));
        arcLabels.push(`<text class="t arc-t" x="${f(e[0])}" y="${f(e[1] + 3)}" text-anchor="middle">${R}</text>`);
      }
    }
    out.push(`<path class="fairway" d="${spline(px(h.fairway))}"/></g>`);
  }
  if (h.water) {
    const d = spline(px(h.water));
    out.push(`<path class="water" d="${d}"/><path class="water-h" d="${d}" fill="url(#${id}w)"/>`);
  }
  for (const t of h.teeBoxes) {
    const cnr = [[-t.w / 2, -t.h / 2], [t.w / 2, -t.h / 2], [t.w / 2, t.h / 2], [-t.w / 2, t.h / 2]].map(([a, b]) => M([t.c[0] + a, t.c[1] + b]));
    out.push(`<path class="teebox${t.ours ? ' ours' : ''}" d="M${cnr.map(P).join('L')}Z"/>`);
  }
  if (!mini) out.push(`<path class="collar" d="${collarD}"/>`);
  out.push(`<path class="green" d="${spline(greenPts)}"/>`);
  for (const b of h.bunkers) {
    const d = spline(px(world(b)));
    out.push(`<path class="bunker" d="${d}"/>${mini ? '' : `<path class="bunker-s" d="${d}" fill="url(#${id}s)"/>`}`);
  }
  // --- les arroseurs : un point dans le fairway, sa distance à l'entrée du green
  if (o.sprinklers && h.sprinklers && !mini) {
    h.sprinklers.forEach((s, i) => {
      const p = M(s);
      if (p[0] < 4 || p[0] > o.w - 4 || p[1] < 4 || p[1] > o.h - 4) return;
      out.push(`<circle class="sprk" cx="${f(p[0])}" cy="${f(p[1])}" r="2.1"/><circle class="sprk-dot" cx="${f(p[0])}" cy="${f(p[1])}" r=".7"/>`);
      if (o.sprinklers === 'num') out.push(`<text class="t sprk-t" x="${f(p[0] + 5.5)}" y="${f(p[1] + 3)}">${m.sprinklers[i]}</text>`);
    });
  }
  out.push(arcLabels.join(''));
  // --- le drapeau
  const pin = M(h.pin);
  const fl = mini ? 0.8 : lvl === 'spread' ? 1.25 : Math.max(1, Math.min(1.5, k));
  out.push(`<path class="flag" d="M${P(pin)}v${f(-15 * fl)}l${f(8 * fl)} ${f(3 * fl)}l${f(-8 * fl)} ${f(3 * fl)}"/><circle class="cup" cx="${f(pin[0])}" cy="${f(pin[1])}" r="${mini ? 1.2 : 1.6}"/>`);

  // --- les coups
  const here = o.stop - h.first; // la balle est sur le point « here » du trou (négatif : pas encore là ; au-delà : trou fini)
  const nb = h.balls.length;
  const B = h.balls.map(M);
  const path = (a, b, bend) => {
    if (!bend) return { d: `M${P(a)}L${P(b)}`, at: (t) => lerp(a, b, t), c: null };
    const mid = lerp(a, b, 0.5);
    const l = dist(a, b);
    const nrm = [(b[1] - a[1]) / l, -(b[0] - a[0]) / l];
    const c = add(mid, nrm, -bend * 2);
    return { d: `M${P(a)}Q${P(c)} ${P(b)}`, at: (t) => lerp(lerp(a, c, t), lerp(c, b, t), t), c };
  };
  const label = (cls, at, txt) => out.push(`<text class="t shot-t ${cls}" x="${f(at[0])}" y="${f(at[1] + 3.4)}" text-anchor="middle">${txt}</text>`);
  let fly = null;
  for (let i = 0; i < nb - 1; i++) {
    const sh = h.shots[i];
    const played = o.every || here > i;
    const next = !o.every && here === i && !o.flight;
    const inAir = o.flight && o.flight.shot === i;
    if (!played && !next && !inAir) continue;
    const a = B[i];
    const big = dist(B[i], B[i + 1]) > 30;
    if (next) {
      // la ligne de jeu : vers le drapeau (ou vers la zone, pour une mise en jeu de par 5), le repère de portée en travers
      const toPin = sh.aim !== 'zone';
      const b = toPin ? pin : B[i + 1];
      const c = path(a, b, toPin ? 0 : (sh.bend || 0) * k);
      out.push(`<path class="shot next" d="${c.d}"/>`);
      if (!mini && big) {
        const l = dist(a, b);
        const dir = [(b[0] - a[0]) / l, (b[1] - a[1]) / l], nrm = [-dir[1], dir[0]];
        const side = o.side?.[i] ?? 1;
        if (o.labels !== false) label('next', add(c.at(o.lenAt?.[i] ?? 0.5), nrm, 14 * side), fmt(toPin ? Math.round(m.balls[i].toPin) : sh.len));
        // le repère de portée, sauf s'il tombe sur le drapeau (un coup tout en portée)
        if (sh.carry && (!toPin || l - sh.carry * k > 14)) {
          const q = c.at((sh.carry * k) / l);
          const at = add(q, nrm, -13 * side);
          out.push(`<path class="carry" d="M${P(add(q, nrm, -5))}L${P(add(q, nrm, 5))}"/><text class="t carry-t" x="${f(at[0])}" y="${f(at[1] + 3)}" text-anchor="middle">${fmt(sh.carry)}</text>`);
        }
      }
      continue;
    }
    const c = path(a, B[i + 1], (sh.bend || 0) * k);
    if (inAir) {
      // la ligne s'écrit au fil du vol : le tracé complet en fantôme, la part parcourue par-dessus
      out.push(`<path class="shot ghost" d="${c.d}"/>`);
      fly = { a, b: B[i + 1], c: c.c };
      continue;
    }
    out.push(`<path class="shot done" d="${c.d}"/>`);
    if (!mini && big && o.labels !== false) {
      const l = dist(a, B[i + 1]);
      const nrm = [-(B[i + 1][1] - a[1]) / l, (B[i + 1][0] - a[0]) / l];
      label('done', add(c.at(o.lenAt?.[i] ?? 0.5), nrm, 14 * (o.side?.[i] ?? 1)), fmt(sh.len));
    }
  }
  // --- les points : un par arrêt du trou (le départ, puis chaque point de chute) ; ce sont les liens
  for (let i = 0; i < nb - 1; i++) {
    const p = B[i];
    const cur = (!o.flight && here === i && !o.every) || o.mark === i;
    const done = o.every || here > i || (o.flight && o.flight.shot >= i);
    if (mini) {
      out.push(cur ? `<circle class="ball-halo" cx="${f(p[0])}" cy="${f(p[1])}" r="5"/><circle class="ball" cx="${f(p[0])}" cy="${f(p[1])}" r="2.2"/>` : `<circle class="spot ${done ? 'done' : ''}" cx="${f(p[0])}" cy="${f(p[1])}" r="1.6"/>`);
      continue;
    }
    // les points serrés autour du trou (approche, putt) : une simple balle, l'encart du green les détaille
    const tight = i > 0 && dist(h.balls[i], h.balls[nb - 1]) < 30;
    if (tight && !o.tightNumbers) {
      out.push(cur ? `<circle class="ball-halo" cx="${f(p[0])}" cy="${f(p[1])}" r="6.5"/><circle class="ball" cx="${f(p[0])}" cy="${f(p[1])}" r="2.6"/>` : `<circle class="spot ${done ? 'done' : ''}" cx="${f(p[0])}" cy="${f(p[1])}" r="1.9"/>`);
      continue;
    }
    const r = lvl === 'spread' ? 7.5 : 7;
    pts.push(link(o, h.first + i, p, `<g class="stop ${cur ? 'cur' : done ? 'done' : 'todo'}">${cur ? `<circle class="ring" cx="${f(p[0])}" cy="${f(p[1])}" r="${f(r + 4)}"/>` : ''}<circle class="disc" cx="${f(p[0])}" cy="${f(p[1])}" r="${f(r)}"/><text class="t num" x="${f(p[0])}" y="${f(p[1] + 3.2)}" text-anchor="middle">${i + 1}</text></g>`, cur));
  }
  if (here >= nb - 1 && !o.every && !o.flight) out.push(`<circle class="ball-halo" cx="${f(pin[0])}" cy="${f(pin[1])}" r="${mini ? 4.6 : 6.5}"/>`);
  // le trou du dernier green mène au contact
  if (o.links && h.first + nb === o.links.ids.length && !mini) pts.push(link(o, h.first + nb - 1, pin, '', here === nb - 1 && !o.every && !o.flight));
  out.push('</g>');

  // --- les cotes du carnet : bunkers depuis le départ (pour l'atteindre · pour le passer), drapeau du jour, nord, échelle, vent
  const x = o.extras;
  if (x && !mini) {
    for (const c of x.callouts || []) {
      const poly = sample(px(world(h.bunkers.find((b) => b.id === c.id))), 6);
      const xs = poly.map((p) => p[0]), ys = poly.map((p) => p[1]);
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      const right = c.side !== 'left';
      const ax = right ? Math.max(...xs) + 4 : Math.min(...xs) - 4;
      const tx = ax + (right ? 10 : -10);
      const b = m.bunkers[c.id];
      const txt = c.carry ? `${b.reach}<tspan class="sep" dx="2.5">·</tspan><tspan dx="2.5">${b.carry}</tspan>` : `${b.reach}`;
      out.push(`<path class="lead" d="M${f(ax)} ${f(cy)}H${f(tx - (right ? 2.5 : -2.5))}"/><text class="t cap b" x="${f(tx)}" y="${f(cy + 3)}" text-anchor="${right ? 'start' : 'end'}">${txt}</text>`);
    }
    if (x.pin) {
      const g = sample(greenPts, 6);
      const left = x.pin.side === 'left';
      const gx = left ? Math.min(...g.map((p) => p[0])) - 10 : Math.max(...g.map((p) => p[0])) + 10;
      out.push(`<text class="t cap b" x="${f(gx + (x.pin.dx || 0))}" y="${f(pin[1] + (x.pin.dy || 0))}" text-anchor="${left ? 'end' : 'start'}">${h.pinOn}<tspan class="sep" dx="2.5">·</tspan><tspan dx="2.5">${h.pinSide} ${esc(x.pin.from)}</tspan></text>`);
    }
    if (x.ruler) {
      // trou tout droit : une règle en marge, graduée depuis le départ
      const rx = x.ruler.x;
      const t0 = M(h.tee);
      const ticks = x.ruler.ticks.map((tk) => ({ ...tk, y: t0[1] - tk.m * k }));
      const topY = Math.min(...ticks.map((tk) => tk.y));
      let d = `M${f(rx)} ${f(t0[1])}V${f(topY)}M${f(rx - 4)} ${f(t0[1])}h8`;
      for (let mm = 50; mm < h.len; mm += 50) d += `M${f(rx)} ${f(t0[1] - mm * k)}h-3`;
      out.push(`<path class="ruler" d="${d}${ticks.map((tk) => `M${f(rx)} ${f(tk.y)}h${tk.long ? -7 : -5}`).join('')}"/>`);
      for (const tk of ticks) out.push(`<text class="t cap ${tk.long ? 'b' : ''}" x="${f(rx - 10)}" y="${f(tk.y + 3)}" text-anchor="end"><tspan class="word">${esc(tk.label)}</tspan><tspan dx="5">${tk.m}</tspan></text>`);
    }
    if (x.north) out.push(north(x.north, h.north - theta));
    if (x.scale) out.push(scaleBar(x.scale, k));
    if (x.wind) {
      // le vent : une flèche dans le sens où il souffle, sa force à côté
      const [wx, wy] = x.wind.at;
      const a = rad(x.wind.to);
      const d = [Math.sin(a), -Math.cos(a)], n = [-d[1], d[0]];
      const tip = add([wx, wy], d, 11), tail = add([wx, wy], d, -11);
      const w1 = add(add(tip, d, -5.5), n, 3.2), w2 = add(add(tip, d, -5.5), n, -3.2);
      out.push(`<path class="windp" d="M${P(tail)}L${P(tip)}M${P(w1)}L${P(tip)}L${P(w2)}"/><text class="t cap b" x="${f(wx + 9)}" y="${f(wy - 2)}">${esc(x.wind.label)}</text><text class="t cap" x="${f(wx + 9)}" y="${f(wy + 8)}"><tspan class="word">${esc(x.wind.unit)}</tspan></text>`);
    }
  }
  const air = flying(fly, mini ? [5, 2.2] : [7.5, 3]);
  return { svg: `<defs>${defs.join('')}</defs><g aria-hidden="true">${out.join('')}</g>${air.line}<g clip-path="url(#${id}c)">${pts.join('')}</g>${air.ball}`, w: o.w, h: o.h, M, hole: h.n };
}

function north([nx, ny], angle) {
  const a = rad(angle);
  const d = [Math.sin(a), -Math.cos(a)], n = [-d[1], d[0]];
  const tip = add([nx, ny], d, 9), tail = add([nx, ny], d, -8);
  const w1 = add(add(tip, d, -6.5), n, 2.8), w2 = add(add(tip, d, -6.5), n, -2.8);
  const lab = add([nx, ny], d, 17);
  return `<path class="north" d="M${P(tail)}L${P(tip)}"/><path class="north-f" d="M${P(tip)}L${P(w1)}L${P(w2)}Z"/><text class="t cap" x="${f(lab[0])}" y="${f(lab[1] + 3)}" text-anchor="middle">N</text>`;
}
function scaleBar([sx, sy, len], k) {
  return `<path class="scale" d="M${f(sx)} ${f(sy - 3.5)}v3.5h${f(len * k)}v-3.5M${f(sx + (len * k) / 2)} ${f(sy)}v-2"/><text class="t cap" x="${f(sx + len * k + 6)}" y="${f(sy + 1)}">${len} m</text>`;
}

// ---------- l'encart du green : la ligne de jeu monte dans la page, d en profondeur, l vers la droite
// o : w, h, scale, cx, cy (cadrage), show (les coups du trou à tracer), numbers et lead (vue d'ensemble :
// pastilles numérotées, déportées par un filet), et comme pour le plan : stop, flight, every, mark, fmt, links.
export function green(h, o) {
  const id = `g${++UID}`;
  const { Lp, M: W, k } = greenFrame(h, o);
  const fmt = o.fmt || String;
  const cy = o.cy ?? o.h / 2;
  const out = [];
  const pts = [];
  const defs = [
    `<pattern id="${id}s" width="4" height="4" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".5"/><circle cx="3" cy="3" r=".5"/></pattern>`,
    `<pattern id="${id}w" width="6" height="3.4" patternUnits="userSpaceOnUse"><path d="M0 .5H6"/></pattern>`,
    `<clipPath id="${id}c"><rect x="0" y="0" width="${o.w}" height="${o.h}"/></clipPath>`,
  ];
  out.push(`<g clip-path="url(#${id}c)">`);
  for (const ln of h.lines) out.push(`<path class="wood" d="${treeline(ln.local ? ln.pts.map(Lp) : ln.pts.map(W), 11, ln.side)}"/>`);
  const gp = h.green.map(Lp);
  const col = `M${offset(sample(gp, 12), 2.2 * k).map(P).join('L')}Z`;
  defs.push(`<mask id="${id}m" maskUnits="userSpaceOnUse" x="0" y="0" width="${o.w}" height="${o.h}"><rect x="0" y="0" width="${o.w}" height="${o.h}" fill="#fff"/><path d="${col}" fill="#000"/></mask>`);
  if (h.fairway) {
    const fw = sample(h.fairway.map(W), 10);
    out.push(`<g mask="url(#${id}m)"><path class="rough" d="M${offset(fw, 8 * k).map(P).join('L')}Z"/><path class="fairway" d="${spline(h.fairway.map(W))}"/></g>`);
  }
  if (h.water) { const d = spline(h.water.map(W)); out.push(`<path class="water" d="${d}"/><path class="water-h" d="${d}" fill="url(#${id}w)"/>`); }
  out.push(`<path class="collar" d="${col}"/><path class="green" d="${spline(gp)}"/>`);
  for (const b of h.bunkers) {
    const d = spline(b.local ? b.pts.map(Lp) : b.pts.map(W));
    out.push(`<path class="bunker" d="${d}"/><path class="bunker-s" d="${d}" fill="url(#${id}s)"/>`);
  }
  // la crête
  if (h.crest) out.push(`<path class="crest" d="${spline(h.crest.map(Lp), false)}"/>`);
  // les pentes : une flèche dans le sens de la descente, le pourcentage à côté
  for (const s of h.slopes) {
    const p = Lp(s.at);
    const a = rad(s.to); // 180 = vers l'entrée (bas de page), 90 = vers la droite
    const dir = [Math.sin(a), -Math.cos(a)];
    const len = 5 + s.pct * 2.6;
    const a0 = add(p, dir, -len / 2), a1 = add(p, dir, len / 2);
    const nrm = [-dir[1], dir[0]];
    const h1 = add(add(a1, dir, -3.4), nrm, 1.9), h2 = add(add(a1, dir, -3.4), nrm, -1.9);
    out.push(`<path class="slope" d="M${P(a0)}L${P(a1)}M${P(h1)}L${P(a1)}L${P(h2)}"/>`);
    const t = add(p, nrm, 8.5);
    out.push(`<text class="t slope-t" x="${f(t[0])}" y="${f(t[1] + 2.6)}" text-anchor="middle">${s.pct}</text>`);
  }
  out.push('</g>');
  // --- la règle de profondeur, à gauche : 0 à l'entrée, un trait tous les 5 m
  const half = h.depth / 2;
  {
    const x = o.rulerX ?? 14;
    const y0 = cy + half * k, y1 = cy - half * k;
    let d = `M${f(x)} ${f(y0)}V${f(y1)}`;
    for (let mm = 0; mm <= h.depth; mm += 5) d += `M${f(x)} ${f(y0 - mm * k)}h${mm % 10 === 0 ? 5 : 3}`;
    d += `M${f(x)} ${f(y1)}h5`;
    out.push(`<path class="ruler" d="${d}"/>`);
    for (let mm = 0; mm <= h.depth - 3; mm += 10) out.push(`<text class="t ruler-t" x="${f(x - 4)}" y="${f(y0 - mm * k + 2.8)}" text-anchor="end">${mm}</text>`);
    out.push(`<text class="t ruler-t" x="${f(x - 4)}" y="${f(y1 + 2.8)}" text-anchor="end">${h.depth}</text>`);
  }
  // --- le drapeau du jour : sa cote au bord le plus proche
  const pinL = h.local(h.pin);
  const pin = Lp(pinL);
  {
    const sgn = h.pinRight ? 1 : -1;
    const edge = Lp([pinL[0], pinL[1] + sgn * h.pinSide]);
    out.push(`<path class="dim" d="M${P(edge)}L${P([pin[0] + sgn * 4, pin[1]])}M${f(edge[0])} ${f(edge[1] - 3)}v6"/>`);
    out.push(`<text class="t dim-t" x="${f((edge[0] + pin[0]) / 2 + sgn * 1)}" y="${f(pin[1] + (o.dimDy ?? -4))}" text-anchor="middle">${h.pinSide}</text>`);
  }
  // --- les coups joués sur et autour du green
  const here = o.stop - h.first;
  const nb = h.balls.length;
  const B = h.balls.map(W);
  let fly = null;
  for (let i = 0; i < nb - 1; i++) {
    if (!o.show?.includes(i)) continue;
    const a = B[i], b = B[i + 1];
    const sh = h.shots[i];
    const played = o.every || here > i;
    const inAir = o.flight && o.flight.shot === i;
    if (!played && !inAir && here !== i) continue; // le coup n'est pas encore à jouer
    const cls = played ? 'done' : 'next';
    const l = dist(a, b);
    const dir = [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
    const nrm = [-dir[1], dir[0]];
    if (sh.putt) {
      // le putt : une courbe légère, tournée vers le bas de la pente
      const brk = (sh.brk ?? 0) * k;
      const c = add(lerp(a, b, 0.55), nrm, brk);
      const d = `M${P(a)}Q${P(c)} ${P(b)}`;
      if (inAir) {
        out.push(`<path class="shot ghost" d="${d}"/>`);
        fly = { a, b, c };
      } else {
        out.push(`<path class="shot ${cls}" d="${d}"/>`);
        // la ligne de visée, droite, et le point visé au bord du trou
        if (!played && brk) out.push(`<path class="aim" d="M${P(a)}L${P(add(b, nrm, brk * 1.5))}"/>`);
      }
    } else if (sh.carry && sh.carry < sh.len) {
      // l'approche : la portée en pointillé, le point de chute, puis la roule
      const land = lerp(a, b, sh.carry / sh.len);
      if (inAir) {
        out.push(`<path class="shot ghost" d="M${P(a)}L${P(b)}"/>`);
        fly = { a, b, carry: sh.carry / sh.len };
      } else {
        out.push(`<path class="shot air ${cls}" d="M${P(a)}L${P(land)}"/><path class="shot ${cls}" d="M${P(land)}L${P(b)}"/>`);
        out.push(`<path class="land ${cls}" d="M${f(land[0] - 3)} ${f(land[1] - 3)}l6 6m0 -6l-6 6"/>`);
      }
    } else if (inAir) {
      out.push(`<path class="shot ghost" d="M${P(a)}L${P(b)}"/>`);
      fly = { a, b };
    } else {
      out.push(`<path class="shot ${cls}" d="M${P(a)}L${P(b)}"/>`);
    }
    if (!inAir) {
      const side = o.side?.[i] ?? -1;
      const at = add(add(lerp(a, b, o.lenAt?.[i] ?? 0.5), nrm, (o.lenOff?.[i] ?? 11) * side), o.lenShift?.[i] ?? [0, 0]);
      if (at[1] > 6 && at[1] < o.h - 6) out.push(`<text class="t shot-t ${cls}" x="${f(at[0])}" y="${f(at[1] + 3)}" text-anchor="middle">${fmt(sh.len)}</text>`);
    }
  }
  out.push(`<path class="flag" d="M${P(pin)}v-19l10 3.8l-10 3.8"/><circle class="cup" cx="${f(pin[0])}" cy="${f(pin[1])}" r="2"/>`);
  for (let i = 0; i < nb - 1; i++) {
    if (!o.show?.includes(i) && !o.show?.includes(i - 1)) continue;
    const p = B[i];
    if (p[1] > o.h + 4 || p[1] < -4) continue;
    const cur = (!o.flight && here === i && !o.every) || o.mark === i;
    const done = o.every || here > i || (o.flight && o.flight.shot >= i);
    if (!cur && !done) continue; // la balle n'y est pas encore passée
    const K = h.first + i;
    if (o.lead?.[i]) {
      // sur le green, la pastille numérotée est déportée : un filet la relie à la balle
      const q = add(p, o.lead[i]);
      const e = lerp(p, q, 1 - 6.4 / dist(p, q));
      out.push(`<path class="lead" d="M${P(p)}L${P(e)}"/><circle class="spot done" cx="${f(p[0])}" cy="${f(p[1])}" r="2.2"/>`);
      pts.push(link(o, K, q, `<g class="stop ${cur ? 'cur' : 'done'}"><circle class="disc" cx="${f(q[0])}" cy="${f(q[1])}" r="6.4"/><text class="t num" x="${f(q[0])}" y="${f(q[1] + 3.1)}" text-anchor="middle">${i + 1}</text></g>`, cur));
      continue;
    }
    if (h.shots[i].putt && !o.numbers) {
      pts.push(link(o, K, p, cur ? `<circle class="ball-halo" cx="${f(p[0])}" cy="${f(p[1])}" r="7"/><circle class="ball" cx="${f(p[0])}" cy="${f(p[1])}" r="2.8"/>` : `<circle class="spot ${done ? 'done' : ''}" cx="${f(p[0])}" cy="${f(p[1])}" r="2.4"/>`, cur));
      continue;
    }
    pts.push(link(o, K, p, `<g class="stop ${cur ? 'cur' : done ? 'done' : 'todo'}">${cur ? `<circle class="ring" cx="${f(p[0])}" cy="${f(p[1])}" r="10"/>` : ''}<circle class="disc" cx="${f(p[0])}" cy="${f(p[1])}" r="6.4"/><text class="t num" x="${f(p[0])}" y="${f(p[1] + 2.9)}" text-anchor="middle">${i + 1}</text></g>`, cur));
  }
  const holed = here >= nb - 1 && !o.every && !o.flight;
  if (holed) out.push(`<circle class="ball-halo" cx="${f(pin[0])}" cy="${f(pin[1])}" r="7"/>`);
  if (o.links && h.first + nb === o.links.ids.length) pts.push(link(o, h.first + nb - 1, pin, '', holed));
  if (o.north) out.push(north(o.north, h.north - (Math.atan2(h.u[0], h.u[1]) * 180) / Math.PI)); // le green est dessiné la ligne de jeu vers le haut
  if (o.scaleBar) out.push(scaleBar(o.scaleBar, k));
  const air = flying(fly, [7, 2.8]);
  return { svg: `<defs>${defs.join('')}</defs><g aria-hidden="true">${out.join('')}</g>${air.line}<g clip-path="url(#${id}c)">${pts.join('')}</g>${air.ball}`, w: o.w, h: o.h, M: W, hole: h.n };
}

// ---------- les vues toutes faites
// ctx (content.js, planCtx) : { fmt, pinFrom, marks (repères du par 3 : [{ m, label }]), wind ({ to, label, unit }), links }
// Les trois cadrages de la page (250 px de large) : 'hole', 'approach', 'green'.
export function pageView(h, name, w, hh, state, ctx) {
  const base = { ...FRAMES[name](h, w, hh), ...state, fmt: ctx.fmt, links: ctx.links };
  if (name === 'green') {
    const first = h.shots.findIndex((s) => s.len < 30); // les coups qui se jouent autour du green
    const show = h.shots.map((_, i) => i).filter((i) => i >= Math.max(0, first - (h.fairway ? 0 : 1)));
    return green(h, {
      ...base, rulerX: 24, show, north: [16, 28], scaleBar: [w - 54, 30, 5],
      ...(h.fairway ? { side: { 2: 1, 3: -1 }, lenAt: { 2: 0.7, 3: 0.5 } } : { side: { 1: -1 }, lenAt: { 1: 0 }, lenOff: { 1: 0 }, lenShift: { 1: [21, 0] }, dimDy: 11 }),
    });
  }
  if (name === 'approach') {
    return plan(h, { ...base, arcs: 'green', arcMax: 220, sprinklers: 'num', skipLines: [0], side: { 0: -1, 1: -1 }, lenAt: { 1: 0.44 }, extras: { pin: { from: ctx.pinFrom, dy: -12, dx: 8 }, north: [16, 28] } });
  }
  if (h.fairway) {
    return plan(h, { ...base, arcs: 'green', side: { 0: 1, 1: -1 }, extras: { callouts: [{ id: 'fairway-droite', carry: true }, { id: 'fairway-gauche', side: 'left' }], pin: { from: ctx.pinFrom, dy: -4 }, north: [16, 28], scale: [6, hh - 8, 100] } });
  }
  // le par 3, tout droit : une règle en marge depuis le départ, et la flèche du vent
  // (une bande est gardée en haut de la page pour le vent : pad)
  return plan(h, { ...base, pad: [46, 0, 0, 0], side: { 0: 1 }, extras: { ruler: { x: 58, ticks: ctx.marks.map((x) => ({ ...x, long: x.m === h.len })) }, pin: { from: ctx.pinFrom, dy: -26, dx: -6 }, north: [w - 22, hh - 30], wind: { at: [w - 40, 26], ...ctx.wind } } });
}

// La languette : le trou en tout petit, la balle à sa place.
export const miniView = (h, w, hh, stop, flight = null) => plan(h, { w, h: hh, box: h.box, stop, flight, level: 'mini' });

// Le carnet ouvert : le plan du trou et l'encart du green, tous les coups joués, « vous êtes ici ».
// size : 'wide' (la double page) ou 'narrow' (une page par trou, sur téléphone).
export function spreadViews(h, size, mark, ctx) {
  const wide = size === 'wide';
  const state = { stop: 99, every: true, mark, level: 'spread', fmt: ctx.fmt, links: ctx.links };
  const one = !!h.fairway;
  const pw = wide ? 236 : 150;
  const ph = wide ? (one ? 606 : 372) : one ? 430 : 250;
  const extras = one
    ? { ...(wide ? { callouts: [{ id: 'fairway-droite', carry: true }, { id: 'fairway-gauche', side: 'left' }], pin: { from: ctx.pinFrom, dy: -4 }, scale: [4, ph - 8, 100] } : {}), north: wide ? [18, 30] : [14, 26] }
    : { ...(wide ? { ruler: { x: 58, ticks: ctx.marks.map((x) => ({ ...x, long: x.m === h.len })) }, wind: { at: [pw - 34, 46], ...ctx.wind } } : {}), north: [pw - 22, ph - 30] };
  const p = plan(h, { ...state, w: pw, h: ph, box: h.box, ...(one ? { arcs: 'green', sprinklers: 'dot', side: { 0: 1, 1: -1 } } : { side: { 0: 1 } }), extras });
  const gw = wide ? 312 : 354;
  const gh = wide ? 244 : 230;
  const g = green(h, {
    ...state, w: gw, h: gh, numbers: true, rulerX: wide ? 30 : 34, cx: wide ? 168 : 190, cy: wide ? 120 : 112, scaleBar: [gw - 60, 20, 5],
    ...(one
      ? { scale: wide ? 5.5 : 5.4, show: [2, 3], lead: { 3: [22, 5] }, side: { 2: 1, 3: -1 }, lenAt: { 2: 0.7, 3: 0.5 } }
      : { scale: wide ? 6.8 : 6.6, show: [1], lead: { 1: [25, -15] }, side: { 1: -1 }, lenOff: { 1: 12 }, lenShift: { 1: [3, 1] }, dimDy: 11 }),
  });
  return { plan: p, green: g };
}

// Le passage d'un cadrage à l'autre, pour deux vues du même trou : la similitude (rotation, échelle,
// glissement, autour du centre de la page) qui amène le dessin « from » sur le dessin « to ».
// Rend { r (degrés), s, x, y } pour « transform: rotate(r) scale(s) translate(x, y) », ou null.
export function between(from, to, h) {
  if (!from || !to || from.hole !== to.hole || from.w !== to.w || from.h !== to.h) return null;
  const A = h.tee, B = h.pin;
  const a = from.M(A), b = from.M(B), a2 = to.M(A), b2 = to.M(B);
  const s = dist(a2, b2) / dist(a, b);
  let r = Math.atan2(b2[1] - a2[1], b2[0] - a2[0]) - Math.atan2(b[1] - a[1], b[0] - a[0]);
  if (r > Math.PI) r -= 2 * Math.PI;
  if (r < -Math.PI) r += 2 * Math.PI;
  const c = [from.w / 2, from.h / 2];
  // x' = c + s·R(r)·(x − c + d) : d tel que a arrive sur a2
  const v = [(a2[0] - c[0]) / s, (a2[1] - c[1]) / s];
  const cos = Math.cos(-r), sin = Math.sin(-r);
  const d = [v[0] * cos - v[1] * sin - (a[0] - c[0]), v[0] * sin + v[1] * cos - (a[1] - c[1])];
  if (Math.abs(s - 1) < 1e-4 && Math.abs(r) < 1e-4 && Math.hypot(d[0], d[1]) < 0.05) return null;
  return { r: (r * 180) / Math.PI, s, x: d[0], y: d[1] };
}
