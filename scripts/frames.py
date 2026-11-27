# Le vrai film : convertit les PNG de render/out en WebP dans public/frames/{s,m,l}, écrit
# manifest.json ("placeholder": false) et poster.webp, au format de PLAN.md (section 4).
#   python3 scripts/frames.py                       # arrêts de render/out/s200, trajets de render/out/s100
#   python3 scripts/frames.py --check               # dit ce qui serait écrit, sans rien écrire
#   python3 scripts/frames.py --draft               # le brouillon animé : arrêts de render/out/s50 (960 px),
#                                                   # trajets de render/out/anim (480 px)
#
# Sources (écrites par render/scene.py) :
#   <holds>/h_00.png … h_06.png        images nettes des arrêts, 3840 × 2160 (--stop N --scale 200)
#   <legs>/l<k>_<nnnn>.png             images des trajets, 1920 × 1080 (--leg N --scale 100), n de 1 à 44
#   render/out/anchors.json            où tombe la balle à chaque arrêt ("focus") et, sous "legs", le calage
#                                      de chaque trajet : {"0": {"impact": 10, "land": 35}} (image de
#                                      l'impact, image où la balle touche le sol), écrits par scene.py
#   render/out/legs.json (facultatif)  un calage posé à la main, qui l'emporte sur celui d'anchors.json
#
# Règles :
#   - les sept arrêts doivent être là, à la bonne taille : sinon rien n'est écrit (le site en ligne se
#     redéploie à chaque poussée, un film à moitié converti s'y verrait). --draft lève l'exigence de
#     taille, pour le brouillon animé : les trois tailles s, m, l portent alors les mêmes images, et le
#     manifeste dit leurs largeurs réelles ("sizes"), sur lesquelles la page choisit ;
#   - un trajet incomplet n'entre pas dans le manifeste : la page fait alors un fondu entre ses deux
#     arrêts. On peut donc convertir et pousser lot après lot ;
#   - une image n'est jamais agrandie ; une image déjà convertie et plus récente que sa source est gardée ;
#   - les fichiers d'un film précédent (le film factice) qui ne font pas partie de celui-ci sont retirés.
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor

from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
OUT = os.path.join(ROOT, 'render', 'out')
IDS = ['depart', 'spendmap', 'fnac-darty', 'payfit', 'revenue-engine', 'estimia', 'contact']
WIDTH, HEIGHT, FPS = 1920, 1080, 27
LEG_FRAMES = 44
# Largeur des images de trajet et des images d'arrêt, par taille (PLAN.md, section 4).
SIZES = {'l': {'motion': 1920, 'hold': 3840}, 'm': {'motion': 1920, 'hold': 2560}, 's': {'motion': 1280, 'hold': 1600}}
QUALITY = {'hold': 86, 'motion': 74}
POSTER_MAX = 30_000  # octets


def convert(job):
    """Un PNG → un WebP de la largeur voulue (jamais plus large que la source). Renvoie la largeur écrite."""
    src, dst, width, quality = job
    if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
        with Image.open(dst) as im:
            return im.width
    with Image.open(src) as im:
        im = im.convert('RGB')
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        tmp = dst + '.tmp'
        im.save(tmp, 'WEBP', quality=quality, method=6)
        os.replace(tmp, dst)
        return im.width


def poster(src, dst):
    """La première image en très petit, sous 30 Ko : on baisse la qualité jusqu'à y arriver."""
    with Image.open(src) as im:
        im = im.convert('RGB').resize((480, 270), Image.LANCZOS)
    for quality in (62, 55, 48, 40, 32, 24):
        im.save(dst, 'WEBP', quality=quality, method=6)
        if os.path.getsize(dst) <= POSTER_MAX:
            break
    return os.path.getsize(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--holds', default='', help='dossier des images d\'arrêt (h_00.png …) : render/out/s200, ou s50 avec --draft')
    ap.add_argument('--legs', default='', help='dossier des images de trajet (l0_0001.png …) : render/out/s100, ou anim avec --draft')
    ap.add_argument('--dst', default=os.path.join(ROOT, 'public', 'frames'))
    ap.add_argument('--anchors', default=os.path.join(OUT, 'anchors.json'))
    ap.add_argument('--draft', action='store_true', help='le brouillon animé : accepte des images plus petites que prévu')
    ap.add_argument('--check', action='store_true', help='n\'écrit rien : dit seulement ce qui serait fait')
    ap.add_argument('--jobs', type=int, default=os.cpu_count() or 2)
    args = ap.parse_args()
    args.holds = args.holds or os.path.join(OUT, 's50' if args.draft else 's200')
    args.legs = args.legs or os.path.join(OUT, 'anim' if args.draft else 's100')

    # Les arrêts : tous, et à la bonne taille.
    with open(args.anchors, encoding='utf8') as fh:
        anchors = json.load(fh)
    problems, holds = [], []
    for k, stop_id in enumerate(IDS):
        src = os.path.join(args.holds, f'h_{k:02d}.png')
        anchor = anchors.get(str(k))
        if not os.path.isfile(src):
            problems.append(f'arrêt {k} : {src} manque')
            continue
        if not anchor or anchor.get('id') != stop_id:
            problems.append(f'arrêt {k} : pas de "focus" pour {stop_id} dans {args.anchors}')
            continue
        with Image.open(src) as im:
            w, h = im.size
        if abs(w * HEIGHT - h * WIDTH) > 2 * WIDTH:
            problems.append(f'arrêt {k} : {w} × {h} n\'est pas en 16:9')
        elif w < SIZES['l']['hold'] and not args.draft:
            problems.append(f'arrêt {k} : {w} px de large, il en faut {SIZES["l"]["hold"]} (--stop {k} --scale 200)')
        holds.append((k, src, w, anchor['focus']))
    if problems:
        print('Rien n\'est écrit :')
        for p in problems:
            print('  -', p)
        return 1

    # Les trajets : seulement ceux dont les 44 images sont là.
    cues = dict(anchors.get('legs') or {})
    cue_path = os.path.join(os.path.dirname(args.anchors), 'legs.json')
    if os.path.isfile(cue_path):
        with open(cue_path, encoding='utf8') as fh:
            cues.update(json.load(fh))
    legs, motion_width = [], None
    for k in range(len(IDS) - 1):
        files = [os.path.join(args.legs, f'l{k}_{n:04d}.png') for n in range(1, LEG_FRAMES + 1)]
        have = [f for f in files if os.path.isfile(f)]
        if len(have) < LEG_FRAMES:
            print(f'trajet {k} → {k + 1} : {len(have)} image(s) sur {LEG_FRAMES}, la page fera un fondu')
            continue
        with Image.open(files[0]) as im:
            w = im.width
        if w < SIZES['l']['motion'] and not args.draft:
            print(f'trajet {k} → {k + 1} : {w} px de large, il en faut {SIZES["l"]["motion"]} : laissé de côté')
            continue
        motion_width = min(motion_width or w, w)
        entry = {'from': k, 'to': k + 1, 'frames': LEG_FRAMES}
        cue = cues.get(str(k))
        if cue and 1 <= cue.get('impact', 0) < cue.get('land', 0) <= LEG_FRAMES:
            entry.update(impact=cue['impact'], land=cue['land'])
        legs.append((entry, files))

    hold_width = min(w for _, _, w, _ in holds)
    sizes = {name: {'motion': min(s['motion'], motion_width or s['motion']), 'hold': min(s['hold'], hold_width)} for name, s in SIZES.items()}
    jobs, keep = [], set()
    for name in SIZES:
        for k, src, _, _ in holds:
            dst = os.path.join(args.dst, name, f'h_{k:02d}.webp')
            jobs.append((src, dst, sizes[name]['hold'], QUALITY['hold']))
            keep.add(dst)
        for entry, files in legs:
            for n, src in enumerate(files, 1):
                dst = os.path.join(args.dst, name, f'l{entry["from"]}_{n:04d}.webp')
                jobs.append((src, dst, sizes[name]['motion'], QUALITY['motion']))
                keep.add(dst)
    manifest = {
        'placeholder': False,
        'width': WIDTH, 'height': HEIGHT, 'fps': FPS,
        'sizes': sizes,
        'stops': [{'id': IDS[k], 'focus': [round(float(f[0]), 4), round(float(f[1]), 4)]} for k, _, _, f in holds],
        'legs': [entry for entry, _ in legs],
    }
    print(f'{len(holds)} arrêts, {len(legs)} trajet(s) complet(s), {len(jobs)} fichiers vers {args.dst}')
    if args.check:
        print(json.dumps(manifest, ensure_ascii=False))
        return 0

    with ProcessPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        list(pool.map(convert, jobs, chunksize=4))
    # Ce qui reste d'un film précédent (le film factice, un trajet refait) n'a plus sa place.
    removed = 0
    for name in SIZES:
        folder = os.path.join(args.dst, name)
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if f.endswith('.webp') and path not in keep:
                os.remove(path)
                removed += 1
    weight = poster(holds[0][1], os.path.join(args.dst, 'poster.webp'))
    with open(os.path.join(args.dst, 'manifest.json'), 'w', encoding='utf8') as fh:
        json.dump(manifest, fh, separators=(',', ':'))
    for name in SIZES:
        folder = os.path.join(args.dst, name)
        total = sum(os.path.getsize(os.path.join(folder, f)) for f in os.listdir(folder))
        print(f'  {name} : arrêts en {sizes[name]["hold"]} px, trajets en {sizes[name]["motion"]} px, {total / 1e6:.1f} Mo')
    print(f'  affiche {weight / 1e3:.1f} Ko, {removed} ancien(s) fichier(s) retiré(s), manifest.json écrit')
    return 0


if __name__ == '__main__':
    sys.exit(main())
