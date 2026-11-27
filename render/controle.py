# Planche de contrôle d'un trajet : ses images en grille, numérotées, pour juger la frappe, la continuité
# de la balle et l'arrivée sur l'arrêt.
#   python3 render/controle.py --leg 0                  # une image sur quatre → render/out/anim/planche_l0.jpg
#   python3 render/controle.py --leg 0 --frames 7-14    # ces images-là, toutes → planche_l0_7-14.jpg
#   python3 render/controle.py --leg 0 --stop render/out/s50/h_01.png   # ajoute l'image de l'arrêt en dernière case
# Le petit trait en haut de chaque case marque x = 0,62, où la balle doit se tenir.
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = ('/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Medium.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--leg', type=int, required=True)
    ap.add_argument('--src', default=os.path.join(HERE, 'out', 'anim'))
    ap.add_argument('--frames', default='', help='« 7-14 » : ces images, toutes ; sinon une sur quatre et la dernière')
    ap.add_argument('--stop', default='', help="image de l'arrêt d'arrivée, à comparer à la dernière")
    ap.add_argument('--cols', type=int, default=4)
    args = ap.parse_args()
    if args.frames:
        a, _, b = args.frames.partition('-')
        frames = list(range(int(a), int(b or a) + 1))
    else:
        frames = list(range(1, 45, 4)) + [44]
    font = next((ImageFont.truetype(f, 13) for f in FONTS if os.path.isfile(f)), ImageFont.load_default())
    cw = 1600 // args.cols
    ch = round(cw * 9 / 16)
    tiles = []
    for n in frames:
        path = os.path.join(args.src, f'l{args.leg}_{n:04d}.png')
        if os.path.isfile(path):
            tiles.append((f'{n}', Image.open(path).convert('RGB')))
    if args.stop and os.path.isfile(args.stop):
        tiles.append(('arrêt', Image.open(args.stop).convert('RGB')))
    rows = (len(tiles) + args.cols - 1) // args.cols
    sheet = Image.new('RGB', (cw * args.cols, ch * rows), (10, 20, 16))
    for k, (name, im) in enumerate(tiles):
        t = im.resize((cw, ch), Image.LANCZOS)
        d = ImageDraw.Draw(t)
        d.rectangle((0, 0, 14 + 8 * len(name), 20), fill=(10, 20, 16))
        d.text((6, 3), name, font=font, fill=(242, 239, 232))
        d.line((round(cw * 0.62), 0, round(cw * 0.62), 6), fill=(242, 169, 59), width=2)
        sheet.paste(t, ((k % args.cols) * cw, (k // args.cols) * ch))
    out = os.path.join(args.src, f'planche_l{args.leg}' + (f'_{args.frames}' if args.frames else '') + '.jpg')
    sheet.save(out, quality=88)
    print(out, sheet.size)


if __name__ == '__main__':
    main()
