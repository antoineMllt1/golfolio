# Film factice, pour tester le site sans attendre le rendu : public/frames/{s,m,l}/*.webp,
# manifest.json et poster.webp, au format de PLAN.md (section 4).
#   python3 scripts/placeholder_frames.py
# 7 images d'arrêt (h_00 … h_06) et 6 trajets de 44 images (l<k>_<nnnn>), chacune étiquetée : arrêt ou
# trajet, numéro d'image. Le fond est un dégradé qui change d'un arrêt à l'autre (aube, matin, heure
# dorée), la « balle » est un disque clair posé à x = 0,62 à l'arrêt et qui se déplace pendant les trajets.
# Les trois tailles reçoivent les mêmes petites images (960 × 540) : le vrai film les remplacera.
#
# Le script ne touche à rien si public/frames/manifest.json n'est pas celui d'un film factice
# ("placeholder": true) : un vrai film ne peut pas être écrasé par erreur.
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
DST = os.path.join(ROOT, 'public', 'frames')
W, H = 960, 540
SS = 2  # suréchantillonnage : tout est dessiné deux fois plus grand, puis réduit
FPS = 27
LEG_FRAMES = 44
SIZES = ('s', 'm', 'l')
FOCUS_X = 0.62
FONTS = (
    '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf',
    '/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
    '/System/Library/Fonts/Menlo.ttc',
    'C:/Windows/Fonts/consola.ttf',
)


def rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float32) / 255


# Un arrêt = une lumière. ciel haut, ciel à l'horizon, arbres flous, herbe au loin, herbe au premier plan.
STOPS = [
    dict(id='depart', focus=[0.62, 0.56], sky=('#27384a', '#e7a56e'), trees='#3a2a22', grass=('#56602c', '#1d3018'), sun=(0.80, 0.36, '#ffd9a0', 0.55), club=True),
    dict(id='spendmap', focus=[0.62, 0.56], sky=('#58809f', '#dfe6dc'), trees='#2c4a33', grass=('#5e8a3c', '#234a22'), sun=(0.88, 0.20, '#fff4d8', 0.30), club=True),
    dict(id='fnac-darty', focus=[0.62, 0.56], sky=('#6394b8', '#e6ecdf'), trees='#31553a', grass=('#6a9744', '#2a5526'), sun=(0.90, 0.16, '#fff6e0', 0.26), club=True),
    dict(id='payfit', focus=[0.62, 0.56], sky=('#78aacd', '#f0f3e6'), trees='#3a6240', grass=('#78a750', '#33642b'), sun=(0.86, 0.12, '#fffbe8', 0.24), club=True),
    dict(id='revenue-engine', focus=[0.62, 0.56], sky=('#3f6e93', '#efd6a2'), trees='#2d4030', grass=('#5c7a34', '#22401f'), sun=(0.30, 0.30, '#ffe2a8', 0.42), water='#4f7f95', club=True),
    dict(id='estimia', focus=[0.62, 0.56], sky=('#b8743a', '#f5cd86'), trees='#3d2d1c', grass=('#7a7a2a', '#2d3a17'), sun=(0.76, 0.34, '#ffe0a0', 0.60), club=True),
    dict(id='contact', focus=[0.62, 0.52], hole=True, grass=('#6f7d2c', '#2c3b18'), sun=(0.84, 0.18, '#ffdc98', 0.40)),
]
# Un trajet = une façon de bouger : vol (la balle monte, traverse le ciel, redescend), roule (elle saute
# puis roule, sans coupe), trou (elle tombe, noir, on redescend du ciel), putt (elle roule jusqu'au trou).
LEGS = ['vol', 'vol', 'roule', 'trou', 'vol', 'putt']

yy, xx = np.mgrid[0:H * SS, 0:W * SS].astype(np.float32)
U = xx / (W * SS)  # 0 à gauche, 1 à droite
V = yy / (H * SS)  # 0 en haut, 1 en bas
HORIZON = 0.44


def smooth(t, a=0.0, b=1.0):
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def glow(img, x, y, colour, strength, radius=0.42):
    d = np.sqrt(((U - x) * W / H) ** 2 + (V - y) ** 2)
    k = np.exp(-(d / radius) ** 2 * 3)[..., None] * strength
    return img + (rgb(colour) - img) * k


def backdrop(stop):
    """Le décor flou d'un arrêt, sans la balle : tableau (H·SS, W·SS, 3) entre 0 et 1."""
    near, far = rgb(stop['grass'][1]), rgb(stop['grass'][0])
    if stop.get('hole'):
        # Vue à l'aplomb du trou : du gazon, plus sombre vers les bords.
        d = np.sqrt(((U - stop['focus'][0]) * W / H) ** 2 + (V - stop['focus'][1]) ** 2)
        img = lerp(far, near, smooth(d, 0.1, 1.0)[..., None])
    else:
        top, low = rgb(stop['sky'][0]), rgb(stop['sky'][1])
        sky = lerp(top, low, (np.clip(V / HORIZON, 0, 1) ** 1.25)[..., None])
        ground = lerp(far, near, (np.clip((V - HORIZON) / (1 - HORIZON), 0, 1) ** 0.75)[..., None])
        img = np.where((V < HORIZON)[..., None], sky, ground)
        # Rideau d'arbres hors mise au point, juste au-dessus de l'horizon.
        band = np.exp(-((V - (HORIZON - 0.05)) / 0.055) ** 2) * (0.72 + 0.2 * np.sin(U * 9.0 + 1.3) * np.sin(U * 23.0))
        img = img + (rgb(stop['trees']) - img) * np.clip(band, 0, 1)[..., None]
        if stop.get('water'):
            w = np.exp(-((V - (HORIZON + 0.085)) / 0.06) ** 2)
            img = img + (rgb(stop['water']) - img) * (w * 0.92)[..., None]
        # L'horizon n'est jamais une ligne nette : tout le fond est flou.
        haze = np.exp(-((V - HORIZON) / 0.035) ** 2) * 0.35
        img = img + (lerp(low, far, 0.5) - img) * haze[..., None]
    sx, sy, colour, strength = stop['sun']
    img = glow(img, sx, sy, colour, strength)
    # La gauche et les coins restent calmes et sombres, comme dans le vrai film.
    shade = 1 - 0.34 * smooth(1 - U, 0.25, 1.0) - 0.22 * smooth(np.abs(V - 0.5) * 2, 0.55, 1.0)
    return np.clip(img * shade[..., None], 0, 1)


def sky_only(a, b):
    """Plein ciel entre deux arrêts : la caméra suit la balle en l'air."""
    def one(stop):
        if stop.get('hole'):
            return None
        return rgb(stop['sky'][0]), rgb(stop['sky'][1])
    pa, pb = one(a), one(b)
    pa, pb = pa or pb, pb or pa
    top, low = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
    img = lerp(top, lerp(top, low, 0.75), (V ** 1.1)[..., None])
    img = glow(img, 0.7, 0.75, '#fff3d6', 0.35, 0.6)
    return np.clip(img, 0, 1)


def to_image(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def draw_club(im, x, y, r):
    """Tête de club posée derrière la balle (à gauche) et son manche : deux formes sombres."""
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    hx, hy = x - r * 1.95, y + r * 0.42
    d.ellipse((hx - r * 2.1, hy - r * 0.62, hx + r * 2.1, hy + r * 0.62), fill=(14, 17, 20, 255))
    d.line((x + r * 0.75, y + r * 0.3, x + r * 4.6, y - r * 6.4), fill=(12, 14, 17, 255), width=max(2, int(r * 0.2)))
    for i in range(5):
        yy_ = hy - r * 0.34 + i * r * 0.17
        d.line((hx + r * 0.9, yy_, hx + r * 1.9, yy_), fill=(225, 225, 220, 235), width=max(1, int(r * 0.045)))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(SS * 0.8)))


def draw_ball(im, x, y, r, streak=(0.0, 0.0), alpha=1.0, shadow=True):
    """La balle : disque clair ombré, avec une traînée si elle va vite (flou de mouvement)."""
    if r < 0.6 or alpha <= 0.01:
        return
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if shadow:
        d.ellipse((x - r * 1.25, y + r * 0.78, x + r * 1.25, y + r * 1.16), fill=(8, 14, 8, int(120 * alpha)))
        layer = layer.filter(ImageFilter.GaussianBlur(max(1, r * 0.16)))
        d = ImageDraw.Draw(layer)
    length = math.hypot(*streak)
    steps = int(min(14, max(1, length / max(1.0, r * 0.35))))
    for i in range(steps):
        k = i / max(1, steps - 1) if steps > 1 else 1.0
        cx, cy = x - streak[0] * (1 - k), y - streak[1] * (1 - k)
        a = int(255 * alpha * (1.0 if steps == 1 else 0.16 + 0.5 * k * k))
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(236, 233, 224, a))
    if steps == 1:
        # Un peu de volume : ombre en bas à gauche, reflet en haut à droite.
        d.ellipse((x - r, y - r, x + r, y + r), fill=(203, 199, 188, int(255 * alpha)))
        d.ellipse((x - r * 0.84, y - r * 0.96, x + r * 0.98, y + r * 0.8), fill=(240, 237, 229, int(255 * alpha)))
        d.ellipse((x - r * 0.2, y - r * 0.78, x + r * 0.7, y + r * 0.06), fill=(252, 250, 244, int(255 * alpha)))
        layer = layer.filter(ImageFilter.GaussianBlur(max(0.6, r * 0.09)))
    im.alpha_composite(layer)


def draw_hole(im, x, y, r, alpha=1.0):
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse((x - r * 1.06, y - r * 1.06, x + r * 1.06, y + r * 1.06), fill=(238, 226, 190, int(150 * alpha)))
    d.ellipse((x - r, y - r, x + r, y + r), fill=(9, 13, 9, int(255 * alpha)))
    im.alpha_composite(layer.filter(ImageFilter.GaussianBlur(SS * 1.2)))


def font(size):
    for path in FONTS:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def label(im, lines):
    """Étiquette lisible sous la balle : visible aussi une fois l'image recadrée pour un téléphone."""
    d = ImageDraw.Draw(im)
    small, big = font(10), font(15)
    cx, y = FOCUS_X * W, 0.70 * H
    rows = [(lines[0], small, (242, 239, 232, 200))] + [(t, big, (242, 239, 232, 255)) for t in lines[1:]]
    widths = [d.textlength(t, font=f) for t, f, _ in rows]
    heights = [15] + [20] * (len(rows) - 1)
    bw, bh = max(widths) + 24, sum(heights) + 14
    d.rounded_rectangle((cx - bw / 2, y, cx + bw / 2, y + bh), radius=5, fill=(10, 20, 16, 150))
    ty = y + 7
    for (t, f, fill), h, w in zip(rows, heights, widths):
        d.text((cx - w / 2, ty), t, font=f, fill=fill)
        ty += h


def finish(base, name, lines):
    """Réduit à 960 × 540, étiquette et écrit la même image dans les trois tailles."""
    im = base.convert('RGB').resize((W, H), Image.LANCZOS).convert('RGBA')
    label(im, lines)
    out = im.convert('RGB')
    for size in SIZES:
        out.save(os.path.join(DST, size, name + '.webp'), 'WEBP', quality=72, method=4)
    return out


def ball_radius(stop):
    return 0.082 * H * SS if not stop.get('hole') else 0.06 * H * SS


def hold(k, stop, bg):
    im = to_image(bg).convert('RGBA')
    x, y = stop['focus'][0] * W * SS, stop['focus'][1] * H * SS
    r = ball_radius(stop)
    if stop.get('hole'):
        draw_hole(im, x, y, r * 2.3)
        draw_ball(im, x, y, r, shadow=False)
    else:
        if stop.get('club'):
            draw_club(im, x, y, r)
        draw_ball(im, x, y, r)
    return finish(im, f'h_{k:02d}', ['FILM FACTICE', f'ARRÊT {k} · {stop["id"]}'])


def leg_state(kind, t, a, b):
    """Où est la balle à l'instant t (0 → 1) : fond (mélanges), position, rayon, opacité."""
    ax, ay = a['focus']
    bx, by = b['focus']
    ra, rb = ball_radius(a), ball_radius(b)
    s = dict(to_sky=0.0, to_b=0.0, black=0.0, x=ax, y=ay, r=ra, alpha=1.0, shadow=True, hole=0.0)
    if kind == 'vol':
        up = smooth(t, 0.10, 0.40)       # la balle part vers le haut de l'image
        down = smooth(t, 0.62, 0.93)     # puis redescend sur l'arrêt suivant
        s['to_sky'] = smooth(t, 0.16, 0.42) * (1 - smooth(t, 0.58, 0.84))
        s['to_b'] = smooth(t, 0.52, 0.78)
        if t < 0.5:
            s['x'] = ax + 0.10 * up
            s['y'] = ay - 0.50 * up ** 1.4
            s['r'] = lerp(ra, ra * 0.16, up)
        else:
            s['x'] = bx - 0.10 * (1 - down)
            s['y'] = by - 0.52 * (1 - down) ** 1.6 - 0.035 * math.sin(max(0.0, (t - 0.93) / 0.07) * math.pi) * (t > 0.93)
            s['r'] = lerp(ra * 0.16, rb, down)
        s['shadow'] = t < 0.14 or t > 0.9
    elif kind == 'roule':
        go = smooth(t, 0.10, 0.92)
        s['to_b'] = smooth(t, 0.22, 0.80)
        hop = math.sin(min(1.0, max(0.0, (t - 0.10) / 0.34)) * math.pi)
        s['x'] = lerp(ax, bx, go) + 0.05 * math.sin(go * math.pi)
        s['y'] = lerp(ay, by, go) - 0.16 * hop
        s['r'] = lerp(ra, rb, go)
        s['shadow'] = hop < 0.2
    elif kind == 'trou':
        roll = smooth(t, 0.06, 0.40)
        s['x'] = ax - 0.06 * roll
        s['y'] = ay + 0.10 * roll
        s['r'] = ra * (1 + 0.5 * roll)
        s['hole'] = smooth(t, 0.10, 0.34) * (1 - smooth(t, 0.44, 0.5))
        s['black'] = smooth(t, 0.38, 0.48) * (1 - smooth(t, 0.56, 0.68))
        s['to_sky'] = smooth(t, 0.50, 0.58) * (1 - smooth(t, 0.66, 0.88))
        s['to_b'] = smooth(t, 0.50, 0.88)
        if t > 0.42:
            s['x'], s['y'], s['r'] = bx, by, rb
            s['alpha'] = smooth(t, 0.74, 0.92)
        else:
            s['alpha'] = 1 - smooth(t, 0.34, 0.42)
    else:  # putt
        go = smooth(t, 0.08, 0.86)
        s['to_b'] = smooth(t, 0.30, 0.90)
        s['x'] = lerp(ax, bx, go) + 0.09 * math.sin(go * math.pi)
        s['y'] = lerp(ay, by, go)
        s['r'] = lerp(ra, rb, go)
        s['hole'] = smooth(t, 0.30, 0.90)
        s['shadow'] = t < 0.6
    return {key: (v if isinstance(v, bool) else float(v)) for key, v in s.items()}


def leg(k, kind, a, b, bga, bgb, sky):
    black = np.zeros_like(bga)
    prev = None
    for n in range(1, LEG_FRAMES + 1):
        t = (n - 1) / (LEG_FRAMES - 1)
        s = leg_state(kind, t, a, b)
        bg = lerp(bga, bgb, s['to_b'])
        bg = lerp(bg, sky, s['to_sky'])
        bg = lerp(bg, black, s['black'])
        im = to_image(bg).convert('RGBA')
        x, y = s['x'] * W * SS, s['y'] * H * SS
        if s['hole'] > 0.01:
            # Le trou : devant la balle pendant le putt du trou 1, sous elle à la fin du trou 2.
            hx, hy = (b['focus'][0] * W * SS, b['focus'][1] * H * SS) if kind == 'putt' else ((a['focus'][0] - 0.06) * W * SS, (a['focus'][1] + 0.10) * H * SS)
            draw_hole(im, hx, hy, ball_radius(b if kind == 'putt' else a) * (2.3 if kind == 'putt' else 2.0), s['hole'])
        streak = (0.0, 0.0) if prev is None else ((x - prev[0]) * 0.9, (y - prev[1]) * 0.9)
        draw_ball(im, x, y, s['r'], streak=streak, alpha=s['alpha'], shadow=s['shadow'])
        prev = (x, y)
        finish(im, f'l{k}_{n:04d}', ['FILM FACTICE', f'TRAJET {k} → {k + 1}', f'{n:02d} / {LEG_FRAMES}'])


def main():
    manifest_path = os.path.join(DST, 'manifest.json')
    if os.path.isfile(manifest_path):
        with open(manifest_path, encoding='utf8') as fh:
            current = json.load(fh)
        if current.get('placeholder') is not True:
            print('public/frames contient un vrai film ("placeholder" absent ou false) : rien n\'est écrit.')
            return 0
    for size in SIZES:
        os.makedirs(os.path.join(DST, size), exist_ok=True)
    backs = [backdrop(s) for s in STOPS]
    first = None
    for k, stop in enumerate(STOPS):
        im = hold(k, stop, backs[k])
        first = first or im
        print(f'arrêt {k} · {stop["id"]}')
    for k, kind in enumerate(LEGS):
        leg(k, kind, STOPS[k], STOPS[k + 1], backs[k], backs[k + 1], sky_only(STOPS[k], STOPS[k + 1]))
        print(f'trajet {k} → {k + 1} · {kind} · {LEG_FRAMES} images')
    first.resize((480, 270), Image.LANCZOS).save(os.path.join(DST, 'poster.webp'), 'WEBP', quality=55, method=6)
    manifest = {
        'placeholder': True,
        'width': W, 'height': H, 'fps': FPS,
        'sizes': {size: {'motion': W, 'hold': W} for size in reversed(SIZES)},
        'stops': [{'id': s['id'], 'focus': s['focus']} for s in STOPS],
        'legs': [{'from': k, 'to': k + 1, 'frames': LEG_FRAMES} for k in range(len(LEGS))],
    }
    with open(manifest_path, 'w', encoding='utf8') as fh:
        json.dump(manifest, fh, separators=(',', ':'))
    total = sum(os.path.getsize(os.path.join(DST, SIZES[0], n)) for n in os.listdir(os.path.join(DST, SIZES[0])))
    print(f'{len(STOPS)} arrêts, {len(LEGS)} trajets : {total / 1e6:.1f} Mo par taille, affiche {os.path.getsize(os.path.join(DST, "poster.webp")) / 1e3:.1f} Ko')
    return 0


if __name__ == '__main__':
    sys.exit(main())
