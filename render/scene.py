# Le film : sept arrêts et six trajets (Blender 5.x / Cycles, lancé avec le module bpy).
#
#   python3 render/fetch_assets.py && python3 scripts/prints.py           # ciels et impressions
#   python render/scene.py -- --stop 3 --scale 50 --samples 32            # une image d'arrêt → render/out/s50/h_03.png
#   python render/scene.py -- --stop 3 --scale 200 --samples 112          # la même en 3840 × 2160 → render/out/s200/
#   python render/scene.py -- --stop 3 --view top                         # une vue de contrôle → …/h_03_top.png
#   python render/scene.py -- --stop 3 --name essai --set height=0.4      # un essai : réglages nommés (opt), ancres intactes
#   python render/scene.py -- --leg 2 --frames 1-44 --scale 100           # un trajet → render/out/s100/l2_0001.png …
#   python3 render/planches.py                                            # les planches des 7 arrêts, ordinateur et téléphone
#
# Principe d'image : le photoréalisme par le gros plan. La balle est le sujet net, vers x = 0,62 de la
# largeur ; la tête du club est posée derrière elle ; le reste est un flou qui vient d'un vrai panorama
# photographié et d'un sol proche en vrais brins. Aucun parcours n'est modélisé en plan large.
#
# Deux ciels : spruit_sunrise pour le trou 1 (une matinée, brume et rosée), lakeside_sunrise pour le
# trou 2 (une fin d'après-midi dorée au bord d'un lac : c'est l'eau du panorama qu'on voit, pas un plan
# d'eau modélisé). Cinq lieux pour sept arrêts : deux arrêts qu'un coup relie sans coupe partagent le
# même lieu (même ciel, même soleil, même sol). Repère d'un lieu : le coup part vers +X, le joueur
# (droitier) est côté +Y.
#   départ du 1 (arrêt 0) · fairway (1) · green du 1 (2 et 3) · départ du 2 au bord de l'eau (4) · green du 2 (5 et 6)
# Chaque arrêt N a sa balle (BN), son cadrage (view_N) et sa scène (stop_N), qui renvoie un Stage : sa
# caméra, sa balle, son club, son lieu (sol, trou, gazon à replanter). Les trajets s'appuient dessus :
# voir LEGS, key, key_view, key_look et render_leg en bas du fichier.
import argparse
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clubs as C  # noqa: E402
import parts as P  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--stop', type=int, default=None, help="numéro de l'arrêt, de 0 à 6")
ap.add_argument('--leg', type=int, default=None, help='numéro du trajet, de 0 à 5 (de son arrêt de départ)')
ap.add_argument('--frames', default='', help='images du trajet à calculer : « 12 » ou « 1-44 » (toutes par défaut)')
ap.add_argument('--samples', type=int, default=None, help='échantillons (32 pour un arrêt, 16 pour un trajet)')
ap.add_argument('--scale', type=int, default=50)
ap.add_argument('--width', type=int, default=1920)
ap.add_argument('--height', type=int, default=1080)
ap.add_argument('--out', default='', help='dossier de sortie (render/out/s<scale> par défaut)')
ap.add_argument('--name', default='')
ap.add_argument('--sun', type=float, default=None, help="azimut du soleil en degrés (0 = +X), pour les essais")
ap.add_argument('--sky', default='', help='un autre ciel de render/assets, pour les essais')
ap.add_argument('--exposure', type=float, default=None)
ap.add_argument('--view', default='', choices=['', 'top', 'side', 'front', 'wide'], help='vue de contrôle')
ap.add_argument('--force', action='store_true', help='recalcule les images de trajet déjà présentes')
ap.add_argument('--set', default='', help='réglages d\'essai, « nom=valeur,nom=valeur » (voir opt dans les arrêts)')
args = ap.parse_args(argv)
OPT = {k: float(v) for k, v in (kv.split('=') for kv in args.set.split(',') if kv)}


def opt(name, default):
    """Un réglage que --set peut changer le temps d'un essai."""
    return OPT.get(name, default)


V = Vector
T0 = time.time()
OUT = args.out or os.path.join(HERE, 'out', f's{args.scale}')
ANCHORS = os.path.join(HERE, 'out', 'anchors.json')
IDS = ['depart', 'spendmap', 'fnac-darty', 'payfit', 'revenue-engine', 'estimia', 'contact']
STAMP = os.path.join(P.PRINTS, 'ball_stamp.png')
scene = None


def reset(samples):
    """Une scène vide, réglée pour Cycles sur processeur."""
    global scene
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.max_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.transmission_bounces = 6
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.sample_clamp_indirect = 8
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    scene.render.resolution_percentage = args.scale
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.view_settings.view_transform = 'AgX'
    for look in ('AgX - Medium High Contrast', 'Medium High Contrast'):
        try:
            scene.view_settings.look = look
            break
        except TypeError:
            pass
    return scene


class View:
    """Un cadrage : position de la caméra, point visé, focale (mm), ouverture, point net."""

    def __init__(self, pos, target, lens, fstop, focus):
        self.pos, self.target, self.lens, self.fstop, self.focus = V(pos), V(target), lens, fstop, V(focus)


class Stage:
    """Ce qu'un arrêt expose aux trajets. id ; view (son cadrage) et cam (la caméra posée dessus), avec
    les raccourcis cam_pos, target, lens, fstop ; ball (objet) et ball_pos ; club (vide parent, None à
    l'arrêt 6) ; hole (centre du trou ou None) ; flag (objet, ou None si le drapeau est retiré) ; turf
    (le gazon du lieu, à replanter ailleurs avec turf.grow) ; obstacles (ce que l'herbe ne traverse
    pas) ; exposure."""

    def __init__(self, view=None, **kw):
        self.hole = self.flag = self.club = self.turf = None
        self.obstacles = []
        self.view = view
        if view is not None:
            self.cam_pos, self.target, self.lens, self.fstop = view.pos, view.target, view.lens, view.fstop
        self.__dict__.update(kw)
        self.exposure = scene.view_settings.exposure
        self.warmth = scene.view_settings.white_balance_temperature if scene.view_settings.use_white_balance else 6500.0


# ---------------------------------------------------------------- ciel
# Colonne u du soleil dans chaque panorama (repérée sur l'image, vérifiée à l'œil) et sa hauteur.
SUN_U = {
    'spruit_sunrise': (0.5992, 8.0),
    'je_gray_park': (0.6002, 17.1),
    'meadow_2': (0.6000, 28.0),
    'spaichingen_hill': (0.6002, 13.0),
    'rooitou_park': (0.6000, 10.5),
    'park_bench': (0.8973, 19.0),
    'ehingen_hillside': (0.6010, 5.0),
    'lilienstein': (0.6010, 21.0),  # voilé
    'lakeside_sunrise': (0.6002, 5.3),  # soleil bas et doré au-dessus d'un lac, son reflet dans l'eau
    'small_harbour_sunset': (0.6012, 10.1),
    'golf_course_sunrise': (0.5850, 6.3),  # voilé
}


def sun_azimuth(hdr):
    """Azimut (radians, 0 = +X) du point le plus lumineux du ciel, sans rotation.
    Ancienne convention, gardée pour l'arrêt 0 : voir sky_at pour les autres."""
    img = bpy.data.images.load(os.path.join(P.ASSETS, hdr + '.hdr'))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[:, :, :3].sum(axis=2)
    lum = lum[h // 2 :]  # au-dessus de l'horizon
    y, x = np.unravel_index(np.argmax(lum), lum.shape)
    bpy.data.images.remove(img)
    u = (x + 0.5) / w
    v = (y + h // 2 + 0.5) / h
    return math.pi - 2 * math.pi * (u - 0.5), (v - 0.5) * math.pi


def sky_at(hdr, sun, strength=1.0, tint=None, backdrop=1.0, mirror=False):
    """Ciel photographié, tourné pour que son soleil soit à l'azimut `sun` (degrés, 0 = +X, sens
    trigonométrique vu de dessus). Blender place la colonne u dans la direction 2π·(0,5 − u), et la
    rotation tourne le regard : le soleil se retrouve à (azimut d'origine − rotation).
    `tint` : teinte multipliée au ciel (pour réchauffer une fin d'après-midi) ; `backdrop` : le fond vu
    par la caméra, plus clair ou plus sombre que la lumière qu'il donne (on pose pour le ciel, comme un
    photographe à contre-jour) ; `mirror` : le panorama est retourné gauche-droite (ce qui était à
    droite du soleil passe à sa gauche), pour choisir ce qui entre dans le cadre."""
    hdr = args.sky or hdr
    sun = args.sun if args.sun is not None else sun
    u, el = SUN_U[hdr]
    rotation = 2 * math.pi * (0.5 - u) + (1 if mirror else -1) * math.radians(sun)
    world = P.sky(hdr, rotation=rotation, strength=strength * backdrop, light=strength if backdrop != 1.0 else None)
    if mirror:
        next(n for n in world.node_tree.nodes if n.type == 'MAPPING').inputs['Scale'].default_value = (1, -1, 1)
    if tint is not None:
        nt = world.node_tree
        env = next(n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT')
        mul = nt.nodes.new('ShaderNodeMix')
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs['Factor'].default_value = 1.0
        mul.inputs['B'].default_value = (*tint, 1)
        nt.links.new(env.outputs['Color'], mul.inputs['A'])
        nt.links.new(mul.outputs['Result'], nt.nodes['Background'].inputs['Color'])
    print(f'ciel {hdr}{" (miroir)" if mirror else ""} : soleil à {sun:.0f}°, hauteur {el:.1f}°')
    return world


# ---------------------------------------------------------------- caméra
def camera(pos, target, lens, fstop, focus):
    cd = bpy.data.cameras.new('Cam')
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start, cd.clip_end = 0.01, 2000
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cd.dof.aperture_blades = 9
    cd.dof.focus_distance = (V(focus) - V(pos)).length
    cam = P.link(bpy.data.objects.new('Camera', cd))
    cam.location = pos
    P.look_at(cam, target)
    scene.camera = cam
    return cam


def shoot(view):
    """Pose la caméra sur un cadrage."""
    return camera(view.pos, view.target, view.lens, view.fstop, view.focus)


def aim(pos, ball, lens, fx=0.62, fy=0.56):
    """Point à viser depuis `pos` pour que `ball` tombe à (fx, fy) de l'image (0 à 1, y vers le bas)."""
    pos, ball = V(pos), V(ball)
    f = (ball - pos).normalized()
    tx, ty = (fx - 0.5) * 36.0 / lens, -(fy - 0.5) * 20.25 / lens
    v = f.copy()
    for _ in range(6):
        r = v.cross(V((0, 0, 1))).normalized()
        u = r.cross(v)
        v = (v + (f.dot(r) / f.dot(v) - tx) * r + (f.dot(u) / f.dot(v) - ty) * u).normalized()
    return pos + v * (ball - pos).length


def around(centre, azimuth, dist, height):
    """Un point à `dist` mètres de `centre` (à plat), dans la direction `azimuth` (degrés, 0 = +X, sens
    trigonométrique vu de dessus), à la hauteur `height` au-dessus du sol."""
    a = math.radians(azimuth)
    return V((centre[0] + dist * math.cos(a), centre[1] + dist * math.sin(a), height))


def focus_of(cam, point):
    """Position d'un point dans l'image : (x, y) de 0 à 1, y vers le bas."""
    bpy.context.view_layer.update()
    p = world_to_camera_view(scene, cam, V(point))
    return [round(p.x, 4), round(1 - p.y, 4)]


def face_stamp(ball, toward, up=(0, 0, 1), turn=0.0, roll=0.0):
    """Tourne la balle pour que son tampon « AM » regarde le point `toward`. turn : écart en degrés
    autour de la verticale (un tampon pile de face fait posé) ; roll : inclinaison du texte."""
    n = (V(toward) - ball.location).normalized()
    n = Matrix.Rotation(math.radians(turn), 3, 'Z') @ n
    z = V(up) - V(up).dot(n) * n
    z = Matrix.Rotation(math.radians(roll), 3, n) @ z.normalized()
    y = -n
    x = y.cross(z)
    ball.rotation_euler = Matrix((x, y, z)).transposed().to_euler()


# ---------------------------------------------------------------- gazons
class Kind:
    """Une herbe : hauteurs h et demi-largeurs w des brins (mètres), inclinaison, touffes, part de
    brins qui dépassent, sens de tonte (radians, None : en tous sens), teintes, et part de brins secs
    (straw ; None : le gazon doré du départ, où presque tous les brins tirent vers la paille)."""

    def __init__(self, name, h, w, lean=(0.1, 0.9), clump=0.22, tall=0.05, mow=None, spread=0.7, dark=(0.030, 0.105, 0.012), light=(0.105, 0.25, 0.03), glow=(0.27, 0.55, 0.06), translucency=0.38, tone=1.0, straw=None):
        self.name, self.h, self.w, self.lean, self.clump, self.tall, self.mow, self.spread = name, h, w, lean, clump, tall, mow, spread
        self.colours = [tuple(c * tone for c in col) for col in (dark, light, glow)]
        self.translucency = translucency
        self.straw = straw

    def but(self, name, **kw):
        """La même herbe, à quelques réglages près (une bande de tonte dans l'autre sens)."""
        other = Kind.__new__(Kind)
        other.__dict__.update(self.__dict__)
        other.name = name
        tone = kw.pop('tone', None)
        other.__dict__.update(kw)
        if tone is not None:
            other.colours = [tuple(c * tone for c in col) for col in self.colours]
        return other

    def material(self):
        if self.straw is None:
            return P.grass_material('Brin' + self.name, *self.colours, translucency=self.translucency)
        return P.turf_material('Brin' + self.name, *self.colours, translucency=self.translucency, straw=self.straw)


TEE = Kind('Depart', h=(0.0085, 0.0125), w=(0.00060, 0.00110), clump=0.18)
FAIRWAY = Kind('Fairway', h=(0.010, 0.014), w=(0.00062, 0.00115), lean=(0.25, 0.95), clump=0.14, tall=0.03)
COLLAR = Kind('Avantgreen', h=(0.010, 0.0155), w=(0.00070, 0.00130), clump=0.22, tall=0.06, dark=(0.026, 0.095, 0.011), light=(0.095, 0.235, 0.028), straw=0.14)
GREEN = Kind('Green', h=(0.0032, 0.0046), w=(0.00042, 0.00072), lean=(0.05, 0.50), clump=0.05, tall=0.0, dark=(0.030, 0.105, 0.018), light=(0.085, 0.235, 0.045), glow=(0.20, 0.48, 0.09), translucency=0.32, straw=0.07)


class Turf:
    """Le gazon d'un lieu : quelles herbes, et laquelle pousse où."""

    def __init__(self, kinds, which=None, scale=None):
        self.kinds = kinds
        self.which = which  # fonction xy (N,2) → indice dans kinds ; None : une seule herbe
        self.scale = scale  # fonction xy → facteur de hauteur (la lisière d'un green), ou None
        self.sown = []  # ce qui a été planté : (indice de l'herbe, xy, hauteur, orientation, inclinaison)

    def grow(self, xy, obstacles=(), seed=5):
        """Plante un brin en chaque point de xy (N,2). obstacles : fonctions points (N,3) → distance
        signée, que les brins ne traversent pas (ils se couchent)."""
        rng = np.random.default_rng(seed)
        idx = self.which(xy) if self.which else np.zeros(len(xy), dtype=np.int64)
        factor = self.scale(xy) if self.scale else None
        for k, K in enumerate(self.kinds):
            p = xy[idx == k]
            m = len(p)
            if not m:
                continue
            clump = 1 + K.clump * (np.sin(p[:, 0] * 9.1 + 1.3) * np.cos(p[:, 1] * 7.3 + 0.4) + 0.55 * np.sin(p[:, 0] * 23 + p[:, 1] * 17))
            h = (K.h[0] + (K.h[1] - K.h[0]) * rng.random(m) ** 1.4) * clump
            tall = rng.random(m) < K.tall
            h[tall] *= 1.3 + 0.45 * rng.random(tall.sum())
            if factor is not None:
                h *= factor[idx == k]
            w = K.w[0] + (K.w[1] - K.w[0]) * rng.random(m)
            lean = K.lean[0] + (K.lean[1] - K.lean[0]) * rng.random(m)
            yaw = rng.random(m) * 2 * math.pi if K.mow is None else K.mow + rng.normal(0.0, K.spread, m)
            h = P.lay(p, h, yaw, lean, list(obstacles))
            P.blades(p, h, w, yaw, lean, material=K.material(), name='Herbe' + K.name)
            self.sown.append((k, p, h, yaw, lean))
        return self

    def dew(self, centre, radius, share, size=(0.00035, 0.0009), seed=3, only=None):
        """Rosée : des gouttes posées le long des brins, autour de `centre` (x, y). only : indices des
        herbes qui en portent (toutes par défaut)."""
        rng = np.random.default_rng(seed)
        drops = []
        for k, p, h, yaw, lean in self.sown:
            if only is not None and k not in only:
                continue
            pick = (np.hypot(p[:, 0] - centre[0], p[:, 1] - centre[1]) < radius) & (rng.random(len(p)) < share) & (h > 0.002)
            t = 0.5 + 0.5 * rng.random(pick.sum())
            fwd = lean[pick] * h[pick] * t * t
            drops.append(np.stack([p[pick, 0] + np.cos(yaw[pick]) * fwd, p[pick, 1] + np.sin(yaw[pick]) * fwd, h[pick] * t * (1 - 0.15 * t) + 0.0003], axis=1))
        if drops:
            P.dew(np.concatenate(drops), radius=size, seed=seed)


def spread(cam_pos, target, cone, spots=(), back=0.25, seed=1):
    """Où planter : un secteur devant la caméra (dense près d'elle, plus rare au loin, là où tout est
    flou) et des disques serrés autour des sujets. cone : (nombre, près, loin, demi-angle en degrés,
    décroissance) ; spots : [(centre, rayon, nombre), …]."""
    view = V(target) - V(cam_pos)
    view.z = 0
    view.normalize()
    origin = V(cam_pos) - view * back
    n, near, far, half, falloff = cone
    sets = [P.scatter_cone(n, origin, view, near, far, math.radians(half), seed=seed, falloff=falloff)]
    for k, (centre, radius, count) in enumerate(spots):
        sets.append(P.scatter_cone(count, centre, view, 0.0, radius, math.pi, seed=seed + 1 + k, falloff=0.0))
    return np.concatenate(sets)


def ball_obstacle(centre):
    c = np.array(centre, dtype=np.float64)
    return lambda pts: np.linalg.norm(pts - c, axis=1) - P.BALL_R


def post_obstacle(centre, radius):
    """Un poteau vertical (tee, tige du drapeau) : distance à son axe."""
    return lambda pts: np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1]) - radius


def club_obstacle(root):
    return lambda pts: C.distance(root, pts)


def socket_floor(hole):
    """Le fond de la douille où s'emboîte le drapeau : sans lui, on verrait le panorama à travers le godet."""
    x, y, z, r = hole[0], hole[1], -P.CUP_DEPTH - 0.028, 0.012
    o = P.mesh_obj('FondDouille', [(x - r, y - r, z), (x + r, y - r, z), (x + r, y + r, z), (x - r, y + r, z)], [(0, 1, 2, 3)], smooth=False)
    P.assign(o, P.mat('FondDouille', (0.012, 0.011, 0.010), rough=0.9))
    return o


def outside(xy, centre, radius):
    """Garde les points hors d'un cercle (le trou, le pied du tee)."""
    return xy[np.hypot(xy[:, 0] - centre[0], xy[:, 1] - centre[1]) > radius]


# ---------------------------------------------------------------- arrêt 0
def stop_0():
    """Trou 1, le départ, à l'aube : la balle sur un tee bas, la face du bois 3 derrière elle.
    Vue de devant (côté cible), au ras du sol."""
    hdr = 'spruit_sunrise'
    az0, el = sun_azimuth(hdr)
    want = math.radians(args.sun if args.sun is not None else 153)
    P.sky(hdr, rotation=want - az0, strength=1.0)
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -0.6
    print(f'soleil : azimut d’origine {math.degrees(az0):.0f}°, hauteur {math.degrees(el):.1f}°, placé à {math.degrees(want):.0f}°')

    lift = 0.016  # bas de la balle au-dessus du sol
    b = P.ball((0, 0, lift + P.BALL_R), stamp=STAMP)
    b.rotation_euler = (math.radians(-4), math.radians(6), math.radians(62))
    P.tee(top=(0, 0, lift + 0.0015))
    club = P.wood3()
    club.location = (-(P.BALL_R + 0.007), 0.0, 0.003)

    cam_pos = V((0.96, -0.56, 0.092))
    target = V((-0.131, 0.012, 0.044))
    lens, fstop = 115, 2.8
    if args.view == 'top':  # contrôle du club, vu du joueur
        cam_pos, target = V((0.16, 0.34, 0.50)), V((-0.035, 0.0, 0.02))
        cam = camera(cam_pos, target, lens=85, fstop=8, focus=(-0.03, 0, 0.03))
    else:
        cam = camera(cam_pos, target, lens=lens, fstop=fstop, focus=(0, 0, lift + P.BALL_R))

    # L'herbe du départ : dense devant la caméra, plus rare au loin, là où tout est flou.
    view = (target - cam_pos).normalized()
    origin = cam_pos - view * 0.25
    xy = np.concatenate(
        [
            P.scatter_cone(1_000_000, origin, view, 0.1, 10.0, math.radians(21), seed=1),
            P.scatter_cone(160_000, (0.3, -0.15), view, 0.0, 0.9, math.pi, seed=2, falloff=0.0),
        ]
    )
    rng = np.random.default_rng(5)
    n = len(xy)
    # Touffes : la hauteur ondule doucement, avec quelques brins qui dépassent.
    clump = 1 + 0.22 * np.sin(xy[:, 0] * 9.1 + 1.3) * np.cos(xy[:, 1] * 7.3 + 0.4) + 0.12 * np.sin(xy[:, 0] * 23 + xy[:, 1] * 17)
    h = (0.010 + 0.006 * rng.random(n) ** 1.4) * clump
    tall = rng.random(n) < 0.05
    h[tall] *= 1.35 + 0.5 * rng.random(tall.sum())
    w = 0.00065 + 0.00055 * rng.random(n)
    # Les brins ne traversent ni le tee ni la semelle du club.
    keep = np.hypot(xy[:, 0], xy[:, 1]) > 0.004
    xy, h, w = xy[keep], h[keep], w[keep]
    _, tips = P.grass(xy, h, w, seed=11, lean=(0.1, 0.9))
    near = np.hypot(tips[:, 0] - 0.2, tips[:, 1] + 0.1) < 2.2
    pick = near & (rng.random(len(tips)) < 0.11)
    drops = tips[pick].copy()
    drops[:, 2] *= 0.55 + 0.45 * rng.random(len(drops))
    P.dew(drops)
    P.ground(color_near=(0.030, 0.085, 0.012), color_far=(0.23, 0.21, 0.10))
    P.bloom()
    return Stage(View(cam_pos, target, lens, fstop, b.location), id=IDS[0], cam=cam, ball=b, ball_pos=V(b.location), club=club, turf=Turf([TEE]))


# ---------------------------------------------------------------- arrêt 1 : le fairway
B1 = V((0, 0, 0.0045 + P.BALL_R))  # la balle repose sur les brins


def view_1():
    """Trois quarts avant, au ras du sol ; l'horizon haut dans l'image."""
    pos = around(B1, opt('az', -40.4), opt('dist', 1.05), opt('height', 0.095))
    lens = opt('lens', 115)
    return View(pos, aim(pos, B1, lens, 0.625, opt('fy', 0.60)), lens, opt('fstop', 2.8), B1)


def stop_1():
    """Fairway du 1, dans la rosée du matin : la balle sur l'herbe tondue ras, le fer long derrière.
    Vue trois quarts avant, au ras du sol, à contre-jour : la rosée accroche le soleil. Le soleil est
    hors du cadre, à droite ; l'horizon est haut dans l'image, pour ne garder du ciel que la bande des
    arbres dans la brume."""
    sky_at('spruit_sunrise', sun=opt('sun', 116), backdrop=opt('backdrop', 1.0))
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -0.9
    centre = B1
    b = P.ball(centre, stamp=STAMP)
    club = C.iron(kind='long')
    C.address(club, centre, gap=0.004, lift=0.003)

    view = view_1()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    face_stamp(b, cam_pos, turn=-9, roll=5)

    # Bandes de tonte de 2 m, en biais : deux tons, les brins couchés dans un sens puis dans l'autre.
    angle, width, offset = math.radians(118), 2.0, 0.55

    def which(xy):
        return (np.floor((xy[:, 0] * math.cos(angle) + xy[:, 1] * math.sin(angle) + offset) / width) % 2).astype(np.int64)

    turf = Turf([FAIRWAY.but('FairwayA', mow=angle, tone=1.10), FAIRWAY.but('FairwayB', mow=angle + math.pi, tone=0.80)], which)
    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (1_000_000, 0.1, 11.0, 21, 1.0), [((0.25, -0.15), 0.9, 200_000)])
    turf.grow(xy, obstacles)
    turf.dew((0.1, -0.1), 1.0, 0.45, size=(0.0005, 0.0014))
    turf.dew((0.0, 0.0), 3.5, 0.10, size=(0.0006, 0.0015), seed=4)
    P.lawn((0.030, 0.085, 0.012), (0.23, 0.22, 0.11), stripes=(angle, width, 0.22, offset))
    P.bloom()
    return Stage(view, id=IDS[1], cam=cam, ball=b, ball_pos=centre, club=club, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêts 2 et 3 : le green du 1
G1_EDGE = 0.11  # le green commence 11 cm devant la balle de l'arrêt 2
G1_R = 12.0
G1_C = (G1_EDGE + G1_R, 0.0)  # centre du green
G1_HOLE = (19.0, 0.0)  # le trou, dans l'axe du coup, à 19 m de la balle de l'arrêt 2
G1_BALL3 = (16.0, 0.0)  # où la balle s'arrête : à 3 m du trou
G1_SUN = 98.0  # le soleil du matin : à contre-jour pour l'arrêt 2, de côté pour l'arrêt 3


def green_turf(centre, radius, angle=math.radians(35), width=0.56, soft=0.035, green=None):
    """Green ras, tondu à la main en bandes de 56 cm, entouré de l'herbe plus haute de l'avant-green.
    `angle` : direction des bandes. Les brins sont couchés le long de la bande, dans un sens puis dans
    l'autre, à peine : deux tons très proches, et une limite qui se mêle sur quelques centimètres.
    La lisière du green ondule un peu, et l'herbe y monte en quelques centimètres : pas de marche nette."""
    nx, ny = -math.sin(angle), math.cos(angle)  # en travers des bandes

    def beyond(xy):  # distance à la lisière, positive hors du green
        dx, dy = xy[:, 0] - centre[0], xy[:, 1] - centre[1]
        arc = np.arctan2(dy, dx) * radius
        return np.hypot(dx, dy) - radius - 0.006 * np.sin(arc * 23) - 0.004 * np.sin(arc * 61 + 1.0)

    def which(xy):
        s = (xy[:, 0] * nx + xy[:, 1] * ny) / width + 0.03 * np.sin(xy[:, 0] * 0.9 + xy[:, 1] * 1.3)
        t = s - np.floor(s)
        edge = np.minimum(t, 1 - t) * width  # distance à la limite de bande la plus proche
        swap = np.random.default_rng(7).random(len(xy)) < 0.5 * np.clip(1 - edge / soft, 0, 1)
        band = (np.floor(s).astype(np.int64) + swap) % 2
        return np.where(beyond(xy) < 0, 1 + band, 0)

    def scale(xy):
        t = np.clip(beyond(xy) / 0.05, 0, 1)
        return np.where(beyond(xy) < 0, 1.0, 0.36 + 0.64 * t * t * (3 - 2 * t))

    green = green or GREEN
    return Turf([COLLAR, green.but('GreenA', mow=angle, spread=1.25, tone=1.03), green.but('GreenB', mow=angle + math.pi, spread=1.25, tone=0.97)], which, scale)


def place_green1(pin=False):
    """Le green du 1, la même matinée que le départ et le fairway : ciel, sol, trou, drapeau si `pin`
    (il est retiré pour l'approche roulée et le putt). Renvoie le gazon à planter et le drapeau."""
    sky_at('spruit_sunrise', sun=opt('sun', G1_SUN), backdrop=opt('backdrop', 1.0))
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -0.9
    P.lawn((0.028, 0.080, 0.011), (0.20, 0.22, 0.10), hole=(*G1_HOLE, P.CUP_R), disc=(*G1_C, G1_R, (0.034, 0.095, 0.014)), specular=0.12)
    P.cup(G1_HOLE)
    socket_floor(G1_HOLE)
    flag = P.flagstick(G1_HOLE, heading=math.radians(200)) if pin else None
    return green_turf(G1_C, G1_R, angle=math.radians(opt('stripes', 168))), flag


B2 = V((0, 0, 0.005 + P.BALL_R))  # la balle est portée par l'herbe de l'avant-green
B3 = V((G1_BALL3[0], G1_BALL3[1], 0.0015 + P.BALL_R))


def view_2():
    """Trois quarts avant, depuis le green, au ras de l'herbe."""
    pos = around(B2, opt('az', -58), opt('dist', 1.0), opt('height', 0.09))
    lens = opt('lens', 105)
    return View(pos, aim(pos, B2, lens, 0.62, opt('fy', 0.60)), lens, opt('fstop', 3.2), B2)


def view_3():
    """Très longue focale, à 6 m derrière le trou, à hauteur de genou, à peine décalée de la ligne du
    putt : le trou passe juste à gauche de l'aplomb de la balle."""
    pos = V((G1_HOLE[0] + opt('back', 6.0), opt('side', 0.07), opt('height', 0.34)))
    lens = opt('lens', 540)
    # Diaphragme très fermé : à cette focale, c'est ce qui garde au trou, trois mètres devant la balle,
    # un contour lisible.
    return View(pos, aim(pos, B3, lens, 0.62, opt('fy', 0.30)), lens, opt('fstop', 36.0), B3)


def stop_2(pin=False):
    """Bord du green du 1 : la balle dans l'herbe de l'avant-green, à deux doigts du green, la face du
    wedge derrière elle. Vue trois quarts avant, depuis le green, au ras de l'herbe : le tapis ras au
    premier plan, la lisière nette juste devant la balle, puis l'herbe plus haute où elle repose."""
    turf, flag = place_green1(pin)
    centre = B2
    b = P.ball(centre, stamp=STAMP)
    club = C.iron(kind='wedge')
    C.address(club, centre, gap=0.004, lift=0.004)

    view = view_2()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    face_stamp(b, cam_pos, turn=8, roll=-6)

    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (1_100_000, 0.1, 10.0, 22, 1.0), [((0.12, -0.12), 0.8, 320_000)])
    turf.grow(outside(xy, G1_HOLE, P.CUP_R + 0.001), obstacles)
    # La rosée tient sur l'herbe haute ; sur le green, rasé du matin, il n'en reste presque rien.
    turf.dew((0.1, -0.1), 0.9, opt('dew', 0.30), size=(0.0004, 0.0012), only=(0,))
    turf.dew((0.0, 0.0), 3.5, opt('dew', 0.30) * 0.25, size=(0.0005, 0.0014), seed=4, only=(0,))
    if opt('greendew', 0.03):
        turf.dew((0.3, -0.3), 1.2, opt('greendew', 0.03), size=(0.0003, 0.0007), seed=6, only=(1, 2))
    P.bloom()
    return Stage(view, id=IDS[2], cam=cam, ball=b, ball_pos=centre, club=club, hole=G1_HOLE, flag=flag, turf=turf, obstacles=obstacles)


def stop_3(pin=False):
    """Sur le green du 1, à 3 m du trou. Très longue focale, de derrière le trou, comme la caméra d'un
    tournoi : le trou en amorce au premier plan, la balle nette trois mètres plus loin, la face du
    putter derrière elle. Tout le cadre est du green : la lumière de côté y allonge les ombres."""
    turf, flag = place_green1(pin)
    centre = B3
    b = P.ball(centre, stamp=STAMP)
    club = C.putter()
    C.address(club, centre, gap=0.004, lift=0.0012)

    view = view_3()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    face_stamp(b, cam_pos, turn=6, roll=4)

    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (int(opt('blades', 1_500_000)), 4.6, 14.5, 3.0, 0.0), [(G1_BALL3, 0.5, 260_000), (G1_HOLE, 0.35, 160_000)], back=0.0)
    turf.grow(outside(xy, G1_HOLE, P.CUP_R + 0.001), obstacles)
    if opt('dew', 0.0):
        turf.dew(G1_BALL3, 1.2, opt('dew', 0.0), size=(0.0003, 0.0008))
    P.bloom()
    return Stage(view, id=IDS[3], cam=cam, ball=b, ball_pos=centre, club=club, hole=G1_HOLE, flag=flag, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêt 4 : le départ du 2, au bord de l'eau
# L'eau n'est pas modélisée : c'est le lac photographié du panorama, que le sol du départ laisse voir
# au-delà de sa rive. Le coup part vers +X et survole l'eau en biais.
T2_VIEW = 68.0  # azimut du regard (degrés) : la rive du départ est perpendiculaire à lui
T2_EDGE = 1.7  # distance de la balle à la rive, le long du regard
T2_SUN = T2_VIEW - 4.8  # le soleil est au-dessus du cadre, à droite : son reflet descend dans l'eau


B4 = V((0, 0, 0.019 + P.BALL_R))  # sur un tee bas, comme pour un fer : la coupelle dépasse à peine de l'herbe


def view_4():
    """Trois quarts arrière, caméra basse : la rive passe juste au-dessus de la balle, le lac occupe le
    tiers de l'image au-dessus d'elle (c'est ce qu'un téléphone garde du cadre)."""
    pos = around(B4, opt('view', T2_VIEW) + 180, opt('dist', 1.29), opt('height', 0.105))
    lens = opt('lens', 135)
    return View(pos, aim(pos, B4, lens, 0.63, opt('fy', 0.62)), lens, opt('fstop', 8.0), B4)


def stop_4():
    """Départ du 2, un par 3 au-dessus de l'eau, en fin d'après-midi : la balle sur un tee bas, le fer 7
    derrière elle. Vue de trois quarts arrière : le dos du fer, la balle, puis le lac et l'autre rive."""
    view, edge = opt('view', T2_VIEW), opt('edge', T2_EDGE)
    phi = math.radians(view)
    # Le panorama est en miroir : entre deux arbres morts plantés dans l'eau, le cadre ne garde que le
    # lac, la colline d'en face et le reflet du soleil. On pose pour le ciel : il est assombri à l'image.
    sky_at('lakeside_sunrise', sun=view - opt('sun', T2_VIEW - T2_SUN), backdrop=opt('backdrop', 0.38), mirror=True)
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -1.3
    centre = B4
    b = P.ball(centre, stamp=STAMP)
    tee = P.tee(top=(0, 0, centre.z - P.BALL_R + 0.0015))
    tee.data.materials[0] = P.mat('TeeBlanc', (0.86, 0.86, 0.82), rough=0.45, coat_weight=0.2, coat_roughness=0.3)  # blanc : il se lit à contre-jour
    club = C.iron(kind='fer7')
    C.address(club, centre, gap=0.004, lift=0.004)

    framing = view_4()
    cam = shoot(framing)
    cam_pos, target = framing.pos, framing.target
    face_stamp(b, cam_pos, turn=-10, roll=4)

    # Le sol du départ s'arrête à la rive : au-delà, le lac du panorama.
    P.lawn((0.030, 0.085, 0.012), (0.20, 0.21, 0.10), bounds=(-450, edge, -450, 450)).rotation_euler = (0, 0, phi)

    turf = Turf([TEE.but('Depart2', straw=opt('straw', 0.16))])
    obstacles = [ball_obstacle(centre), club_obstacle(club), post_obstacle((0, 0), 0.004)]
    xy = spread(cam_pos, target, (900_000, 0.1, 6.0, 22, 1.0), [((0.0, -0.1), 0.8, 200_000)])
    xy = xy[xy[:, 0] * math.cos(phi) + xy[:, 1] * math.sin(phi) < edge - 0.01]
    turf.grow(outside(xy, (0, 0), 0.006), obstacles)
    P.bloom()
    return Stage(framing, id=IDS[4], cam=cam, ball=b, ball_pos=centre, club=club, tee=tee, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêts 5 et 6 : le green du 2
G2_HOLE = (1.5, 0.0)  # le trou, à 1,5 m de la balle de l'arrêt 5
G2_C = (3.0, 2.5)
G2_R = 11.0
# Sous un soleil très bas et très chaud, un vert ordinaire vire à l'olive : celui-ci renvoie moins de rouge.
GREEN_GOLD = GREEN.but('GreenDore', colours=[(0.022, 0.100, 0.018), (0.060, 0.230, 0.045), (0.14, 0.46, 0.08)])
G2_SUN = 0.0  # le soleil de l'heure dorée, bas, dans l'axe du putt : il éclaire en plein la face du putter


def place_green2(pin=False):
    """Le green du 2, à l'heure dorée, sous le même ciel que le départ au bord de l'eau. Le drapeau
    n'y est que si `pin` : il est retiré pour le putt."""
    sky_at('lakeside_sunrise', sun=G2_SUN, backdrop=opt('backdrop', 0.8), mirror=True)
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -1.5
    P.lawn((0.028, 0.080, 0.011), (0.22, 0.20, 0.09), hole=(*G2_HOLE, P.CUP_R), disc=(*G2_C, G2_R, (0.034, 0.095, 0.014)), specular=0.2)
    P.cup(G2_HOLE)
    socket_floor(G2_HOLE)
    flag = P.flagstick(G2_HOLE, heading=math.radians(215)) if pin else None
    return green_turf(G2_C, G2_R, angle=math.radians(opt('stripes', 152)), green=GREEN_GOLD), flag


B5 = V((0, 0, 0.0015 + P.BALL_R))
G2_UP = math.radians(G2_SUN + 135)  # le haut de l'image de l'arrêt 6 : le soleil y vient d'en bas à droite
# Au fond du godet, contre sa paroi du haut de l'image (à une heure) : la caméra, un peu penchée, la voit
# entière, et le godet reste centré sur elle quand un téléphone recadre.
B6 = V((G2_HOLE[0] + 0.0312 * math.cos(G2_UP - math.radians(12)), G2_HOLE[1] + 0.0312 * math.sin(G2_UP - math.radians(12)), -P.CUP_DEPTH + P.BALL_R))


def view_5():
    """Trois quarts avant, au ras du green."""
    pos = around(B5, opt('az', -50), opt('dist', 1.05), opt('height', 0.085))
    lens = opt('lens', 115)
    return View(pos, aim(pos, B5, lens, 0.62, opt('fy', 0.60)), lens, opt('fstop', 3.2), B5)


def view_6():
    """Plongée sur le trou, d'un peu plus d'un mètre, penchée de 28° : on voit la paroi du fond, sa bande
    de terre au soleil, et le gazon se floute en haut et en bas. Le godet entier tient dans la bande
    que garde un téléphone."""
    tilt, dist = math.radians(opt('tilt', 28)), opt('dist', 1.22)
    pos = V((G2_HOLE[0] - dist * math.sin(tilt) * math.cos(G2_UP), G2_HOLE[1] - dist * math.sin(tilt) * math.sin(G2_UP), dist * math.cos(tilt)))
    return View(pos, aim(pos, B6, 85, 0.62, opt('fy', 0.47)), 85, opt('fstop', 2.8), B6 + V((0, 0, P.BALL_R)))


def stop_5(pin=False):
    """Green du 2, à 1,5 m du trou, à l'heure dorée : la balle, la face fraisée du putter derrière elle.
    Vue trois quarts avant, au ras du green ; le soleil bas vient de la droite et allonge les ombres.
    Le trou est à droite, hors du cadre : c'est le trajet qui y mène."""
    turf, flag = place_green2(pin)
    centre = B5
    b = P.ball(centre, stamp=STAMP)
    club = C.putter()
    C.address(club, centre, gap=0.004, lift=0.0012)

    view = view_5()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    face_stamp(b, cam_pos, turn=-13, roll=-5)  # le tampon à gauche du reflet du soleil

    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (1_100_000, 0.1, 10.0, 21, 1.0), [((0.15, -0.2), 0.8, 380_000)])
    turf.grow(outside(xy, G2_HOLE, P.CUP_R + 0.001), obstacles)
    P.bloom()
    return Stage(view, id=IDS[5], cam=cam, ball=b, ball_pos=centre, club=club, hole=G2_HOLE, flag=flag, turf=turf, obstacles=obstacles)


def stop_6(pin=False):
    """Le contact : la balle au fond du trou du 2. Vue plongeante : le godet blanc, la bande de terre
    au soleil, le bord de gazon ras dans la lumière dorée."""
    turf, flag = place_green2(pin)
    up = G2_UP
    hx, hy = G2_HOLE
    centre = B6
    b = P.ball(centre, stamp=STAMP)
    # Le soleil rasant n'entre pas dans le trou : le godet n'est éclairé que par le ciel, bleu. On pose
    # pour lui, et on réchauffe la balance des blancs, comme le ferait un photographe à l'ombre.
    scene.view_settings.exposure = args.exposure if args.exposure is not None else 1.1
    if opt('wb', 8500):
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = opt('wb', 8500)

    view = view_6()
    cam = shoot(view)
    cam_pos = view.pos
    face_stamp(b, cam_pos, up=(math.cos(up), math.sin(up), 0), turn=0, roll=-9)

    obstacles = []
    xy = spread(cam_pos, V((hx, hy, 0)) + V((math.cos(up), math.sin(up), 0)), (160_000, 0.1, 2.6, 180, 1.0), [(G2_HOLE, 0.65, 1_700_000)], back=0.0)
    turf.grow(outside(xy, G2_HOLE, P.CUP_R + 0.0008), obstacles)
    P.bloom()
    return Stage(view, id=IDS[6], cam=cam, ball=b, ball_pos=centre, hole=G2_HOLE, flag=flag, turf=turf, obstacles=obstacles)


STOPS = [stop_0, stop_1, stop_2, stop_3, stop_4, stop_5, stop_6]


# ---------------------------------------------------------------- vues de contrôle
def control_camera(stage, view):
    """Remplace la vue de la frappe par une vue de contrôle autour de la balle."""
    b = V(stage.ball_pos)
    if view == 'wide':  # le lieu, de plus haut et de plus loin, dans l'axe de la vue de la frappe
        back = V(stage.cam_pos) - b
        back.z = 0
        pos = b + back.normalized() * 3.2 + V((0, 0, 1.3))
        return camera(pos, b, lens=28, fstop=16, focus=b)
    pos, lens = {'top': (V((-0.012, 0.11, 0.80)), 110), 'side': (V((0.0, -0.62, 0.11)), 85), 'front': (V((0.62, -0.06, 0.11)), 85)}[view]
    return camera(b + pos, b + V((-0.015, 0.0, 0.0)), lens=lens, fstop=8, focus=b)


def save_anchor(k, stage):
    """Note où tombe la balle dans l'image de l'arrêt k : le site recadre autour d'elle."""
    data = {}
    if os.path.exists(ANCHORS):
        with open(ANCHORS, encoding='utf8') as fh:
            data = json.load(fh)
    data[str(k)] = {'id': IDS[k], 'focus': focus_of(stage.cam, stage.ball_pos)}
    os.makedirs(os.path.dirname(ANCHORS), exist_ok=True)
    with open(ANCHORS, 'w', encoding='utf8') as fh:
        json.dump(dict(sorted(data.items())), fh, indent=1)
    return data[str(k)]['focus']


def render_stop(k):
    reset(args.samples or 32)
    stage = STOPS[k]()
    if args.view and k != 0:
        control_camera(stage, args.view)
    elif not args.view and not args.name:  # un essai nommé ne touche pas aux ancres
        print('balle à', save_anchor(k, stage))
    path = os.path.join(OUT, (args.name or (f'h_{k:02d}' + (f'_{args.view}' if args.view else ''))) + '.png')
    os.makedirs(OUT, exist_ok=True)
    t1 = time.time()
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    print(f'RESULT {path} construction {t1 - T0:.1f}s rendu {time.time() - t1:.1f}s')


# ---------------------------------------------------------------- trajets
# Un trajet est une suite de plans : (première image, dernière image, fonction). Un plan = un lieu, une
# prise sans coupe ; un raccord entre deux lieux = deux plans (dans le ciel, ou dans le noir du trou).
# La fonction d'un plan reçoit ses deux numéros d'image et construit sa scène à partir d'un arrêt :
#
#   def putt_du_2(first, last):
#       a = stop_5()                                  # le lieu, la caméra, la balle, le putter, l'herbe
#       end = view_6()                                # le cadrage d'arrivée, sans construire l'arrêt 6
#       # L'herbe n'est plantée que là où la vue de l'arrêt en a besoin : on replante le long du mouvement.
#       a.turf.grow(outside(spread(end.pos, end.target, (60_000, 0.1, 2.4, 180, 1.0), [(G2_HOLE, 0.55, 900_000)], back=0.0), G2_HOLE, P.CUP_R + 0.001), a.obstacles, seed=9)
#       key(a.club, first, a.club.location)           # clés d'animation : club, balle, caméra
#       key(a.ball, 12, B5)
#       key(a.ball, 36, B6)
#       key_view(a.cam, first, a.view)
#       key_view(a.cam, last, end)
#       key_look(first, a.exposure, a.warmth)         # l'arrêt 6 est posé pour l'ombre du godet
#       key_look(last, 1.1, 8500)
#   LEGS[5] = [(1, 44, putt_du_2)]
#
# Le flou de mouvement vient des clés. La première image d'un trajet est la vue de son arrêt de départ
# (a.view), la dernière celle de l'arrêt d'arrivée (view_N) : la page enchaîne sur l'image nette par un
# fondu. Les arrêts 2, 3, 5 et 6 se construisent sans drapeau ; stop_N(pin=True) le remet dans le trou.
# Si la frappe et la chute ne tombent pas à 20 % et 85 % du trajet, écrire leurs images dans
# render/out/legs.json ({"5": {"impact": 12, "land": 36}}) : scripts/frames.py les porte au manifeste.
LEG_FRAMES = 44
LEGS = [None] * 6  # LEGS[k] = [(1, 20, plan_a), (21, 44, plan_b)] : à écrire


def key(obj, frame, location=None, rotation=None):
    """Pose une clé d'animation sur un objet : sa position, et son orientation (angles d'Euler) si donnée."""
    if location is not None:
        obj.location = location
        obj.keyframe_insert('location', frame=frame)
    if rotation is not None:
        obj.rotation_euler = rotation
        obj.keyframe_insert('rotation_euler', frame=frame)


def key_view(cam, frame, view):
    """Pose la caméra sur un cadrage à une image donnée : position, visée, focale, mise au point, ouverture."""
    cam.location = view.pos
    P.look_at(cam, view.target)
    cam.keyframe_insert('location', frame=frame)
    cam.keyframe_insert('rotation_euler', frame=frame)
    cam.data.lens = view.lens
    cam.data.dof.focus_distance = (view.focus - view.pos).length
    cam.data.dof.aperture_fstop = view.fstop
    cam.data.keyframe_insert('lens', frame=frame)
    cam.data.dof.keyframe_insert('focus_distance', frame=frame)
    cam.data.dof.keyframe_insert('aperture_fstop', frame=frame)


def key_look(frame, exposure=None, warmth=None):
    """Clé sur le développement de l'image : l'exposition, et la balance des blancs (kelvins ; 6500 :
    neutre). Deux arrêts d'un même lieu ne sont pas posés pareil (stage.exposure, stage.warmth)."""
    vs = scene.view_settings
    if exposure is not None:
        vs.exposure = exposure
        scene.keyframe_insert('view_settings.exposure', frame=frame)
    if warmth is not None:
        vs.use_white_balance = True
        vs.white_balance_temperature = warmth
        scene.keyframe_insert('view_settings.white_balance_temperature', frame=frame)


def render_leg(k):
    shots = LEGS[k]
    if not shots:
        raise SystemExit(f'trajet {k} → {k + 1} : pas encore écrit (voir LEGS dans render/scene.py)')
    first, _, last = args.frames.partition('-')
    first = int(first) if first else 1
    last = int(last) if last else (first if args.frames else LEG_FRAMES)
    os.makedirs(OUT, exist_ok=True)
    for start, end, build in shots:
        todo = [n for n in range(max(first, start), min(last, end) + 1) if args.force or not os.path.exists(os.path.join(OUT, f'l{k}_{n:04d}.png'))]
        if not todo:
            continue
        reset(args.samples or 16)
        scene.render.use_motion_blur = True
        scene.render.motion_blur_shutter = 0.5
        scene.frame_start, scene.frame_end = 1, LEG_FRAMES
        build(start, end)
        for n in todo:
            t1 = time.time()
            scene.frame_set(n)
            path = os.path.join(OUT, f'l{k}_{n:04d}.png')
            scene.render.filepath = os.path.abspath(path)
            bpy.ops.render.render(write_still=True)
            print(f'RESULT {path} rendu {time.time() - t1:.1f}s')


if __name__ == '__main__':
    if args.leg is not None:
        render_leg(args.leg)
    else:
        render_stop(args.stop or 0)
