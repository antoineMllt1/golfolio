# Assemble les captures de render/verif/jouer.mjs en planches : une ligne par coup (vol, vol, arrivée).
#   python render/verif/planches_site.py render/out/site/animatique
import sys
from PIL import Image
src = sys.argv[1]
def sheet(name, shots, tile, cols, out):
    tiles = []
    for k in shots:
        for part in (['arret'] if k == 0 else ['vol-a', 'vol-b', 'arret']):
            tiles.append(Image.open(f'{src}/{name}-{k}-{part}.png').convert('RGB').resize(tile, Image.LANCZOS))
    rows = (len(tiles) + cols - 1) // cols
    im = Image.new('RGB', (tile[0] * cols, tile[1] * rows), (10, 20, 16))
    for i, t in enumerate(tiles):
        im.paste(t, ((i % cols) * tile[0], (i // cols) * tile[1]))
    im.save(f'{src}/{out}', quality=88)
    print(out, im.size)
sheet('ordi', [1, 2, 3], (533, 333), 3, 'planche_ordi_trou1.jpg')
sheet('ordi', [4, 5, 6], (533, 333), 3, 'planche_ordi_trou2.jpg')
sheet('tel', [0, 1, 2, 3], (160, 346), 10, 'planche_tel_trou1.jpg')
sheet('tel', [4, 5, 6], (160, 346), 9, 'planche_tel_trou2.jpg')
