# Le lot : tout le film en haute définition, image par image, reprenable.
#
#   python render/batch.py                         # les 7 arrêts (3840 × 2160) puis les 264 images de trajet (1920 × 1080)
#   python render/batch.py --dry                   # ce qui reste à faire et le temps estimé, sans rien calculer
#   python render/batch.py --order h1,l0:9,l0:17   # quelques images seulement, dans cet ordre
#   python render/batch.py --order l2,l5 --leg-samples 48 --leg-noise 0.03
#
# Chaque image est calculée par render/scene.py, lancé ici en sous-processus (un par arrêt, un par
# trajet : les plans d'un trajet gardent leurs données d'une image à l'autre). Les images vont dans
# render/out/hd : h_00.png … h_06.png, l0_0001.png … l5_0044.png, les noms qu'attend scripts/frames.py.
#
# Reprise : une image déjà là, entière (un PNG fermé, à la bonne taille), n'est pas refaite ; une image
# tronquée par un arrêt brutal est effacée et refaite. On peut donc arrêter le lot à tout moment
# (Ctrl-C, kill) et le relancer avec la même commande : au pire, l'image en cours est perdue.
# Pour refaire une image, l'effacer ; pour tout refaire à d'autres réglages, changer de dossier (--out).
#
# Journal : render/out/hd/journal.txt, une ligne par image (heure, image, durée, reste estimé). Le reste
# estimé part des durées mesurées (DUREES, plus bas) et se corrige avec celles du journal.
#
# Ordre (--order) : « h3 » un arrêt, « l2 » un trajet entier, « l2:9 » une image, « l2:9-20 » une suite.
import argparse
import os
import re
import signal
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE = os.path.join(HERE, 'scene.py')
LEG_FRAMES = 44
ORDER = 'h0,h1,h2,h3,h4,h5,h6,l0,l1,l2,l3,l4,l5'

# Durées de départ, en secondes par image, mesurées sur cette machine (4 cœurs, pas de carte
# graphique) aux réglages par défaut ci-dessous : un arrêt (construction comprise) ; une image de
# chaque trajet. Le journal les remplace dès qu'il a des mesures.
DUREES = {'h': 2400.0, 'l0': 200.0, 'l1': 200.0, 'l2': 200.0, 'l3': 200.0, 'l4': 200.0, 'l5': 200.0}

ap = argparse.ArgumentParser(description='Rend le film en haute définition, en sautant ce qui existe déjà.')
ap.add_argument('--order', default=ORDER, help='quoi rendre et dans quel ordre (voir en tête du fichier)')
ap.add_argument('--out', default=os.path.join(HERE, 'out', 'hd'), help='dossier des images et du journal')
ap.add_argument('--dry', action='store_true', help='affiche ce qui reste à faire et le temps estimé, sans rien rendre')
ap.add_argument('--python', default=sys.executable, help='le Python qui a le module bpy')
ap.add_argument('--stop-scale', type=int, default=200, help='arrêts : 200 → 3840 × 2160, 133 → 2554 × 1436')
ap.add_argument('--stop-samples', type=int, default=128)
ap.add_argument('--stop-noise', type=float, default=0.02, help="arrêts : seuil de bruit de l'échantillonnage adaptatif")
ap.add_argument('--leg-scale', type=int, default=100, help='trajets : 100 → 1920 × 1080, 67 → 1286 × 724')
ap.add_argument('--leg-samples', type=int, default=64)
ap.add_argument('--leg-noise', type=float, default=0.02, help="trajets : seuil de bruit de l'échantillonnage adaptatif")
ap.add_argument('--shutter', type=float, default=None, help='trajets : obturateur du flou de mouvement (0,5 par défaut)')
ap.add_argument('--blur-steps', type=int, default=None, help='trajets : étapes du flou de mouvement')
ap.add_argument('--density', type=float, default=1.0, help="part des brins d'herbe plantés (1 : tous)")
ap.add_argument('--set', default='', help="autres réglages d'essai passés à scene.py (« nom=valeur,… »)")
ap.add_argument('--threads', type=int, default=None, help='fils de calcul (tous les cœurs par défaut)')
args = ap.parse_args()

OUT = os.path.abspath(args.out)
JOURNAL = os.path.join(OUT, 'journal.txt')
VERROU = os.path.join(OUT, 'lot.pid')
child = None


def size_of(kind):
    """Taille attendue d'une image : celle que Blender donne à 1920 × 1080 pour cette échelle."""
    scale = args.stop_scale if kind == 'h' else args.leg_scale
    return 1920 * scale // 100, 1080 * scale // 100


def whole(path, size):
    """Vrai si le fichier est un PNG entier (en-tête, taille attendue, bloc de fin)."""
    try:
        with open(path, 'rb') as fh:
            head = fh.read(24)
            fh.seek(-12, os.SEEK_END)
            tail = fh.read(12)
    except OSError:
        return False
    return head[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', head[16:24]) == size and tail[4:8] == b'IEND'


def stop_path(n):
    return os.path.join(OUT, f'h_{n:02d}.png')


def leg_path(k, n):
    return os.path.join(OUT, f'l{k}_{n:04d}.png')


def parse(order):
    """La liste des tâches : ('h', arrêt, [arrêt]) ou ('l', trajet, [images])."""
    jobs = []
    for item in (s.strip() for s in order.split(',') if s.strip()):
        m = re.fullmatch(r'h(\d)|l(\d)(?::(\d+)(?:-(\d+))?)?', item)
        if not m or (m.group(1) and int(m.group(1)) > 6) or (m.group(2) and int(m.group(2)) > 5):
            raise SystemExit(f'--order : « {item} » ne se lit pas (h0 à h6, l0 à l5, l2:9, l2:9-20)')
        if m.group(1):
            jobs.append(('h', int(m.group(1)), [int(m.group(1))]))
        else:
            a = int(m.group(3) or 1)
            b = int(m.group(4) or (m.group(3) or LEG_FRAMES))
            jobs.append(('l', int(m.group(2)), list(range(max(a, 1), min(b, LEG_FRAMES) + 1))))
    return jobs


def missing(job):
    """Les images d'une tâche qui restent à faire ; les fichiers tronqués sont effacés au passage."""
    kind, k, frames = job
    todo = []
    for n in frames:
        path = stop_path(n) if kind == 'h' else leg_path(k, n)
        if whole(path, size_of(kind)):
            continue
        if os.path.exists(path) and not args.dry:
            os.remove(path)  # tronquée, ou d'une autre taille : scene.py ne la sauterait pas à bon escient
        todo.append(n)
    return todo


def measured():
    """Durée moyenne d'une image par famille (« h », « l0 » … « l5 »), d'après le journal."""
    sums = {}
    if os.path.exists(JOURNAL):
        with open(JOURNAL, encoding='utf8') as fh:
            for line in fh:
                m = re.search(r'\b(h)_\d\d\.png\s+(\d+) s|\b(l\d)_\d{4}\.png\s+(\d+) s', line)
                if m:
                    key, sec = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                    s = sums.setdefault(key, [0.0, 0])
                    s[0] += float(sec)
                    s[1] += 1
    return {k: s / n for k, (s, n) in sums.items()}


def remaining(jobs, done=()):
    """Secondes et images qui restent, toutes tâches confondues."""
    mean = {**DUREES, **measured()}
    seconds, images = 0.0, 0
    for kind, k, frames in jobs:
        for n in frames:
            path = stop_path(n) if kind == 'h' else leg_path(k, n)
            if path in done or whole(path, size_of(kind)):
                continue
            seconds += mean['h' if kind == 'h' else f'l{k}']
            images += 1
    return seconds, images


def clock(seconds):
    m = int(round(seconds / 60))
    return f'{m // 60} h {m % 60:02d}' if m >= 60 else f'{m} min'


def log(text):
    line = f'{time.strftime("%Y-%m-%d %H:%M:%S")}  {text}'
    print(line, flush=True)
    with open(JOURNAL, 'a', encoding='utf8') as fh:
        fh.write(line + '\n')


def command(job, todo):
    kind, k, _ = job
    cmd = [args.python, SCENE, '--', '--out', OUT]
    sets = ','.join(s for s in (f'density={args.density:g}' if args.density != 1.0 else '', args.set) if s)
    if sets:
        cmd += ['--set', sets]
    if args.threads:
        cmd += ['--threads', str(args.threads)]
    if kind == 'h':
        return cmd + ['--stop', str(k), '--scale', str(args.stop_scale), '--samples', str(args.stop_samples), '--noise', str(args.stop_noise)]
    cmd += ['--leg', str(k), '--frames', f'{todo[0]}-{todo[-1]}', '--scale', str(args.leg_scale), '--samples', str(args.leg_samples), '--noise', str(args.leg_noise)]
    if args.shutter is not None:
        cmd += ['--shutter', str(args.shutter)]
    if args.blur_steps:
        cmd += ['--blur-steps', str(args.blur_steps)]
    return cmd


def run(job, todo, jobs):
    """Lance scene.py pour une tâche et tient le journal au fil de ses images. Renvoie son code de sortie."""
    global child
    kind, k, _ = job
    started = last = time.time()
    child = subprocess.Popen(command(job, todo), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace')
    tail = []
    for line in child.stdout:
        tail = (tail + [line.rstrip()])[-12:]
        if line.startswith('PLAN '):
            last = time.time()  # la construction d'un plan n'est pas comptée dans sa première image
            log(f'  trajet {k} : {line.split(" ", 2)[2].strip()}')
        elif line.startswith('RESULT '):
            path = line.split()[1]
            now = time.time()
            took = now - (started if kind == 'h' else last)  # un arrêt : construction comprise
            last = now
            if whole(path, size_of(kind)):
                seconds, images = remaining(jobs)
                log(f'{os.path.basename(path)}  {took:.0f} s  reste {clock(seconds)} ({images} images)')
            else:
                log(f'{os.path.basename(path)}  ÉCHEC : fichier absent ou incomplet')
    code = child.wait()
    child = None
    if code:
        log(f'ÉCHEC {"arrêt" if kind == "h" else "trajet"} {k} : scene.py sort avec le code {code}')
        for line in tail:
            log('    ' + line)
    return code


def halt(signum, frame):
    """Arrêt demandé : on tue le rendu en cours (son image sera refaite) et on rend la main."""
    if child is not None:
        child.kill()
        child.wait()
    log('lot arrêté à la demande ; relancer la même commande pour reprendre')
    if os.path.exists(VERROU):
        os.remove(VERROU)
    sys.exit(130)


def locked():
    """Vrai si un autre lot tourne déjà dans ce dossier (deux rendus à la fois se partageraient les cœurs)."""
    try:
        with open(VERROU) as fh:
            os.kill(int(fh.read().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = parse(args.order)
    seconds, images = remaining(jobs)
    total = sum(len(frames) for _, _, frames in jobs)
    print(f'{images} images à faire sur {total}, environ {clock(seconds)} ; sortie : {OUT}')
    if args.dry:
        for job in jobs:
            todo = missing(job)
            if todo:
                kind, k, _ = job
                print(('  arrêt ' if kind == 'h' else '  trajet ') + f'{k} : ' + ((f'{len(todo)} images ({todo[0]} à {todo[-1]})' if len(todo) > 1 else f'image {todo[0]}') if kind == 'l' else '1 image'))
        return 0
    if locked():
        raise SystemExit(f'un lot tourne déjà dans {OUT} (voir {VERROU})')
    with open(VERROU, 'w') as fh:
        fh.write(str(os.getpid()))
    signal.signal(signal.SIGINT, halt)
    signal.signal(signal.SIGTERM, halt)
    log(f'lot lancé : {images} images à faire sur {total}, environ {clock(seconds)} · arrêts {size_of("h")[0]} × {size_of("h")[1]}, {args.stop_samples} éch., bruit {args.stop_noise:g} · trajets {size_of("l")[0]} × {size_of("l")[1]}, {args.leg_samples} éch., bruit {args.leg_noise:g} · herbe {args.density:g}')
    failed = 0
    for job in jobs:
        todo = missing(job)
        if not todo:
            continue
        if run(job, todo, jobs) or missing(job):
            failed += 1  # on passe à la suite : une relance retentera ce qui manque
    os.remove(VERROU)
    seconds, images = remaining(jobs)
    log('lot terminé : tout est là' if not images else f'lot terminé avec {images} images manquantes ({failed} tâches en échec) : relancer pour les reprendre')
    return 1 if images else 0


if __name__ == '__main__':
    sys.exit(main())
