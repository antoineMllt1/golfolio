# Télécharge les fichiers Poly Haven (CC0) utilisés par les scènes dans render/assets (non versionné).
#   python3 render/fetch_assets.py [nom[@8k] ...]      sans argument : tous les ciels de SKIES
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'assets')
UA = {'User-Agent': 'render-client'}
# Les deux ciels du film : une matinée pour le trou 1, une fin d'après-midi au bord d'un lac pour le trou 2.
SKIES = {
    'spruit_sunrise': '4k',  # trou 1 : aube, brume, arbres à contre-jour
    'lakeside_sunrise': '4k',  # trou 2 : soleil bas et doré, lac, falaise ocre
}
# Essayés puis écartés (render/scene.py connaît la place de leur soleil, pour --sky) : meadow_2,
# ehingen_hillside, je_gray_park, spaichingen_hill, rooitou_park, park_bench, lilienstein,
# small_harbour_sunset, golf_course_sunrise.


def get(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA)) as r, open(path, 'wb') as fh:
        fh.write(r.read())
    print('  ', os.path.relpath(path, OUT), os.path.getsize(path) // 1024, 'ko')


def files(asset):
    return json.load(urllib.request.urlopen(urllib.request.Request(f'https://api.polyhaven.com/files/{asset}', headers=UA)))


for arg in sys.argv[1:] or SKIES:
    # « nom » ou « nom@8k » : la résolution par défaut est celle de SKIES, sinon 4k.
    name, _, res = arg.partition('@')
    res = res or SKIES.get(name, '4k')
    print(name, res)
    suffix = '' if res == SKIES.get(name, '4k') else f'_{res}'
    get(files(name)['hdri'][res]['hdr']['url'], os.path.join(OUT, f'{name}{suffix}.hdr'))
