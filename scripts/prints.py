# Les impressions de la scène (textures) : pour l'instant, le tampon de la balle.
#   python3 scripts/prints.py        → render/prints/*.png
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'render', 'prints')
FONT = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
os.makedirs(OUT, exist_ok=True)


def ball_stamp():
    s = 1024
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ink = (22, 24, 28, 255)
    amber = (226, 140, 30, 255)
    big = ImageFont.truetype(FONT, 250)
    small = ImageFont.truetype(FONT, 150)
    d.text((s / 2, s * 0.42), 'AM', font=big, fill=ink, anchor='mm')
    d.rectangle((s * 0.30, s * 0.565, s * 0.70, s * 0.577), fill=ink)
    d.text((s / 2, s * 0.69), '3', font=small, fill=amber, anchor='mm')
    im.save(os.path.join(OUT, 'ball_stamp.png'))


ball_stamp()
print(sorted(os.listdir(OUT)))
