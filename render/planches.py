# Les deux planches à faire valider : les sept arrêts en grille, puis recadrés comme sur un téléphone.
#   python3 render/planches.py                      # depuis render/out/s50 → render/out/planche_*.jpg
#   python3 render/planches.py --src render/out/s200
# Le recadrage du téléphone reprend celui du site (src/lib/film.js, place) : l'image couvre un écran
# de 9 × 19,5, la balle au milieu de la largeur et à 31 % de la hauteur ; le bas de l'écran, sous
# l'image, est dans la couleur du fond (la fiche du projet s'y pose).
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out')
NAMES = ['0 · départ', '1 · fairway, fer long', '2 · bord du green, wedge', '3 · green du 1, putt de 3 m', '4 · départ du 2, fer 7', '5 · green du 2, putt de 1,5 m', '6 · au fond du trou']
BACK = (10, 20, 16)  # le fond du site, #0a1410
FONTS = ('/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')


def font(size):
    for path in FONTS:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def label(im, text, size):
    d = ImageDraw.Draw(im)
    f = font(size)
    w = d.textlength(text, font=f)
    d.rectangle((0, 0, w + 2 * size, 2 * size), fill=BACK)
    d.text((size, size // 2), text, font=f, fill=(242, 239, 232))


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def phone(im, focus, w, h, ty=0.31):
    """L'image telle qu'un téléphone tenu debout la montre : mêmes formules que le site."""
    s = max(w / im.width, h / im.height)
    dw, dh = round(im.width * s), round(im.height * s)
    dx = clamp(w / 2 - focus[0] * dw, w - dw, 0)
    dy = clamp(h * ty - focus[1] * dh, -0.34 * h, 0)
    screen = Image.new('RGB', (w, h), BACK)
    screen.paste(im.resize((dw, dh), Image.LANCZOS), (round(dx), round(dy)))
    return screen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=os.path.join(OUT, 's50'), help='dossier des h_00.png … h_06.png')
    ap.add_argument('--anchors', default=os.path.join(OUT, 'anchors.json'))
    ap.add_argument('--dst', default=OUT)
    args = ap.parse_args()
    with open(args.anchors, encoding='utf8') as fh:
        anchors = json.load(fh)
    images = [Image.open(os.path.join(args.src, f'h_{k:02d}.png')).convert('RGB') for k in range(7)]

    # Planche des arrêts : deux colonnes, 1600 px de large.
    cw, gap = 796, 8
    ch = round(cw * 9 / 16)
    rows = (len(images) + 1) // 2
    sheet = Image.new('RGB', (2 * cw + gap, rows * ch + (rows - 1) * gap), BACK)
    for k, im in enumerate(images):
        tile = im.resize((cw, ch), Image.LANCZOS)
        label(tile, NAMES[k], 12)
        sheet.paste(tile, ((k % 2) * (cw + gap), (k // 2) * (ch + gap)))
    path = os.path.join(args.dst, 'planche_arrets.jpg')
    sheet.save(path, quality=90)
    print(path, sheet.size)

    # Planche du téléphone : les sept écrans côte à côte.
    pw, gap = 222, 8
    ph = round(pw * 19.5 / 9)
    sheet = Image.new('RGB', (7 * pw + 6 * gap, ph), (40, 40, 40))
    for k, im in enumerate(images):
        tile = phone(im, anchors[str(k)]['focus'], pw, ph)
        label(tile, str(k), 11)
        sheet.paste(tile, (k * (pw + gap), 0))
    path = os.path.join(args.dst, 'planche_telephone.jpg')
    sheet.save(path, quality=90)
    print(path, sheet.size)


if __name__ == '__main__':
    main()
