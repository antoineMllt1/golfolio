# Retouche du ciel du trou 2 : efface les deux arbres morts plantés dans l'eau de part et d'autre du
# soleil de lakeside_sunrise, que la caméra croise en descendant sur le départ du 2 et en se tournant
# vers la cible. À lancer une fois, après render/fetch_assets.py :
#   python render/retouche_ciel.py        # render/assets/lakeside_sunrise.hdr → render/assets/lakeside_soir.hdr
# Un arbre mort est fait de traits fins et sombres devant un fond lisse (ciel, colline, eau) : dans
# chaque ligne de la zone, tout pixel nettement plus sombre que la médiane de ses voisins de gauche et
# de droite est remplacé par cette médiane (dans l'eau : par l'eau voisine). Le reste de l'image n'est
# pas touché.
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'assets', 'lakeside_sunrise.hdr')
OUT = os.path.join(HERE, 'assets', 'lakeside_soir.hdr')
# Zones, en pixels du panorama de 4096 × 2048 (ligne 0 en haut) : colonnes, lignes, largeur de la médiane.
ZONES = [
    ((2325, 2455), (890, 1430), 91),  # le tronc seul, à gauche du soleil
    ((2475, 2795), (800, 1430), 181),  # l'arbre branchu, à sa droite
]
SHIFT = 40  # voir clean
HORIZON = 1030  # au-dessus : ciel et colline, où le moindre trait sombre s'efface ; au-dessous : l'eau, dont les vagues restent


def clean(a, cols, rows, width):
    (x0, x1), (y0, y1), half = cols, rows, width // 2
    block = a[y0:y1, x0 - half : x1 + half]
    lum = block.mean(axis=2)
    win = np.lib.stride_tricks.sliding_window_view(lum, width, axis=1)  # (lignes, colonnes, largeur)
    med = np.median(win, axis=2)
    here = lum[:, half:-half]
    limit = np.where(np.arange(y0, y1)[:, None] < HORIZON, 0.955, 0.86)
    mask = here < limit * med
    # Le masque déborde d'un pixel ou deux : le bord d'un trait est à moitié sombre.
    grown = mask.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (0, 2), (0, -2)):
        grown |= np.roll(mask, (dy, dx), axis=(0, 1))
    fill = np.stack([np.median(np.lib.stride_tricks.sliding_window_view(block[:, :, c], width, axis=1), axis=2) for c in range(3)], axis=2)
    # Dans l'eau, une médiane lisserait les vagues en bandes : on y recopie plutôt l'eau voisine, prise
    # SHIFT colonnes à gauche, là où elle n'est pas elle-même à retoucher.
    water = (np.arange(y0, y1) >= HORIZON)[:, None]
    near = a[y0:y1, x0 - SHIFT : x1 - SHIFT]
    free = np.ones_like(grown)
    free[:, SHIFT:] = ~grown[:, :-SHIFT]
    free &= near.mean(axis=2) < 1.2 * med  # pas le reflet du soleil : il se dédoublerait
    fill = np.where((water & free)[:, :, None], near, fill)
    # Fondu vers l'image d'origine au bord de la zone.
    edge = np.minimum(np.arange(x1 - x0), np.arange(x1 - x0)[::-1])[None, :, None] / 12.0
    part = grown[:, :, None] * np.clip(edge, 0.0, 1.0)
    a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - part) + fill * part
    return int(grown.sum())


def save(a):
    """Écrit l'image (H, W, 3) au format Radiance, sans compression. (Blender, en enregistrant un
    tampon flottant en .hdr, écrête les hautes lumières : le soleil y perdrait mille fois sa force.)"""
    top = a.max(axis=2)
    mantissa, exponent = np.frexp(top)  # top = mantissa · 2^exponent, mantissa de 0,5 à 1
    scale = np.where(top > 1e-32, 256.0 / np.exp2(exponent.astype(np.float64)), 0.0)
    rgbe = np.zeros(a.shape[:2] + (4,), dtype=np.uint8)
    rgbe[:, :, :3] = np.clip(a * scale[:, :, None], 0, 255).astype(np.uint8)
    rgbe[:, :, 3] = np.where(top > 1e-32, exponent + 128, 0).astype(np.uint8)
    with open(OUT, 'wb') as fh:
        fh.write(b'#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n' + f'-Y {a.shape[0]} +X {a.shape[1]}\n'.encode())
        fh.write(rgbe.tobytes())


def main():
    img = bpy.data.images.load(SRC)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)[::-1].copy()  # ligne 0 en haut
    k = w / 4096.0
    for cols, rows, width in ZONES:
        n = clean(a[:, :, :3], tuple(round(c * k) for c in cols), tuple(round(r * k) for r in rows), int(width * k) | 1)
        print(f'zone {cols} : {n} pixels retouchés')
    save(a[:, :, :3])
    print(OUT, os.path.getsize(OUT) // 1024, 'ko')


if __name__ == '__main__':
    main()
