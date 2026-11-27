// Le film rendu dans Blender (Cycles), rejoué sur un canvas 2D.
//
// Format de public/frames (PLAN.md, section 4) : sept arrêts, six trajets.
//   <taille>/h_<kk>.webp        image nette de l'arrêt k : grande, propre, c'est elle qu'on regarde ;
//   <taille>/l<k>_<nnnn>.webp   image n (à partir de 1) du trajet k → k+1, avec flou de mouvement.
// Avancer d'un arrêt joue le trajet à la cadence du manifeste (27 images par seconde). À l'arrivée,
// l'image nette remplace la dernière image du trajet par un fondu d'un tiers de seconde, puis la vue
// dérive très lentement : l'image ne ressemble jamais à une vidéo en pause. Reculer, sauter plusieurs
// arrêts, ou avancer alors que le trajet est absent ou pas encore chargé : fondu d'un arrêt à l'autre.
// Pendant un trajet, le lecteur dit à chaque image où il en est au magasin d'état du vol (flight.js) :
// le carnet, le traceur et la ligne du tour s'y abonnent pour avancer avec la balle.
import { flight } from './flight.js';

const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const ease = (t) => t * t * (3 - 2 * t);
const pad = (n, len) => String(n).padStart(len, '0');
const BG = '#0a1410';
const ORDER = ['s', 'm', 'l'];

// Écran vertical : même seuil que la mise en page « téléphone » de styles.css.
export const isPortrait = () => window.innerWidth / window.innerHeight < 0.9;

// Écran horizontal : la part de la largeur où se tient la balle (fx : sa place dans l'image). Elle garde
// sa place dans le cadre ; plus la fenêtre est étroite, plus on la pousse vers la droite, pour laisser
// la gauche au texte. Le carnet s'en sert pour savoir s'il a la place de s'ouvrir sans la recouvrir.
export const ballAt = (fx = 0.62, w = window.innerWidth, h = window.innerHeight) => fx + (0.74 - fx) * clamp((16 / 9 - w / h) / (16 / 9 - 0.9), 0, 1);

// Quelle taille de fichier pour cet écran. L'image est recadrée pour couvrir l'écran : sur un téléphone
// tenu debout on n'en voit qu'une bande, il faut donc une image bien plus large que l'écran.
// Les images nettes et les images de trajet se choisissent séparément (le flou pardonne plus) ; un
// petit écran ne reçoit jamais la plus grande image nette (mémoire) et prend les trajets les plus légers.
export function pickSizes(manifest) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const cw = window.innerWidth * dpr;
  const ch = window.innerHeight * dpr;
  const need = Math.max(cw, (ch * manifest.width) / manifest.height);
  const names = ORDER.filter((k) => manifest.sizes?.[k]);
  const pick = (kind, slack) => names.find((k) => manifest.sizes[k][kind] >= need * slack) || names[names.length - 1];
  const small = Math.min(window.innerWidth, window.innerHeight) < 600;
  let hold = pick('hold', 0.85);
  if (small && hold === 'l' && names.includes('m')) hold = 'm';
  return { hold, motion: small ? names[0] : pick('motion', 0.7) };
}

// Économiseur de données : comme pour les animations réduites, on ne charge pas les trajets.
export const savesData = () => !!navigator.connection?.saveData;

export class Film {
  constructor(canvas, { manifest, sizes, reduce, still = reduce, start = 0, onReady, onProgress }) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d', { alpha: false });
    this.m = manifest;
    this.sizes = sizes;
    this.reduce = reduce;
    this.cb = { onReady, onProgress };
    // Le serveur ajoute « v » au manifeste : les images sont gardées longtemps en cache, ce numéro les renouvelle.
    this.query = manifest.v ? `?v=${encodeURIComponent(manifest.v)}` : '';
    this.fps = manifest.fps || 27;
    this.stops = manifest.stops;
    // Nombre d'images de chaque trajet k → k+1 (0 : pas de trajet, la page fera un fondu).
    // « still » : animations réduites ou économiseur de données, aucun trajet n'est chargé.
    this.legs = this.stops.slice(0, -1).map((_, k) => (still ? 0 : manifest.legs?.find((l) => l.from === k && l.to === k + 1)?.frames || 0));
    this.holds = [];
    this.frames = this.legs.map(() => []);
    this.count = this.legs.map(() => 0);
    this.wanted = new Set();
    this.stop = clamp(start, 0, this.stops.length - 1);
    this.anim = null; // trajet en cours
    this.fade = null; // fondu en cours
    this.under = null; // dernière image du trajet, sous l'image nette qui arrive
    this.view = { s: 1, x: 0, y: 0 };
    this.rest = 0;
    this.hdAlpha = 0;
    this.last = '';
    this.drawn = 0;
    this.loaded = 0;
    this.total = 1;
    this.ready = false;
    this.alive = true;
    this.now = performance.now();
    this.snap = document.createElement('canvas');
    this.resize = this.resize.bind(this);
    window.addEventListener('resize', this.resize);
    this.resize();
    this.load();
    const tick = () => {
      if (!this.alive) return;
      this.tick();
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
  }

  // ---- chargement : l'arrêt courant, le prochain trajet du grossier au fin, son arrivée, puis les
  // autres trajets en commençant par le plus proche, enfin le reste des images nettes.
  load() {
    const queue = [];
    const n = this.stops.length;
    const near = [];
    for (let k = this.stop; k < n - 1; k++) near.push(k);
    for (let k = this.stop - 1; k >= 0; k--) near.push(k);
    const pass = (k, step) => {
      for (let i = 0; i < this.legs[k]; i += step) queue.push({ leg: k, i });
      if (this.legs[k]) queue.push({ leg: k, i: this.legs[k] - 1 }); // la dernière image : c'est sur elle qu'on se pose
    };
    queue.push({ hold: this.stop });
    near.forEach((k, j) => {
      pass(k, 6);
      pass(k, 3);
      queue.push({ hold: k + 1 });
      if (j === 0) pass(k, 1);
    });
    near.forEach((k) => pass(k, 1));
    for (let k = 0; k < n; k++) queue.push({ hold: k });
    // Les passes grossières remettent certaines images en file : on garde la première.
    const seen = new Set();
    this.queue = queue.filter((job) => {
      const key = job.hold !== undefined ? `h${job.hold}` : `${job.leg}_${job.i}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    this.total = this.queue.length;
    // L'image de l'arrêt courant part seule : c'est elle qu'on attend, elle a toute la bande passante.
    // Les six files du reste démarrent quand elle est arrivée et que la page a fini de se charger.
    this.pump();
  }

  pump() {
    if (!this.alive) return;
    // Passent devant : l'image nette de l'arrêt courant ou celle qu'on attend ; pendant un vol parti
    // avec une image sur trois, celles qui manquent encore devant la balle ; puis le trajet qui part de
    // l'arrêt courant.
    let idx = this.queue.findIndex((job) => job.hold !== undefined && (job.hold === this.stop || this.wanted.has(job.hold)));
    const a = this.anim;
    if (idx < 0 && a) {
      const at = ((this.now - a.t0) / 1000) * this.fps + 2; // deux images d'avance : le temps du téléchargement
      idx = this.queue.findIndex((job) => job.leg === a.leg && job.i >= at);
    }
    if (idx < 0) idx = this.queue.findIndex((job) => job.leg === this.stop);
    if (idx < 0) idx = 0;
    const job = this.queue.splice(idx, 1)[0];
    if (!job) return;
    const isHold = job.hold !== undefined;
    const img = new Image();
    img.decoding = 'async';
    const done = () => {
      this.loaded += 1;
      this.cb.onProgress?.(this.loaded / this.total);
      // Même si la première image manque, la page doit s'ouvrir.
      if (!this.ready && isHold) {
        this.ready = true;
        this.cb.onReady?.();
        // Le reste du film attend que la page ait fini de se charger (événement « load ») : chaque image
        // lancée avant le retarde, et l'onglet du navigateur tournerait tant que tout le film n'est pas là.
        let started = false;
        const rest = () => {
          if (started) return;
          started = true;
          for (let k = 0; k < 6; k++) this.pump();
        };
        if (document.readyState === 'complete') rest();
        else {
          window.addEventListener('load', () => setTimeout(rest, 0), { once: true });
          setTimeout(rest, 2500);
        }
        return;
      }
      this.pump();
    };
    img.onload = () => {
      if (isHold) {
        this.holds[job.hold] = img;
        this.wanted.delete(job.hold);
      } else {
        this.frames[job.leg][job.i] = img;
        this.count[job.leg] += 1;
      }
      this.last = '';
      done();
    };
    img.onerror = done;
    img.src = isHold
      ? `/frames/${this.sizes.hold}/h_${pad(job.hold, 2)}.webp${this.query}`
      : `/frames/${this.sizes.motion}/l${job.leg}_${pad(job.i + 1, 4)}.webp${this.query}`;
  }

  resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(window.innerWidth * dpr);
    this.canvas.height = Math.round(window.innerHeight * dpr);
    this.dpr = dpr;
    this.portrait = isPortrait();
    this.last = '';
  }

  // Où dessiner l'image pour qu'elle couvre l'écran, selon l'endroit où se trouve la balle (0 à 1).
  place([fx, fy]) {
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const s = Math.max(cw / this.m.width, ch / this.m.height);
    const dw = this.m.width * s;
    const dh = this.m.height * s;
    if (this.portrait) {
      // Téléphone : la balle au milieu de la largeur et dans le tiers haut, la fiche occupe le bas.
      // L'image remonte donc, et le bas de l'écran reste dans la couleur du fond, sous le dégradé.
      // Sur un petit téléphone la fiche monte plus haut : la balle aussi.
      const ty = window.innerHeight < 720 ? 0.27 : 0.31;
      return { dx: clamp(cw / 2 - fx * dw, cw - dw, 0), dy: clamp(ch * ty - fy * dh, -0.34 * ch, 0), dw, dh };
    }
    // Écran horizontal : voir ballAt.
    const tx = ballAt(fx, cw, ch);
    return { dx: clamp(cw * tx - fx * dw, cw - dw, 0), dy: fy * (ch - dh), dw, dh };
  }

  // ---- déplacements
  want(k) {
    if (!this.holds[k]) this.wanted.add(k);
  }

  // Assez d'images pour jouer le trajet k : une sur trois, la passe grossière.
  playable(k) {
    return this.legs[k] > 0 && this.count[k] * 3 >= this.legs[k];
  }

  // Aller à l'arrêt « to ». Renvoie true si le trajet est joué, false si c'est un fondu.
  go(to, done) {
    const from = this.stop;
    this.want(to);
    if (this.anim || this.fade) {
      // Un déplacement était en cours : il est remplacé (son « done » n'est pas appelé).
      this.anim = null;
      flight.rest();
      this.dissolve(to, done);
      return false;
    }
    if (to === from) {
      done?.();
      return false;
    }
    if (to === from + 1 && this.playable(from)) {
      this.stop = to;
      this.under = null;
      this.anim = { leg: from, t0: this.now, done };
      flight.begin(from, this.legs[from], this.m.legs?.find((l) => l.from === from && l.to === to));
      // L'image nette de l'arrivée sera prête à être peinte quand la balle se posera.
      this.holds[to]?.decode?.().catch(() => {});
      return true;
    }
    this.dissolve(to, done);
    return false;
  }

  // Un geste pendant le vol : on saute à l'arrivée.
  skip() {
    const a = this.anim;
    if (!a) return false;
    this.anim = null;
    flight.finish();
    this.dissolve(
      a.leg + 1,
      () => {
        a.done?.();
        flight.rest();
      },
      260,
    );
    return true;
  }

  dissolve(to, done, ms = 520) {
    this.snap.width = this.canvas.width;
    this.snap.height = this.canvas.height;
    this.snap.getContext('2d').drawImage(this.canvas, 0, 0);
    this.stop = to;
    this.anim = null;
    this.under = null;
    this.rest = 0;
    this.hdAlpha = 1;
    // t0 reste vide tant que l'image d'arrivée n'est pas là ; la page, elle, n'attend pas plus d'une seconde.
    this.fade = { t0: null, since: this.now, dur: this.reduce ? 160 : ms, done };
    this.want(to);
    this.last = '';
  }

  // ---- dessin
  nearest(k, i) {
    const imgs = this.frames[k];
    for (let d = 0; d < this.legs[k]; d++) {
      if (imgs[i - d]) return imgs[i - d];
      if (imgs[i + d]) return imgs[i + d];
    }
    return null;
  }

  // À défaut d'image nette : la fin du trajet qui arrive à cet arrêt, ou le début de celui qui en part.
  fallback(k) {
    return (k > 0 && this.legs[k - 1] ? this.nearest(k - 1, this.legs[k - 1] - 1) : null) || (this.legs[k] ? this.frames[k][0] : null) || null;
  }

  // La carte de score couvre tout l'écran : inutile de redessiner le film dessous (la dérive
  // tourne sinon en permanence, et gêne le défilement sur un téléphone modeste).
  sleep(asleep) {
    this.asleep = asleep;
    this.last = '';
  }

  tick() {
    const now = performance.now();
    const dt = Math.min(0.05, (now - this.now) / 1000);
    this.now = now;
    if (this.asleep && !this.anim && !this.fade) return;
    let focus = this.stops[this.stop].focus;
    let base = null;
    let key = `s${this.stop}`;
    const a = this.anim;
    if (a) {
      const n = this.legs[a.leg];
      const f = ((now - a.t0) / 1000) * this.fps;
      if (f >= n - 1) {
        // Posé : la dernière image du trajet reste dessous pendant que l'image nette arrive.
        this.anim = null;
        this.under = this.nearest(a.leg, n - 1);
        this.hdAlpha = 0;
        this.rest = 0;
        flight.finish();
        a.done?.();
        flight.rest();
      } else {
        flight.at(f);
        const i = Math.round(f);
        base = this.nearest(a.leg, i);
        key = `l${a.leg}_${i}`;
        const t = ease(f / (n - 1));
        const from = this.stops[a.leg].focus;
        const to = this.stops[a.leg + 1].focus;
        focus = [from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t];
      }
    }
    const moving = !!this.anim;
    this.rest = moving ? 0 : this.rest + dt;
    let hd = null;
    if (!moving) {
      hd = this.holds[this.stop] || null;
      base = this.under || (hd ? null : this.fallback(this.stop));
      // L'image nette monte en un tiers de seconde sur la dernière image du trajet.
      this.hdAlpha = hd ? clamp(this.hdAlpha + dt / 0.33, 0, 1) : 0;
      if (hd && this.hdAlpha >= 1) this.under = null;
    }

    // Dérive lente à l'arrêt (un léger zoom, un glissement infime) ; retour au cadre pendant un trajet.
    const v = this.view;
    const tgt =
      !moving && !this.reduce
        ? { s: 1 + (0.03 * (1 - Math.cos((this.rest * 2 * Math.PI) / 36))) / 2, x: 6 * Math.sin((this.rest * 2 * Math.PI) / 47), y: 3 * Math.sin((this.rest * 2 * Math.PI) / 39) }
        : { s: 1, x: 0, y: 0 };
    const k = 1 - Math.exp(-dt * (moving ? 5 : 1.2));
    v.s += (tgt.s - v.s) * k;
    v.x += (tgt.x - v.x) * k;
    v.y += (tgt.y - v.y) * k;

    const fade = this.fade;
    if (fade) {
      // Le fondu ne démarre que lorsqu'il y a quelque chose à montrer ; la page est prévenue au plus tard après 0,9 s.
      if (fade.t0 === null && (hd || base)) fade.t0 = now;
      if (fade.done && fade.t0 === null && now - fade.since > 900) {
        const done = fade.done;
        fade.done = null;
        done();
      }
    }
    const fading = fade ? (fade.t0 === null ? 0 : clamp((now - fade.t0) / fade.dur, 0, 1)) : 1;
    const drifting = Math.abs(v.s - 1) > 0.0004 || Math.abs(v.x) > 0.2;
    const state = `${key}|${base ? 1 : 0}|${hd ? 1 : 0}`;
    const busy = moving || fade || (hd && this.hdAlpha < 1);
    if (state === this.last && !busy && (!drifting || now - this.drawn < 40)) return;
    if (!base && !hd) return;
    this.last = state;
    this.drawn = now;

    const { ctx } = this;
    const cw = this.canvas.width;
    const ch = this.canvas.height;
    const { dx, dy, dw, dh } = this.place(focus);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    if (this.portrait) {
      ctx.fillStyle = BG;
      ctx.fillRect(0, 0, cw, ch);
    }
    ctx.setTransform(v.s, 0, 0, v.s, (cw / 2) * (1 - v.s) + v.x * this.dpr, (ch / 2) * (1 - v.s) + v.y * this.dpr);
    if (base && !(hd && this.hdAlpha >= 1)) ctx.drawImage(base, dx, dy, dw, dh);
    if (hd) {
      ctx.globalAlpha = base ? this.hdAlpha : 1;
      ctx.drawImage(hd, dx, dy, dw, dh);
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    if (fade) {
      if (fading < 1) {
        ctx.globalAlpha = 1 - ease(fading);
        // Étirée à la taille du canvas : la fenêtre a pu changer de taille (ou le téléphone tourner) pendant le fondu.
        ctx.drawImage(this.snap, 0, 0, cw, ch);
      } else {
        this.fade = null;
        fade.done?.();
      }
    }
    ctx.globalAlpha = 1;
  }

  dispose() {
    this.alive = false;
    flight.rest();
    cancelAnimationFrame(this.raf);
    window.removeEventListener('resize', this.resize);
  }
}
