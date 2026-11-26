// Petit serveur du site : il sert la version construite (dist/), répond à /api/health, et écrit le
// texte du site dans la page. Avant d'envoyer index.html, il glisse dans <div id="root"> une version
// texte tirée de content/site.json (accueil, les cinq projets, parcours, contact) et, dans l'en-tête,
// le titre, la description, les balises de partage et les données structurées : les robots et les
// lecteurs sans JavaScript ont tout le contenu. React remplace ce texte au montage.
import express from 'express';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const dist = join(root, 'dist');
const PORT = Number(process.env.PORT) || 3003;
const site = JSON.parse(readFileSync(join(root, 'content/site.json'), 'utf8'));
// Les images du film gardent leur nom d'un rendu à l'autre : ce numéro, ajouté au manifeste puis à
// chaque adresse d'image, change à chaque mise en ligne et permet un cache d'un an.
const VERSION = (process.env.RAILWAY_GIT_COMMIT_SHA || '').slice(0, 10) || Date.now().toString(36);

const app = express();
app.disable('x-powered-by');
app.set('trust proxy', 1);
app.use((_req, res, next) => {
  res.setHeader(
    'Content-Security-Policy',
    [
      "default-src 'self'",
      "script-src 'self'",
      "style-src 'self' 'unsafe-inline'",
      "font-src 'self'",
      "img-src 'self' data: blob:",
      "connect-src 'self'",
      "object-src 'none'",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join('; '),
  );
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
  res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
  next();
});

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// ---- la version texte
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const fr = (v) => (v && typeof v === 'object' ? (v.fr ?? '') : (v ?? ''));
const t = site.ui.fr;
const intro = site.stops.find((s) => s.kind === 'intro');
const contact = site.stops.find((s) => s.kind === 'contact');
const projects = site.stops.filter((s) => s.kind === 'project');
const ext = (url, label) => `<a href="${esc(url)}" rel="noopener">${esc(label)}</a>`;

function projectHtml(p) {
  const links = [p.links?.demo && ext(p.links.demo, t.viewDemo), p.links?.code && ext(p.links.code, t.viewCode)].filter(Boolean);
  return [
    `<article id="${esc(p.id)}">`,
    `<p class="label">${esc(fr(p.label))}</p>`,
    `<h3>${esc(p.name)}</h3>`,
    `<p><em>${esc(fr(p.concept))}</em></p>`,
    `<p>${esc(fr(p.sentence))}</p>`,
    `<p><strong>${esc(t.result)}&nbsp;:</strong> ${esc(fr(p.result))}</p>`,
    `<p><strong>${esc(t.tools)}&nbsp;:</strong> ${esc(p.tools.join(', '))}</p>`,
    `<p><strong>${esc(t.problem)}.</strong> ${esc(fr(p.case.problem))}</p>`,
    `<p><strong>${esc(t.built)}.</strong></p>`,
    `<ol>${p.case.built.map((b) => `<li>${esc(fr(b))}</li>`).join('')}</ol>`,
    `<p><strong>${esc(t.flow)}&nbsp;:</strong> ${p.case.flow.map((f) => esc(fr(f))).join(' → ')}</p>`,
    `<p><strong>${esc(t.outcome)}.</strong> ${esc(fr(p.case.outcome))}</p>`,
    `<p><strong>${esc(t.role)}.</strong> ${esc(fr(p.case.role))}</p>`,
    links.length ? `<p>${links.join(' · ')}</p>` : '',
    '</article>',
  ].join('');
}

const staticHtml = [
  '<div class="static">',
  '<header>',
  `<p class="label">${esc(fr(intro.label))}</p>`,
  `<h1>${esc(site.meta.name)}</h1>`,
  `<p><strong>${esc(fr(intro.title))}</strong></p>`,
  `<p>${esc(fr(intro.body))}</p>`,
  `<noscript><p>${esc(t.noScript)}</p></noscript>`,
  `<nav aria-label="${esc(t.stops)}"><ul>${[...projects.map((p) => `<li><a href="#${esc(p.id)}">${esc(p.name)}</a></li>`), `<li><a href="#${esc(contact.id)}">${esc(t.contact)}</a></li>`].join('')}</ul></nav>`,
  '</header>',
  '<main>',
  `<section><h2>${esc(t.projects)}</h2>${projects.map(projectHtml).join('')}</section>`,
  `<section><h2>${esc(t.journey)}</h2>${site.about.journey.map((j) => `<article><h3>${esc(fr(j.org))}</h3><p><strong>${esc(fr(j.role))}</strong> · ${esc(fr(j.period))}</p><p>${esc(fr(j.text))}</p></article>`).join('')}</section>`,
  `<section><h2>${esc(t.skills)}</h2><ul>${site.about.skills.map((s) => `<li><strong>${esc(fr(s.name))}</strong> : ${esc(s.items.join(', '))}. ${esc(fr(s.text))}</li>`).join('')}</ul></section>`,
  `<section><h2>${esc(t.certifications)}</h2><ul>${site.about.certifications.map((c) => `<li>${esc(fr(c.title))} · ${esc(fr(c.issuer))}</li>`).join('')}</ul></section>`,
  `<section id="${esc(contact.id)}"><h2>${esc(t.contact)}</h2><h3>${esc(fr(contact.title))}</h3><p>${esc(fr(contact.body))}</p>`,
  `<p><a href="mailto:${esc(contact.email)}">${esc(contact.email)}</a></p>`,
  `<ul>${contact.links.map((l) => `<li>${ext(l.url, l.label)}</li>`).join('')}</ul></section>`,
  '</main>',
  `<footer><p>${esc(t.credits)}</p></footer>`,
  '</div>',
].join('');

// ---- l'en-tête : titre, description, partage (image en adresse absolue), données structurées
function headHtml(origin) {
  const title = fr(site.meta.title);
  const description = fr(site.meta.description);
  const image = `${origin}/frames/poster.webp?v=${VERSION}`;
  const person = {
    '@context': 'https://schema.org',
    '@type': 'Person',
    name: site.meta.name,
    jobTitle: fr(intro.title),
    description,
    url: `${origin}/`,
    email: `mailto:${contact.email}`,
    image,
    sameAs: contact.links.map((l) => l.url),
    worksFor: site.about.journey.filter((j) => j.current).map((j) => ({ '@type': 'Organization', name: fr(j.org) }))[0],
    alumniOf: site.about.journey.filter((j) => j.kind === 'school').map((j) => ({ '@type': 'EducationalOrganization', name: fr(j.org) })),
    knowsAbout: site.about.skills.flatMap((s) => s.items),
  };
  return [
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(description)}" />`,
    `<link rel="canonical" href="${esc(origin)}/" />`,
    '<meta property="og:type" content="profile" />',
    `<meta property="og:site_name" content="${esc(site.meta.name)}" />`,
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(description)}" />`,
    `<meta property="og:url" content="${esc(origin)}/" />`,
    `<meta property="og:image" content="${esc(image)}" />`,
    '<meta property="og:locale" content="fr_FR" />',
    '<meta property="og:locale:alternate" content="en_GB" />',
    '<meta name="twitter:card" content="summary_large_image" />',
    `<meta name="twitter:title" content="${esc(title)}" />`,
    `<meta name="twitter:description" content="${esc(description)}" />`,
    `<meta name="twitter:image" content="${esc(image)}" />`,
    // « < » est échappé : rien dans le JSON ne peut fermer la balise.
    `<script type="application/ld+json">${JSON.stringify(person).replace(/</g, '\\u003c')}</script>`,
  ].join('\n    ');
}

// L'adresse publique du site : fixée par PUBLIC_URL, sinon le domaine Railway, sinon l'hôte demandé.
const HOST = /^[a-z0-9.-]+(:\d{1,5})?$/i;
function originOf(req) {
  if (process.env.PUBLIC_URL) return process.env.PUBLIC_URL.replace(/\/+$/, '');
  if (process.env.RAILWAY_PUBLIC_DOMAIN) return `https://${process.env.RAILWAY_PUBLIC_DOMAIN}`;
  const host = req.get('host') || '';
  return HOST.test(host) ? `${req.protocol}://${host}` : 'https://golfolio-production.up.railway.app';
}

// ---- compression (gzip ou brotli) des réponses texte, gardée en mémoire
const packed = new Map();
function send(req, res, key, type, make) {
  const accepts = String(req.headers['accept-encoding'] || '');
  const enc = /\bbr\b/.test(accepts) ? 'br' : /\bgzip\b/.test(accepts) ? 'gzip' : '';
  const id = `${enc}:${key}`;
  let body = packed.get(id);
  if (!body) {
    const raw = Buffer.from(make());
    body = enc === 'br' ? brotliCompressSync(raw, { params: { [constants.BROTLI_PARAM_QUALITY]: 9 } }) : enc === 'gzip' ? gzipSync(raw) : raw;
    if (packed.size < 400) packed.set(id, body);
  }
  res.setHeader('Content-Type', type);
  res.setHeader('Vary', 'Accept-Encoding');
  if (enc) res.setHeader('Content-Encoding', enc);
  res.end(body);
}

// ---- la page
const template = existsSync(join(dist, 'index.html')) ? readFileSync(join(dist, 'index.html'), 'utf8') : null;
function pageHtml(origin) {
  return template
    .replace(/<title>[\s\S]*?<\/title>\s*/, '')
    .replace(/<meta name="description"[^>]*>\s*/, '')
    .replace('</head>', `  ${headHtml(origin)}\n  </head>`)
    .replace('<div id="root"></div>', `<div id="root">${staticHtml}</div>`);
}
function page(req, res) {
  if (!template) return res.status(503).type('text/plain').send('Site non construit : lancer « npm run build ».');
  const origin = originOf(req);
  res.setHeader('Cache-Control', 'no-cache');
  return send(req, res, `page:${origin}`, 'text/html; charset=utf-8', () => pageHtml(origin));
}

// ---- le film : le manifeste (jamais gardé en cache) porte le numéro de version, les images sont gardées un an
app.get('/frames/manifest.json', (req, res) => {
  const file = join(dist, 'frames/manifest.json');
  if (!existsSync(file)) return res.status(404).json({ error: 'no film' });
  res.setHeader('Cache-Control', 'no-cache');
  return send(req, res, 'manifest', 'application/json; charset=utf-8', () => JSON.stringify({ ...JSON.parse(readFileSync(file, 'utf8')), v: VERSION }));
});
app.use(
  '/frames',
  express.static(join(dist, 'frames'), {
    index: false,
    fallthrough: false,
    // L'affiche n'a pas de numéro de version dans son adresse : cache court.
    setHeaders: (res, file) => res.setHeader('Cache-Control', file.endsWith('poster.webp') ? 'public, max-age=3600' : 'public, max-age=31536000, immutable'),
  }),
);

// ---- le reste de la version construite
const TEXT = { '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8' };
app.get(/^\/assets\/([A-Za-z0-9._-]+\.(?:js|css))$/, (req, res, next) => {
  const name = req.params[0];
  const file = join(dist, 'assets', name);
  if (!existsSync(file)) return next();
  res.setHeader('Cache-Control', 'public, max-age=31536000, immutable');
  return send(req, res, `asset:${name}`, TEXT[name.slice(name.lastIndexOf('.'))], () => readFileSync(file));
});
app.use('/assets', express.static(join(dist, 'assets'), { immutable: true, maxAge: '1y', index: false, fallthrough: false }));
app.use('/fonts', express.static(join(dist, 'fonts'), { immutable: true, maxAge: '1y', index: false, fallthrough: false }));
app.use(express.static(dist, { index: false, maxAge: '1h' }));
// Une seule page : tout autre chemin est une erreur 404.
app.get(['/', '/index.html'], page);
app.use((_req, res) => res.status(404).type('text/plain').send('Not found'));

// Un fichier absent sous /frames, /assets ou /fonts : 404 sans détail.
app.use((err, _req, res, _next) => {
  res.status(err.status === 404 ? 404 : 500).type('text/plain').send(err.status === 404 ? 'Not found' : 'Server error');
});

const server = app.listen(PORT, () => console.log(`[golfolio] en écoute sur :${PORT} (film ${VERSION})`));
process.on('SIGTERM', () => server.close(() => process.exit(0)));
