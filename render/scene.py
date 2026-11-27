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
import finish as F  # noqa: E402
import parts as P  # noqa: E402
import strike as K  # noqa: E402

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
ap.add_argument('--crop', default='', help='ne calcule qu\'un recadrage : « x0,y0,x1,y1 » de 0 à 1, y vers le bas (pour juger une matière à l\'échelle 200)')
ap.add_argument('--force', action='store_true', help='recalcule les images de trajet déjà présentes')
ap.add_argument('--set', default='', help='réglages d\'essai, « nom=valeur,nom=valeur » (voir opt dans les arrêts)')
# Réglages de qualité, pour le rendu en haute définition (render/batch.py) : sans eux, rien ne change.
ap.add_argument('--noise', type=float, default=None, help="seuil de bruit de l'échantillonnage adaptatif (0,02 par défaut ; 0 : tous les échantillons partout)")
ap.add_argument('--min-samples', type=int, default=None, help="échantillons au moins par pixel avant que l'adaptatif ne s'arrête (choisi par Cycles par défaut)")
ap.add_argument('--denoise', default='', choices=['', 'oidn', 'non'], help='débruitage : oidn (par défaut) ou non')
ap.add_argument('--shutter', type=float, default=None, help="obturateur du flou de mouvement d'un trajet, en images (0,5 par défaut ; 0 : pas de flou)")
ap.add_argument('--blur-steps', type=int, default=None, help='étapes du flou de mouvement de chaque objet (1 par défaut : trois positions par image)')
ap.add_argument('--no-persistent', action='store_true', help="trajet : reconstruit tout à chaque image (pour mesurer ce que rapportent les données gardées d'une image à l'autre)")
ap.add_argument('--threads', type=int, default=None, help='nombre de fils de calcul (tous les cœurs par défaut)')
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
    scene.cycles.use_adaptive_sampling = args.noise is None or args.noise > 0
    scene.cycles.adaptive_threshold = args.noise or 0.02
    if args.min_samples is not None:
        scene.cycles.adaptive_min_samples = args.min_samples
    scene.cycles.use_denoising = args.denoise != 'non'
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    if args.threads:
        scene.render.threads_mode = 'FIXED'
        scene.render.threads = args.threads
    scene.cycles.max_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.transmission_bounces = 6
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.cycles.sample_clamp_indirect = opt('clamp', 8)
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
    if args.crop:
        x0, y0, x1, y1 = (float(v) for v in args.crop.split(','))
        r = scene.render
        r.use_border = r.use_crop_to_border = True
        r.border_min_x, r.border_max_x, r.border_min_y, r.border_max_y = x0, x1, 1 - y1, 1 - y0
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


SUN = {'dir': (0.0, 0.0, 1.0), 'az': 0.0, 'el': 90.0}  # le soleil du lieu en cours : la rosée et les trajets s'en servent
MIST = ((0.05, 0.06, 0.08), 0.42, 7.0)  # brume du matin : voile ajouté, part, hauteur (degrés) où elle s'efface
MORNING, EVENING = 5900.0, 7300.0  # balance des blancs : matin froid, soir chaud (6500 : neutre)
LAWN = (0.022, 0.075, 0.022)  # le sol sous les brins
FAR_MIST = (0.13, 0.19, 0.14)  # le sol lointain du matin, pris dans la brume


def sky_at(hdr, sun, strength=1.0, tint=None, backdrop=1.0, mirror=False, mist=None, gloss=0.5):
    """Ciel photographié, tourné pour que son soleil soit à l'azimut `sun` (degrés, 0 = +X, sens
    trigonométrique vu de dessus). Blender place la colonne u dans la direction 2π·(0,5 − u), et la
    rotation tourne le regard : le soleil se retrouve à (azimut d'origine − rotation).
    `tint` : teinte multipliée au ciel (pour réchauffer une fin d'après-midi) ; `backdrop` : le fond vu
    par la caméra, plus clair ou plus sombre que la lumière qu'il donne (on pose pour le ciel, comme un
    photographe à contre-jour) ; `mirror` : le panorama est retourné gauche-droite (ce qui était à
    droite du soleil passe à sa gauche), pour choisir ce qui entre dans le cadre ; `mist` : (voile,
    part, hauteur) une brume qui pâlit et désature le bas du ciel, jusqu'à `hauteur` degrés ; `gloss` :
    saturation du ciel dans les reflets (un manche chromé sous un ciel pur vire au bleu vif)."""
    hdr = args.sky or hdr
    sun = args.sun if args.sun is not None else sun
    u, el = SUN_U[hdr]
    rotation = 2 * math.pi * (0.5 - u) + (1 if mirror else -1) * math.radians(sun)
    world = P.sky(hdr, rotation=rotation, strength=strength * backdrop, light=strength if backdrop != 1.0 else None)
    nt = world.node_tree
    if mirror:
        next(n for n in nt.nodes if n.type == 'MAPPING').inputs['Scale'].default_value = (1, -1, 1)
    colour = next(n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT').outputs['Color']

    def blend(kind, factor, a, b):
        n = nt.nodes.new('ShaderNodeMix')
        n.data_type = 'RGBA'
        n.blend_type = kind
        for socket, v in ((n.inputs['Factor'], factor), (n.inputs['A'], a), (n.inputs['B'], b)):
            if hasattr(v, 'is_linked'):
                nt.links.new(v, socket)
            else:
                socket.default_value = (*v, 1) if isinstance(v, tuple) else v
        return n.outputs['Result']

    def grey(c):
        n = nt.nodes.new('ShaderNodeRGBToBW')
        nt.links.new(c, n.inputs[0])
        return n.outputs[0]

    if tint is not None:
        colour = blend('MULTIPLY', 1.0, colour, tuple(tint))
    if mist is not None:
        veil, amount, top = mist
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(next(n for n in nt.nodes if n.type == 'TEX_COORD').outputs['Generated'], sep.inputs[0])
        low = nt.nodes.new('ShaderNodeMapRange')
        low.interpolation_type = 'SMOOTHSTEP'
        for name, v in (('From Min', math.sin(math.radians(top))), ('From Max', 0.0), ('To Min', 0.0), ('To Max', amount)):
            low.inputs[name].default_value = v
        nt.links.new(sep.outputs['Z'], low.inputs['Value'])
        pale = blend('ADD', 1.0, blend('MULTIPLY', 1.0, grey(colour), (0.93, 0.98, 1.09)), tuple(veil))
        colour = blend('MIX', low.outputs[0], colour, pale)
    if gloss < 1.0:
        path = nt.nodes.new('ShaderNodeLightPath')
        colour = blend('MIX', path.outputs['Is Glossy Ray'], colour, blend('MIX', 1.0 - gloss, colour, grey(colour)))
    nt.links.new(colour, nt.nodes['Background'].inputs['Color'])
    a, e = math.radians(sun), math.radians(el)
    SUN.update(dir=(math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)), az=sun, el=el)
    print(f'ciel {hdr}{" (miroir)" if mirror else ""} : soleil à {sun:.0f}°, hauteur {el:.1f}°')
    return world


def look(exposure, warmth=6500.0):
    """Le développement de l'image d'un lieu : exposition, et balance des blancs (kelvins ; plus haut :
    image plus chaude)."""
    vs = scene.view_settings
    vs.exposure = args.exposure if args.exposure is not None else opt('ev', exposure)
    warmth = opt('wb', warmth)
    vs.use_white_balance = abs(warmth - 6500.0) > 1.0
    vs.white_balance_temperature = warmth


# ---------------------------------------------------------------- caméra
# Essai (--set near=0.017) : le plan net avancé d'autant de mètres vers la caméra. Le point net d'un
# arrêt est le centre de la balle ; son tampon, 2 cm plus près, est alors flou d'une dizaine de pixels
# en 3840 × 2160. À 0, rien ne change. Les suivis de caméra (K.track) ne le lisent pas.
NEAR = opt('near', 0.0)


def camera(pos, target, lens, fstop, focus):
    cd = bpy.data.cameras.new('Cam')
    cd.lens = lens
    cd.sensor_width = 36
    cd.clip_start, cd.clip_end = 0.01, 2000
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = fstop
    cd.dof.aperture_blades = 9
    cd.dof.focus_distance = (V(focus) - V(pos)).length - NEAR
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


def face_stamp(ball, toward, up=(0, 0, 1), turn=0.0, roll=0.0, at=None):
    """Tourne la balle pour que son tampon « AM » regarde le point `toward`. turn : écart en degrés
    autour de la verticale (un tampon pile de face fait posé) ; roll : inclinaison du texte. Renvoie
    l'orientation (quaternion) ; `at` : centre de la balle si elle n'y est pas encore (un trajet l'y
    amène), et `ball` peut alors valoir None."""
    n = (V(toward) - V(at if at is not None else ball.location)).normalized()
    n = Matrix.Rotation(math.radians(turn), 3, 'Z') @ n
    z = V(up) - V(up).dot(n) * n
    z = Matrix.Rotation(math.radians(roll), 3, n) @ z.normalized()
    y = -n
    x = y.cross(z)
    rot = Matrix((x, y, z)).transposed()
    if ball is not None:
        ball.rotation_euler = rot.to_euler()
    return rot.to_quaternion()


# ---------------------------------------------------------------- gazons
class Kind:
    """Une herbe : hauteurs h et demi-largeurs w des brins (mètres), inclinaison, touffes, part de
    brins qui dépassent, sens de tonte (radians, None : en tous sens), teintes (un vert qui garde du
    bleu), part de brins secs, largeur du bout coupé (part de la base : un gazon tondu n'a pas de
    pointes), variation du ton par grandes taches, et brillant du brin (rugosité, velouté, reflet)."""

    def __init__(self, name, h, w, lean=(0.1, 0.9), clump=0.22, tall=0.015, mow=None, spread=0.7, dark=(0.020, 0.090, 0.022), light=(0.070, 0.225, 0.052), glow=(0.19, 0.50, 0.10), translucency=0.38, tone=1.0, straw=0.05, tip=0.55, mottle=0.10, shine=(0.42, 0.25, 0.5)):
        self.name, self.h, self.w, self.lean, self.clump, self.tall, self.mow, self.spread = name, h, w, lean, clump, tall, mow, spread
        self.colours = [tuple(c * tone for c in col) for col in (dark, light, glow)]
        self.translucency, self.straw, self.tip, self.mottle, self.shine = translucency, straw, tip, mottle, shine

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
        return P.turf_material('Brin' + self.name, *self.colours, translucency=self.translucency, straw=self.straw, straw_colour=(0.30, 0.29, 0.11), patches=0.6, mottle=self.mottle, rough=self.shine[0], sheen=self.shine[1], specular=self.shine[2])


TEE = Kind('Depart', h=(0.0085, 0.0125), w=(0.00060, 0.00110), clump=0.18)
FAIRWAY = Kind('Fairway', h=(0.010, 0.014), w=(0.00062, 0.00115), lean=(0.25, 0.95), clump=0.14, tall=0.012, straw=0.04)
COLLAR = Kind('Avantgreen', h=(0.010, 0.0155), w=(0.00070, 0.00130), clump=0.22, tall=0.03, straw=0.07)
GREEN = Kind('Green', h=(0.0032, 0.0046), w=(0.00042, 0.00072), lean=(0.05, 0.50), clump=0.05, tall=0.0, dark=(0.030, 0.120, 0.038), light=(0.056, 0.205, 0.066), glow=(0.15, 0.44, 0.13), translucency=0.32, straw=0.0, mottle=0.14, shine=(0.62, 0.05, 0.15))


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
            P.blades(p, h, w, yaw, lean, material=K.material(), name='Herbe' + K.name, tip=K.tip)
            self.sown.append((k, p, h, yaw, lean))
        return self

    def dew(self, centre, radius, share, size=(0.0006, 0.0015), seed=3, only=None, focus=None, camera=None):
        """Rosée : des gouttes perlées en haut des brins, autour de `centre` (x, y) ; share : part des
        brins qui en portent ; size : rayons. only : indices des herbes qui en portent (toutes par
        défaut) ; focus : le point net, autour duquel les gouttes sont maillées finement ; camera : sa
        position, pour éclaircir la rosée du premier plan (très floue, elle voilerait l'image de blanc)."""
        rng = np.random.default_rng(seed)
        pts, rad = [], []
        for k, p, h, yaw, lean in self.sown:
            if only is not None and k not in only:
                continue
            chance = np.full(len(p), share)
            if camera is not None and focus is not None:
                reach = math.hypot(focus[0] - camera[0], focus[1] - camera[1])
                chance[np.hypot(p[:, 0] - camera[0], p[:, 1] - camera[1]) < reach - 0.22] *= 0.15
            pick = (np.hypot(p[:, 0] - centre[0], p[:, 1] - centre[1]) < radius) & (rng.random(len(p)) < chance) & (h > 0.002)
            n = int(pick.sum())
            t = 1.0 - 0.45 * rng.random(n) ** 2
            r = size[0] + (size[1] - size[0]) * rng.random(n) ** 2
            fwd = lean[pick] * h[pick] * t * t
            pts.append(np.stack([p[pick, 0] + np.cos(yaw[pick]) * fwd, p[pick, 1] + np.sin(yaw[pick]) * fwd, h[pick] * t * (1 - 0.15 * t) + 0.6 * r], axis=1))
            rad.append(r)
        if pts and sum(len(r) for r in rad):
            pts, rad = np.concatenate(pts), np.concatenate(rad)
            fine = np.linalg.norm(pts - np.array(focus), axis=1) < 0.22 if focus is not None else None
            P.drops(pts, rad, SUN['dir'], fine=fine, glint=(opt('glint', 500.0), opt('glint1', 40.0), opt('glint2', 200.0)))
            print(f'rosée : {len(pts)} gouttes')


DENSITY = opt('density', 1.0)  # part des brins plantés : moins pour une animatique, où tout bouge


def spread(cam_pos, target, cone, spots=(), back=0.25, seed=1):
    """Où planter : un secteur devant la caméra (dense près d'elle, plus rare au loin, là où tout est
    flou) et des disques serrés autour des sujets. cone : (nombre, près, loin, demi-angle en degrés,
    décroissance) ; spots : [(centre, rayon, nombre), …]."""
    view = V(target) - V(cam_pos)
    view.z = 0
    view.normalize()
    origin = V(cam_pos) - view * back
    n, near, far, half, falloff = cone
    sets = [P.scatter_cone(int(n * DENSITY), origin, view, near, far, math.radians(half), seed=seed, falloff=falloff)]
    for k, (centre, radius, count) in enumerate(spots):
        sets.append(P.scatter_cone(int(count * DENSITY), centre, view, 0.0, radius, math.pi, seed=seed + 1 + k, falloff=0.0))
    return np.concatenate(sets)


def ball_obstacle(centre):
    c = np.array(centre, dtype=np.float64)
    return lambda pts: np.linalg.norm(pts - c, axis=1) - P.BALL_R


def post_obstacle(centre, radius):
    """Un poteau vertical (tee, tige du drapeau) : distance à son axe."""
    return lambda pts: np.hypot(pts[:, 0] - centre[0], pts[:, 1] - centre[1]) - radius


def club_obstacle(root):
    return lambda pts: C.distance(root, pts)


def wood_obstacle(root):
    """Le dessous de la tête du bois 3 (distance approchée, négative dedans) : son contour vu de
    dessus et sa semelle bombée, d'après les cotes de parts.wood3."""
    ox, oy, oz = root.location
    a, b, xc, zmid, h_bot = 0.056, 0.051, -0.042, 0.0145, 0.0145

    def f(pts):
        dx, dy = (pts[:, 0] - ox - xc) / a, (pts[:, 1] - oy) / b
        r = np.maximum(np.hypot(dx, dy), 1e-9)
        c, s = dx / r, dy / r
        ex = np.where(c > 0, 3.6, 2.15)
        rho = r * (np.abs(c) ** ex + np.abs(s) ** ex) ** (1 / ex)
        sole = oz + zmid - h_bot * np.maximum(1 - np.minimum(rho, 1.0) ** 3.6, 0.0) ** (1 / 2.6)
        return np.maximum((rho - 1.0) * 0.05, sole - pts[:, 2])

    return f


def socket_floor(hole):
    """Le fond de la douille où s'emboîte le drapeau : sans lui, on verrait le panorama à travers le godet."""
    x, y, z, r = hole[0], hole[1], -P.CUP_DEPTH - 0.028, 0.012
    o = P.mesh_obj('FondDouille', [(x - r, y - r, z), (x + r, y - r, z), (x + r, y + r, z), (x - r, y + r, z)], [(0, 1, 2, 3)], smooth=False)
    P.assign(o, P.mat('FondDouille', (0.012, 0.011, 0.010), rough=0.9))
    return o


def outside(xy, centre, radius):
    """Garde les points hors d'un cercle (le trou, le pied du tee)."""
    return xy[np.hypot(xy[:, 0] - centre[0], xy[:, 1] - centre[1]) > radius]


# ---------------------------------------------------------------- arrêt 0 : le départ du 1
B0 = V((0, 0, 0.016 + P.BALL_R))  # sur un tee bas
T1_SUN = 200.0  # à contre-jour pour la vue de la frappe ; l'ombre du joueur tombe loin de la balle


def view_0():
    """De devant (côté cible), au ras du sol."""
    pos = V((0.96, -0.56, 0.092))
    return View(pos, V((-0.131, 0.012, 0.044)), 115, opt('fstop', 2.8), B0)


def stop_0():
    """Trou 1, le départ, à l'aube : la balle sur un tee bas, la face du bois 3 derrière elle. Vue de
    devant (côté cible), au ras du sol, à contre-jour : le soleil, derrière le départ et hors du cadre,
    ourle la balle et la couronne du bois, traverse l'herbe et allume la rosée ; au fond, la bande des
    arbres dans la brume."""
    sky_at('spruit_sunrise', sun=opt('sun', T1_SUN), mist=MIST)
    look(-0.35, MORNING)
    centre = B0
    b = P.ball(centre, stamp=STAMP)
    tee = P.tee(top=(0, 0, centre.z - P.BALL_R + 0.0015))
    club = P.wood3()
    club.location = (-(P.BALL_R + 0.007), 0.0, 0.003)

    view = view_0()
    cam = shoot(view)
    face_stamp(b, view.pos, turn=-6, roll=5)

    turf = Turf([TEE])
    obstacles = [ball_obstacle(centre), post_obstacle((0, 0), 0.004), wood_obstacle(club)]
    xy = spread(view.pos, view.target, (1_000_000, 0.1, 10.0, 21, 1.0), [((0.3, -0.15), 0.9, 240_000)])
    turf.grow(outside(xy, (0, 0), 0.004), obstacles)
    turf.dew((0.2, -0.1), 1.2, opt('dew', 0.03), focus=centre, camera=view.pos)
    turf.dew((0.0, 0.0), 3.5, opt('dew', 0.03) * 0.3, size=(0.0008, 0.0018), seed=4, focus=centre, camera=view.pos)
    P.lawn(LAWN, FAR_MIST, haze=(20, 200))
    P.bloom(threshold=2.0)
    return Stage(view, id=IDS[0], cam=cam, ball=b, ball_pos=centre, club=club, tee=tee, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêt 1 : le fairway
B1 = V((0, 0, 0.0045 + P.BALL_R))  # la balle repose sur les brins
F1_SUN = 165.0  # derrière la balle, à peine du côté du joueur : contre-jour, et son ombre passe loin devant elle


def view_1():
    """Trois quarts avant, au ras du sol ; l'horizon haut dans l'image."""
    pos = around(B1, opt('az', -40.4), opt('dist', 1.05), opt('height', 0.095))
    lens = opt('lens', 115)
    return View(pos, aim(pos, B1, lens, 0.625, opt('fy', 0.60)), lens, opt('fstop', 2.8), B1)


def stop_1():
    """Fairway du 1, dans la rosée du matin : la balle sur l'herbe tondue ras, le fer long derrière.
    Vue trois quarts avant, au ras du sol, à contre-jour : la rosée accroche le soleil. Le soleil est
    hors du cadre, au-dessus à gauche ; l'horizon est haut dans l'image, pour ne garder du ciel que la
    bande des arbres dans la brume."""
    sky_at('spruit_sunrise', sun=opt('sun', F1_SUN), backdrop=opt('backdrop', 1.0), mist=MIST)
    look(-0.7, MORNING)
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
    xy = spread(cam_pos, target, (1_000_000, 0.1, 11.0, 21, 1.0), [((0.25, -0.15), 0.9, 300_000)])
    turf.grow(xy, obstacles)
    turf.dew((0.1, -0.1), 1.0, opt('dew', 0.025), focus=centre, camera=cam_pos)
    turf.dew((0.0, 0.0), 3.5, opt('dew', 0.025) * 0.3, size=(0.0008, 0.0018), seed=4, focus=centre, camera=cam_pos)
    P.lawn(LAWN, FAR_MIST, haze=(20, 200), stripes=(angle, width, 0.22, offset))
    P.bloom()
    return Stage(view, id=IDS[1], cam=cam, ball=b, ball_pos=centre, club=club, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêts 2 et 3 : le green du 1
G1_EDGE = 0.11  # le green commence 11 cm devant la balle de l'arrêt 2
G1_R = 12.0
G1_C = (G1_EDGE + G1_R, 0.0)  # centre du green
G1_HOLE = (19.0, 0.0)  # le trou, dans l'axe du coup, à 19 m de la balle de l'arrêt 2
G1_BALL3 = (16.0, 0.0)  # où la balle s'arrête : à 3 m du trou
G1_SUN = 160.0  # le soleil du matin, derrière la balle : à contre-jour pour les deux vues, et l'ombre du joueur loin de la balle


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
    return Turf([COLLAR, green.but('GreenA', mow=angle, spread=1.25, tone=1.06), green.but('GreenB', mow=angle + math.pi, spread=1.25, tone=0.94)], which, scale)


def place_green1(pin=False):
    """Le green du 1, la même matinée que le départ et le fairway : ciel, sol, trou, drapeau si `pin`
    (il est retiré pour l'approche roulée et le putt). Renvoie le gazon à planter et le drapeau."""
    sky_at('spruit_sunrise', sun=opt('sun', G1_SUN), backdrop=opt('backdrop', 1.0), mist=MIST)
    look(-0.7, MORNING)
    P.lawn(LAWN, FAR_MIST, haze=(40, 240), hole=(*G1_HOLE, P.CUP_R), disc=(*G1_C, G1_R, (0.045, 0.165, 0.050)), specular=0.0)
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
    """Derrière le trou, bas, à peine décalée de la ligne du putt : le trou en amorce au premier plan,
    juste à gauche de l'aplomb de la balle, la balle nette trois mètres plus loin, et au-dessus du
    green la bande des arbres dans la brume. Le diaphragme reste fermé : vu si bas, le trou n'est
    qu'une ellipse très plate, qu'un flou plus fort effacerait."""
    pos = V((G1_HOLE[0] + opt('back', 3.0), opt('side', 0.07), opt('height', 0.17)))
    lens = opt('lens', 250)
    return View(pos, aim(pos, B3, lens, 0.62, opt('fy', 0.45)), lens, opt('fstop', 20.0), B3)


def stop_2(pin=False, place=None):
    """Bord du green du 1 : la balle dans l'herbe de l'avant-green, à deux doigts du green, la face du
    wedge derrière elle. Vue trois quarts avant, depuis le green, au ras de l'herbe : le tapis ras au
    premier plan, la lisière nette juste devant la balle, puis l'herbe plus haute où elle repose."""
    turf, flag = place or place_green1(pin)
    centre = B2
    b = P.ball(centre, stamp=STAMP)
    club = C.iron(kind='wedge')
    C.address(club, centre, gap=0.004, lift=0.004)

    view = view_2()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    face_stamp(b, cam_pos, turn=8, roll=-6)

    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (1_100_000, 0.1, 10.0, 22, 1.0), [((0.12, -0.12), 0.8, 400_000)])
    turf.grow(outside(xy, G1_HOLE, P.CUP_R + 0.001), obstacles)
    # La rosée tient sur l'herbe haute ; sur le green, rasé du matin, il n'en reste presque rien.
    turf.dew((0.1, -0.1), 0.9, opt('dew', 0.03), focus=centre, only=(0,), camera=cam_pos)
    turf.dew((0.0, 0.0), 3.5, opt('dew', 0.03) * 0.3, size=(0.0008, 0.0018), seed=4, only=(0,), focus=centre, camera=cam_pos)
    if opt('greendew', 0.004):
        turf.dew((0.3, -0.3), 1.2, opt('greendew', 0.004), size=(0.0004, 0.0008), seed=6, only=(1, 2))
    P.bloom()
    return Stage(view, id=IDS[2], cam=cam, ball=b, ball_pos=centre, club=club, hole=G1_HOLE, flag=flag, turf=turf, obstacles=obstacles)


def stop_3(pin=False, place=None, ball=None):
    """Sur le green du 1, à 3 m du trou. De derrière le trou, bas, au téléobjectif : le trou en amorce
    au premier plan, la balle nette trois mètres plus loin, la face du putter derrière elle, et la
    lumière du matin qui vient de face : elle fait briller le green et allonge les ombres vers nous.
    `place` : le lieu s'il est déjà posé ; `ball` : la balle si elle existe déjà (un trajet l'amène)."""
    turf, flag = place or place_green1(pin)
    centre = B3
    view = view_3()
    cam = shoot(view)
    cam_pos, target = view.pos, view.target
    b = ball or P.ball(centre, stamp=STAMP)
    turn = face_stamp(None if ball else b, cam_pos, turn=6, roll=4, at=centre)
    club = C.putter()
    C.address(club, centre, gap=0.004, lift=0.0012)

    obstacles = [ball_obstacle(centre), club_obstacle(club)]
    xy = spread(cam_pos, target, (int(opt('blades', 1_800_000)), 2.2, 16.0, 6.0, 0.6), [(G1_BALL3, 0.5, 300_000), (G1_HOLE, 0.4, 200_000)], back=0.0)
    turf.grow(outside(xy, G1_HOLE, P.CUP_R + 0.001), obstacles, seed=7)
    # Au-delà, jusqu'à la brume : peu de brins suffisent, vus si rasants, pour que le sol nu ne se voie pas.
    turf.grow(spread(cam_pos, target, (int(opt('far', 800_000)), 9.0, 75.0, 5.0, 0.0), back=0.0, seed=21), seed=8)
    if opt('dew3', 0.0):
        turf.dew(G1_BALL3, 1.2, opt('dew3', 0.0), size=(0.0003, 0.0008), only=(1, 2))
    P.bloom()
    return Stage(view, id=IDS[3], cam=cam, ball=b, ball_pos=centre, ball_turn=turn, club=club, hole=G1_HOLE, flag=flag, turf=turf, obstacles=obstacles)


# ---------------------------------------------------------------- arrêt 4 : le départ du 2, au bord de l'eau
# L'eau n'est pas modélisée : c'est le lac photographié du panorama, que le sol du départ laisse voir
# au-delà de sa rive. Le coup part vers +X et survole l'eau en biais.
T2_VIEW = 50.0  # azimut du regard (degrés) : de derrière la balle, côté pointe ; le joueur reste hors du cadre, à gauche ; la rive est perpendiculaire au regard
T2_EDGE = 1.7  # distance de la balle à la rive, le long du regard
T2_SUN = T2_VIEW - 4.8  # le soleil est au-dessus du cadre, à droite : son reflet descend dans l'eau


B4 = V((0, 0, 0.019 + P.BALL_R))  # sur un tee bas, comme pour un fer : la coupelle dépasse à peine de l'herbe


def view_4():
    """Trois quarts arrière, côté pointe, un peu au-dessus du fer : son dos, la balle qui dépasse à sa
    droite, puis la rive, le lac et l'autre rive (c'est ce qu'un téléphone garde du cadre)."""
    pos = around(B4, opt('view', T2_VIEW) + 180, opt('dist', 1.2), opt('height', 0.19))
    lens = opt('lens', 105)
    return View(pos, aim(pos, B4, lens, 0.63, opt('fy', 0.62)), lens, opt('fstop', 5.6), B4)


def stop_4():
    """Départ du 2, un par 3 au-dessus de l'eau, en fin d'après-midi : la balle sur un tee bas, le fer 7
    derrière elle. Vue de trois quarts arrière : le dos du fer, la balle, puis le lac et l'autre rive."""
    view, edge = opt('view', T2_VIEW), opt('edge', T2_EDGE)
    phi = math.radians(view)
    # Le panorama est en miroir : entre deux arbres morts plantés dans l'eau, le cadre ne garde que le
    # lac, la colline d'en face et le reflet du soleil. On pose pour le ciel : il est assombri à l'image.
    sky_at('lakeside_sunrise', sun=view - opt('sun', T2_VIEW - T2_SUN), backdrop=opt('backdrop', 0.45), mirror=True)
    look(-1.1, EVENING)
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
    P.lawn(LAWN, (0.20, 0.21, 0.10), bounds=(-450, edge, -450, 450)).rotation_euler = (0, 0, phi)

    turf = Turf([TEE.but('Depart2', straw=opt('straw', 0.02), tall=0.008)])
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
    look(-0.7, EVENING)
    P.lawn(LAWN, (0.22, 0.20, 0.09), hole=(*G2_HOLE, P.CUP_R), disc=(*G2_C, G2_R, (0.024, 0.085, 0.026)), specular=0.2)
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
    """Plongée sur le trou, d'un mètre, penchée de 40° : on voit la paroi du fond, sa bande de terre au
    soleil, la balle contre elle, et le gazon se floute franchement devant et derrière. Le godet entier
    tient dans la bande que garde un téléphone."""
    tilt, dist = math.radians(opt('tilt', 40)), opt('dist', 1.0)
    pos = V((G2_HOLE[0] - dist * math.sin(tilt) * math.cos(G2_UP), G2_HOLE[1] - dist * math.sin(tilt) * math.sin(G2_UP), dist * math.cos(tilt)))
    return View(pos, aim(pos, B6, 85, 0.62, opt('fy', 0.47)), 85, opt('fstop', 2.8), B6 + V((0, 0, P.BALL_R)))


def stop_5(pin=False, place=None):
    """Green du 2, à 1,5 m du trou, à l'heure dorée : la balle, la face fraisée du putter derrière elle.
    Vue trois quarts avant, au ras du green ; le soleil bas vient de la droite et allonge les ombres.
    Le trou est à droite, hors du cadre : c'est le trajet qui y mène. `place` : le lieu s'il est déjà posé."""
    turf, flag = place or place_green2(pin)
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


def stop_6(pin=False, place=None, ball=None, clear=None):
    """Le contact : la balle au fond du trou du 2. Vue plongeante : le godet blanc, la bande de terre
    au soleil, le bord de gazon ras dans la lumière dorée. `place` : le lieu s'il est déjà posé ;
    `ball` : la balle si elle existe déjà (le dernier putt l'amène) ; `clear` : le cadrage d'un autre
    arrêt du même lieu, dont le champ est laissé tel qu'il l'a planté."""
    turf, flag = place or place_green2(pin)
    up = G2_UP
    hx, hy = G2_HOLE
    centre = B6
    b = ball or P.ball(centre, stamp=STAMP)
    # Le soleil rasant n'entre pas dans le trou : le godet n'est éclairé que par le ciel, bleu. On pose
    # pour lui, et on réchauffe la balance des blancs, comme le ferait un photographe à l'ombre.
    look(1.4, 8500.0)

    view = view_6()
    cam = shoot(view)
    cam_pos = view.pos
    turn = face_stamp(None if ball else b, cam_pos, up=(math.cos(up), math.sin(up), 0), turn=0, roll=-9, at=centre)

    obstacles = []
    xy = spread(cam_pos, V((hx, hy, 0)) + V((math.cos(up), math.sin(up), 0)), (160_000, 0.1, 2.6, 180, 1.0), [(G2_HOLE, 0.65, 1_700_000)], back=0.0)
    if clear is not None:
        xy = beside(xy, clear, 21)
    turf.grow(outside(xy, G2_HOLE, P.CUP_R + 0.0008), obstacles)
    P.bloom()
    return Stage(view, id=IDS[6], cam=cam, ball=b, ball_pos=centre, ball_turn=turn, hole=G2_HOLE, flag=flag, turf=turf, obstacles=obstacles)


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
    if args.view:
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
# prise sans coupe ; un raccord entre deux lieux = deux plans (dans le blanc du ciel, ou dans le noir du
# trou). La fonction d'un plan reçoit ses deux numéros d'image, construit sa scène à partir d'un arrêt
# (stop_N) et pose ses clés avec render/strike.py (K) : voir tee_shot, fairway_shot, arrive,
# chip_and_run, birdie_putt et last_putt plus bas.
#
# Règles communes :
#   - la première image d'un trajet est la vue de son arrêt de départ, la dernière celle de l'arrêt
#     d'arrivée (la page enchaîne sur l'image nette par un fondu) : rien ne bouge pendant la première
#     demi-image, et tout est posé avant la dernière ;
#   - la caméra suit la balle, gardée vers x = 0,62 (aim) ; à l'arrivée elle reste à la place de l'arrêt,
#     et vise la place de la balle au sol : ce sont ses rebonds qui bougent dans l'image, pas le décor ;
#   - le club du coup suivant n'est pas là quand la balle arrive : il vient se poser derrière elle
#     (K.settle), une fois qu'elle est arrêtée ;
#   - l'herbe d'un arrêt n'est plantée que dans son cadre : on replante là où la caméra regarde
#     pendant le mouvement, hors du secteur de l'arrêt (beside), pour que la dernière image reste la sienne ;
#   - CUES[k] : l'image de l'impact et celle où la balle touche le sol (pour un putt : celle où elle
#     tombe dans le trou), portées dans anchors.json ("legs") puis dans le manifeste par
#     scripts/frames.py : le compteur de distance du site s'y cale.
# Animatique : --leg N --scale 25 --samples 10 --set density=0.35 --out render/out/anim
LEG_FRAMES = 44
CUES = {
    0: {'impact': 10, 'land': 30},
    1: {'impact': 11, 'land': 31},
    2: {'impact': 10, 'land': 20},
    3: {'impact': 8, 'land': 19},
    4: {'impact': 11, 'land': 31},
    5: {'impact': 8, 'land': 22},
}


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
    cam.data.dof.focus_distance = (view.focus - view.pos).length - NEAR
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


def beside(xy, view, half, back=0.25):
    """Garde les points (N,2) hors du secteur qu'un arrêt a déjà planté devant son cadrage `view`
    (demi-angle `half` en degrés, sommet à `back` mètres derrière la caméra, comme spread)."""
    d = view.target - view.pos
    d.z = 0
    d.normalize()
    o = view.pos - d * back
    az = np.arctan2(xy[:, 1] - o.y, xy[:, 0] - o.x) - math.atan2(d.y, d.x)
    return xy[np.abs((az + np.pi) % (2 * np.pi) - np.pi) > math.radians(half)]


def save_cues():
    """Porte CUES dans anchors.json, sous "legs"."""
    data = {}
    if os.path.exists(ANCHORS):
        with open(ANCHORS, encoding='utf8') as fh:
            data = json.load(fh)
    data['legs'] = {str(k): v for k, v in sorted(CUES.items())}
    with open(ANCHORS, 'w', encoding='utf8') as fh:
        json.dump(dict(sorted(data.items())), fh, indent=1)


# ---- trajet 0 → 1 : le bois 3 depuis le tee
def tee_shot(first, last):
    """Plan 1 : la frappe au bois 3, au ralenti, de la vue de l'arrêt 0, caméra fixe. Le club recule
    hors champ, revient, la balle s'écrase et part vers nous, le tee saute. Coupe franche ensuite."""
    a = stop_0()
    K.setup()
    clock = K.Clock(CUES[0]['impact'], slow=0.105 / K.CLUBS['bois3']['speed'])
    K.swing(a.club, 'bois3', clock, first=first, reach=0.020, last=last)
    K.launch(K.Ball(a.ball), K.Flight.of('bois3', B0), clock, first=first, last=last)
    K.burst([a.tee], B0, clock, last, speed=(6.0, 8.0), lift=(35, 50), fan=8, tumble=70, hidden=False)


def wide_finish(first, last):
    """Plan 2 : Antoine de dos au finish, en silhouette (render/finish.py) ; la trace ambre de la balle
    se dessine dans le ciel jusqu'à la coupe, dans un cadre presque fixe, et le plan finit dans le blanc
    en deux images. L'image est développée comme l'image validée (le contraste posé par reset) : ses
    noirs restent des noirs. Mesuré sur render/out/test/finish.png : elle a été posée à −1,35 (à −0,6,
    le réglage par défaut de finish.py, les cuisses et la colline sont une fois et demie trop claires)."""
    F.build(F.options(['--rot', '324', '--turn', str(opt('turn', 2.0)), '--halo', str(opt('halo', 0.18)), '--glow', str(opt('glow', 2.4)), '--exposure', str(opt('ev', -1.35))]), shot=(first, last))  # le ciel de l'image validée


def arrive(stage, first, land, stop, last, lie, fall, hops, run, settle=None, burn=2.2, wide=45.0, high=0.28, pin=None):
    """Plan d'arrivée d'un coup long, dans la scène de l'arrêt `stage` : on sort du blanc du ciel, la
    balle en descend, touche le sol à l'image `land`, rebondit, roule et s'arrête à l'image `stop`, là
    où l'arrêt la montre. La caméra ne quitte pas la place de l'arrêt et attend la balle plus qu'elle
    ne la suit : elle ouvre son champ (focale `wide` à la première image, celle de l'arrêt une image
    avant `stop`), la balle descend dans l'image pendant sa chute (de `high` hauteur d'image), et dès
    qu'elle a touché le sol c'est sa place au sol qui est visée : le sol reste stable, la balle saute
    dans l'image, ses rebonds se lisent. Au premier impact, une gerbe de rosée. Puis le club du coup
    suivant (angle de lie `lie`) vient se poser derrière la balle. fall, hops, run : voir K.arrival.
    `pin` : (x, y) d'un point à garder dans le champ pendant la chute (le drapeau), ou None."""
    view, cam = stage.view, stage.cam
    fx, fy = focus_of(cam, stage.ball_pos)
    rest = V(stage.ball_pos)
    frames, pts = K.arrival(rest, first, land, stop, fall=fall, hops=hops, run=run, last=last)
    down = pts[frames.index(land)]  # où elle touche le sol
    # L'herbe du côté d'où vient la balle : la caméra, au grand-angle, la regarde arriver avant de
    # revenir sur son cadrage.
    xy = beside(spread(view.pos, down, (1_000_000, 0.1, 14.0, 50, 1.0), seed=31), view, 21)
    stage.turf.grow(outside(xy, stage.hole, P.CUP_R + 0.001) if stage.hole else xy, stage.obstacles, seed=33)
    K.setup()
    ball = K.Ball(stage.ball)
    for f, p in zip(frames, pts):
        ball.key(f, p)
    ball.roll(frames, pts, ball.rest)
    target, lens, focus = [], [], []
    for f, p in zip(frames, pts):
        mm = math.exp(math.log(wide) + (math.log(view.lens) - math.log(wide)) * float(K.smooth((f - first) / (stop - 1.0 - first))))
        if f <= land:
            t = aim(view.pos, p, mm, fx, fy - high * (1.0 - float(K.smooth((f - first) / (land - first)))))
        else:
            t = aim(view.pos, V((p.x, p.y, rest.z)), mm, fx, fy)
        target.append(t.lerp(view.target, float(K.smooth((f - (stop - 1.0)) / 1.0))))
        lens.append(mm)
        focus.append(min((p - view.pos).length, 80.0))
    K.track(cam, frames, [view.pos] * len(frames), target, lens=lens, focus=focus)
    K.settle(stage.club, settle if settle is not None else math.ceil(stop) - 2, last, lie)
    key_look(first, stage.exposure + burn, stage.warmth)
    key_look(first + 3, stage.exposure, stage.warmth)
    # La gerbe de rosée du premier impact, en temps réel (une image = 1/27 s).
    real = K.Clock(land, slow=1.0 / 27.0, before=1.0, after=1.0)
    K.burst(K.spray(22, SUN['dir']), V((down.x, down.y, 0.01)), real, min(last, land + 12), speed=(2.0, 5.0), lift=(40, 70), fan=70, scatter=0.03, tumble=0.0, seed=9)
    # La trace ambre du plan précédent se poursuit : si loin, la balle n'est qu'un point gris dans le
    # ciel. Elle la suit jusqu'au sol, un tiers d'image derrière elle (pendant la pose, le trait ne
    # dépasse jamais la balle), puis s'efface en trois images.
    trace = K.Trace(K.Path(frames, pts), view.pos, lens=wide, span=(first, land), strength=K.amber(stage.exposure), tail=3.0, width=0.0012, colour=K.AMBER, steps=60, dot=False)
    for f in frames:
        trace.key(f, f - 0.35)
        trace.glow(f, K.amber(stage.exposure + burn * max(0.0, 1.0 - (f - first) / 3.0)))


def fairway_arrival(first, last):
    """Plan 3 : la balle retombe sur le fairway, fait deux rebonds qui se lisent, roule et s'arrête ;
    le fer long vient se poser derrière elle."""
    arrive(stop_1(), first, CUES[0]['land'], 39.5, last, 60.5, fall=(0.85, 0.70), hops=((3.5, 3.0, 0.40), (2.5, 1.2, 0.10)), run=1.5, settle=39)


# ---- trajet 1 → 2 : le fer long vers le green
def fairway_shot(first, last):
    """Plan 1 : la frappe au fer long, de la vue de l'arrêt 1. La tête descend encore à l'impact : elle
    prend la balle, puis l'herbe, et la motte s'envole avec ses miettes. La caméra se retourne d'un
    fouetté pour suivre la balle, qui file vers le ciel en trace ambre, et le plan finit dans le blanc."""
    a = stop_1()
    view = a.view
    # Un peu d'herbe du côté de la cible, que le fouetté balaie.
    a.turf.grow(beside(spread(view.pos, V((6, 0, 0)), (300_000, 0.1, 9.0, 60, 1.0), seed=41), view, 21), a.obstacles, seed=43)
    K.setup()
    impact = CUES[1]['impact']
    clock = K.Clock(impact, slow=0.095 / K.CLUBS['long']['speed'], cap=0.22)  # au plus 0,22 s de vol par image : la balle monte encore à la fin du plan
    K.swing(a.club, 'long', clock, first=first, reach=0.010, last=impact + 3)
    fly = K.Flight.of('long', B1)
    where = K.launch(K.Ball(a.ball), fly, clock, first=first, last=last, step=0.25)
    turf = a.turf.kinds[0].material()
    spot = V((0.055, 0.0, 0.0))  # la tête touche le sol juste après la balle
    K.burst([K.divot(turf)], spot + V((0.03, 0, 0)), clock, last, speed=(7.5, 9.0), lift=(30, 38), fan=6, scatter=0.0, tumble=22, seed=2)
    K.burst(K.crumbs(26), spot, clock, last, speed=(4, 13), lift=(18, 62), fan=30, scatter=0.03, tumble=60, seed=3)
    K.burst(K.loose_blades(34, turf), spot, clock, last, speed=(3, 10), lift=(25, 70), fan=38, scatter=0.035, tumble=50, seed=4)
    # La caméra reste où elle est et se tourne : en deux images elle a rattrapé la balle, puis la tient
    # au même point de l'image (celui où le plan d'arrivée la reprend). La motte reste dans le cadre le
    # temps de la voir partir. La balle passe à 70 cm de l'objectif : une clé par quart d'image, sans
    # quoi la visée la quitte pendant la pose et elle bave en tache.
    frames = K.half_frames(first, last, step=0.25)
    fx, fy = focus_of(a.cam, B1)
    target, focus = [], []
    for f in frames:
        w, p = float(K.smooth((f - impact) / 2.0)), V(where[f])
        target.append(view.target.lerp(aim(view.pos, p, view.lens, fx + (0.62 - fx) * w, fy + (0.60 - fy) * w), w))
        focus.append((p - view.pos).length)
    K.track(a.cam, frames, [view.pos] * len(frames), target, focus=focus)
    # La trace ambre : au loin la balle n'est plus qu'un point, c'est elle qu'on suit. Le plan finit dans
    # le blanc du ciel ; la trace baisse d'autant pour rester ambre pendant que le ciel blanchit.
    burn = 2.2
    trace = K.Trace(fly, view.pos, lens=view.lens, span=(0.03, 3.4), strength=K.amber(a.exposure), tail=0.9, width=0.0017, colour=K.AMBER)
    for f in frames:
        trace.key(f, max(0.0, clock.at(f)))
        trace.glow(f, K.amber(a.exposure + burn * min(1.0, max(0.0, (f - (last - 4)) / 4.0))))
    key_look(last - 4, a.exposure, a.warmth)
    key_look(last, a.exposure + burn, a.warmth)


def green_arrival(first, last):
    """Plan 2 : la balle retombe devant le green du 1, rebondit et s'arrête dans l'avant-green, à deux
    doigts du green ; le wedge vient se poser derrière elle."""
    arrive(stop_2(), first, CUES[1]['land'], 39.0, last, 64.0, fall=(1.0, 1.05), hops=((2.0, 2.0, 0.45), (1.5, 0.9, 0.10)), run=1.2, settle=38)


# ---- trajet 2 → 3 : l'approche roulée, sans coupe
def chip_and_run(first, last):
    """Un seul plan sur le green du 1 : le wedge fait sauter la balle, elle vole six mètres, retombe sur
    le green, roule et s'arrête à trois mètres du trou. La caméra recule devant elle au ras du sol,
    passe au-dessus du trou et finit sur le cadrage de l'arrêt 3 ; le putter vient se poser."""
    place = place_green1()
    a = stop_2(place=place)
    fya = focus_of(a.cam, B2)[1]
    b = stop_3(place=place, ball=a.ball)
    fyb = focus_of(b.cam, B3)[1]
    bpy.data.objects.remove(a.cam)
    cam, va, vb = b.cam, a.view, b.view
    impact, land, stop = CUES[2]['impact'], CUES[2]['land'], 40
    # L'herbe du couloir, entre les deux cadrages : la caméra y passe vite, peu de brins suffisent.
    rng = np.random.default_rng(51)
    n = int(1_100_000 * DENSITY)
    xy = np.stack([-2.5 + 25.5 * rng.random(n), -2.6 + 4.2 * rng.random(n)], axis=1)
    place[0].grow(outside(beside(beside(xy, va, 22), vb, 6, back=0.0), G1_HOLE, P.CUP_R + 0.001), seed=53)
    K.setup()
    clock = K.Clock(impact, slow=0.060 / K.CLUBS['wedge']['speed'], before=1.25, after=1.9, cap=0.118)
    K.swing(a.club, 'wedge', clock, first=first, back=4, reach=0.0125, last=impact + 5)
    ball = K.Ball(a.ball)
    fly = K.Flight.of('wedge', B2, draw=(0.0, 0.0))
    where = K.launch(ball, fly, clock, first=first, last=land)
    hop = (1.5, 1.35, 0.08)
    frames2, pts2 = K.arrival(B3, land, land, stop, hops=(hop,), run=B3.x - hop[1] - float(fly.at(clock.at(land))[0]), last=last)
    where.update(zip(frames2, pts2))
    for f, p in zip(frames2, pts2):
        ball.key(f, p)
    rolling = K.half_frames(impact + 0.5, last)
    ball.roll(rolling, [where[f] for f in rolling], b.ball_turn)
    K.burst(K.loose_blades(14, a.turf.kinds[0].material()), V((0.03, 0, 0)), clock, land, speed=(1.2, 3.5), lift=(30, 70), fan=30, tumble=25, seed=5)
    K.settle(b.club, stop, last, 70.0)
    # La caméra : devant la balle, de plus en plus loin devant ; quand la balle vole, elle monte plus
    # qu'elle et la regarde d'un peu au-dessus (huit degrés), pour la garder sur le vert du green : le
    # soleil est bas, juste derrière, et une balle blanche devant lui se dissout dans son halo. Elle
    # la tient toujours au même point de l'image.
    frames = K.half_frames(first, last)
    pts = [V(where[f]) for f in frames]
    soft = K.follow(pts, B2, weight=0.6)
    ahead = vb.pos.x - B3.x - va.pos.x  # ce dont la caméra s'éloigne de la balle, d'un cadrage à l'autre
    pos, target, lens, focus, fstop = [], [], [], [], []
    for k, f in enumerate(frames):
        g = float(K.smooth((f - impact - 0.5) / (42.5 - impact)))
        early = 2.2 * float(K.smooth((f - impact) / 6.0))
        p = V((soft[k].x + va.pos.x + early + (ahead - 2.2) * g, va.pos.y + (vb.pos.y - va.pos.y) * g, va.pos.z + (vb.pos.z - va.pos.z) * g + opt('lift', 1.45) * max(0.0, soft[k].z - B2.z)))
        p = p.lerp(vb.pos, float(K.smooth((f - 38) / 5.0)))
        mm = math.exp(math.log(va.lens) + (math.log(vb.lens) - math.log(va.lens)) * g)
        w = float(K.smooth((f - impact) / 1.5))
        pos.append(p)
        lens.append(mm)
        fstop.append(math.exp(math.log(va.fstop) + (math.log(vb.fstop) - math.log(va.fstop)) * g))
        target.append(vb.target if f >= 43 else va.target.lerp(aim(p, pts[k], mm, 0.62, fya + (fyb - fya) * g), w))
        focus.append((pts[k] - p).length)
    K.track(cam, frames, pos, target, lens=lens, focus=focus, fstop=fstop)


# ---- trajet 3 → 4 : le putt pour birdie, le noir du trou, puis le départ du 2
def putter_clock(impact):
    """Le temps d'un putt : presque le temps réel à l'impact (une image = 0,04 s), la descente du
    putter raccordée à la fin de son recul, et une fin de geste qui se pose sans hâte."""
    return K.Clock(impact, slow=0.04, before=1.7, after=1.2)


def bezier(points, u):
    """Un point d'une courbe de Bézier à quatre points de contrôle."""
    a, b, c, d = points
    return a * (1 - u) ** 3 + b * (3 * u * (1 - u) ** 2) + c * (3 * u * u * (1 - u)) + d * u**3


def birdie_putt(first, last):
    """Plan 1 : le putt de 3 m, de la vue de l'arrêt 3, derrière le trou. Le putter frappe, la balle
    vient vers nous sur une ligne un peu courbe, bascule par-dessus le bord du trou et tombe. La caméra
    ne bouge pas tant que la balle roule : elle s'incline à peine, pour remonter le trou dans l'image ;
    puis elle fonce sur lui, plonge dans le godet, et le plan finit dans le noir."""
    a = stop_3()
    view, cam = a.view, a.cam
    impact, land = CUES[3]['impact'], CUES[3]['land']
    hole = V((G1_HOLE[0], G1_HOLE[1], 0.0))
    # L'herbe autour du trou, hors du couloir étroit que voit le téléobjectif : la plongée la découvre.
    xy = beside(spread(view.pos, hole, (500_000, 1.2, 9.0, 28, 0.6), seed=61), view, 6, back=0.0)
    a.turf.grow(outside(xy, G1_HOLE, P.CUP_R + 0.001), a.obstacles, seed=63)
    K.setup()
    # Le putter reste en fin de geste : le joueur regarde sa balle rouler.
    K.swing(a.club, 'putter', putter_clock(impact), first=first, back=4, reach=0.004, finish=0.22, last=impact + 10, leave=False, soft=True)
    where = K.putt(K.Ball(a.ball), G1_HOLE, impact, land, first=first, last=last, bow=opt('bow', -0.05))
    frames = K.half_frames(first, last)
    dive = land + 1.5  # la balle bascule et tombe sous nos yeux, puis la caméra part
    low = aim(view.pos, hole, view.lens, 0.62, 0.64)
    path = [view.pos, V((hole.x + 1.3, 0.03, 0.42)), V((hole.x + 0.10, 0.0, 0.34)), V((hole.x + 0.02, 0.0, -0.03))]
    bottom = V((hole.x, hole.y, -P.CUP_DEPTH))
    pos, target, lens, focus = [], [], [], []
    for f in frames:
        g = float(K.smooth((f - impact - 1) / (land - impact - 1)))
        u = min(1.0, max(0.0, (f - dive) / (last - dive)))
        e = u**1.3  # de plus en plus vite : on ne freine pas, on entre dans le noir
        p = bezier(path, e)
        # Elle vise le trou, et son fond seulement quand elle y entre.
        t = view.target.lerp(low, g).lerp(hole + (bottom - hole) * float(K.smooth((u - 0.85) / 0.15)), float(K.smooth(2.0 * u)))
        pos.append(p)
        target.append(t)
        lens.append(math.exp(math.log(view.lens) + (math.log(30.0) - math.log(view.lens)) * e))
        focus.append((V(where[f]) - p).length if f < dive else max(0.05, (t - p).length))
    K.track(cam, frames, pos, target, lens=lens, focus=focus)
    key_look(first, a.exposure, a.warmth)
    key_look(last - 2, a.exposure, a.warmth)
    key_look(last - 1, a.exposure - 1.0, a.warmth)
    key_look(last, a.exposure - 14.0, a.warmth)


def tee2_descent(first, last):
    """Plan 2 : on sort du noir dans le ciel de fin d'après-midi, au-dessus du lac ; la caméra descend,
    bascule vers le sol et se pose sur le cadrage de l'arrêt 4, derrière la balle du par 3. Le fer 7
    vient se placer derrière elle."""
    a = stop_4()
    view, cam = a.view, a.cam
    phi, edge = math.radians(opt('view', T2_VIEW)), opt('edge', T2_EDGE)
    d = view.target - view.pos
    flat = V((d.x, d.y, 0)).normalized()
    pitch1 = math.atan2(d.z, math.hypot(d.x, d.y))
    back, up, pitch0, lens0 = opt('back', 2.4), opt('up', 1.5), math.radians(opt('pitch', 24)), opt('lens0', 40.0)
    done = last - 4  # posée : il reste au fer le temps d'arriver
    # L'herbe du départ vue d'en haut, autour du secteur que l'arrêt a planté, jusqu'à la rive.
    high = view.pos - flat * back + V((0, 0, up))
    xy = beside(spread(high, B4, (700_000, 0.3, 9.0, 34, 0.6), seed=65), view, 22)
    xy = xy[xy[:, 0] * math.cos(phi) + xy[:, 1] * math.sin(phi) < edge - 0.01]
    a.turf.grow(outside(xy, (0, 0), 0.006), a.obstacles, seed=67)
    K.setup()
    frames = K.half_frames(first, last)
    pos, target, lens, focus = [], [], [], []
    for f in frames:
        u = (f - first) / (done - first)
        e = float(K.ease_out(u, 2.4))  # déjà lancée en sortant du noir, elle freine en se posant
        p = view.pos - flat * (back * (1 - e)) + V((0, 0, up * (1 - e)))
        mm = math.exp(math.log(lens0) + (math.log(view.lens) - math.log(lens0)) * e)
        # La visée : le même azimut que l'arrêt (la balle reste vers x = 0,63), le regard qui bascule du ciel au sol.
        b = B4 - p
        az = math.atan2(b.y, b.x) + math.atan((0.63 - 0.5) * 36.0 / mm)
        el = pitch1 + (pitch0 - pitch1) * (1 - float(K.ease_out(u, 2.0)))
        t = p + V((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el))) * d.length
        t = t.lerp(view.target, float(K.smooth((f - (done - 4)) / 4.0)))
        pos.append(p)
        target.append(t)
        lens.append(mm)
        focus.append((B4 - p).length)
    K.track(cam, frames, pos, target, lens=lens, focus=focus)
    K.settle(a.club, done - 1, last, 62.5, reach=3.2)
    key_look(first, a.exposure - 9.0, a.warmth)
    key_look(first + 1, a.exposure - 1.5, a.warmth)
    key_look(first + 3, a.exposure, a.warmth)


# ---- trajet 4 → 5 : le fer 7 au-dessus de l'eau
def par3_shot(first, last):
    """Plan 1 : la frappe au fer 7, de la vue de l'arrêt 4, derrière la balle. La tête la prend sur son
    tee bas, puis frôle l'herbe : le tee saute, quelques brins volent. La caméra se tourne vers la
    cible et suit la balle qui monte au-dessus de l'eau, en trace ambre ; le plan finit dans le ciel."""
    a = stop_4()
    view = a.view
    phi, edge = math.radians(opt('view', T2_VIEW)), opt('edge', T2_EDGE)
    # L'herbe du côté de la cible, jusqu'à la rive : la caméra la balaie en se tournant.
    xy = beside(spread(view.pos, V((6, 0, 0)), (300_000, 0.1, 9.0, 60, 1.0), seed=81), view, 22)
    xy = xy[xy[:, 0] * math.cos(phi) + xy[:, 1] * math.sin(phi) < edge - 0.01]
    a.turf.grow(outside(xy, (0, 0), 0.006), a.obstacles, seed=83)
    K.setup()
    impact = CUES[4]['impact']
    clock = K.Clock(impact, slow=0.095 / K.CLUBS['fer7']['speed'], cap=0.22)
    K.swing(a.club, 'fer7', clock, first=first, reach=0.010, last=impact + 2)  # il disparaît dans le filé : le champ qui s'ouvre le reprendrait
    fly = K.Flight.of('fer7', B4)
    where = K.launch(K.Ball(a.ball), fly, clock, first=first, last=last, step=0.25)
    turf = a.turf.kinds[0].material()
    K.burst([a.tee], B4, clock, last, speed=(5.0, 7.0), lift=(40, 55), fan=8, tumble=70, hidden=False)
    K.burst(K.loose_blades(22, turf), V((0.05, 0, 0)), clock, last, speed=(3, 9), lift=(25, 65), fan=32, scatter=0.03, tumble=50, seed=4)
    # La caméra reste où elle est et se tourne : elle rattrape la balle en deux images, puis la tient
    # dans le haut de l'image en ouvrant son champ (du 105 au 32 mm), pour garder sous elle la rive
    # d'en face et le lac qu'elle survole.
    frames = K.half_frames(first, last, step=0.25)
    fx, fy = focus_of(a.cam, B4)
    wide, high = opt('wide', 32.0), opt('high', 0.32)
    target, focus, lens = [], [], []
    for f in frames:
        w, z, p = float(K.smooth((f - impact) / 2.0)), float(K.smooth((f - impact - 0.5) / 5.0)), V(where[f])
        mm = math.exp(math.log(view.lens) + (math.log(wide) - math.log(view.lens)) * z)
        target.append(view.target.lerp(aim(view.pos, p, mm, fx + (0.62 - fx) * w, fy + (high - fy) * z), w))
        focus.append((p - view.pos).length)
        lens.append(mm)
    K.track(a.cam, frames, [view.pos] * len(frames), target, lens=lens, focus=focus)
    # La trace ambre, vue de derrière : elle monte dans le ciel du soir, et baisse d'autant quand le
    # plan blanchit.
    burn = 2.0
    trace = K.Trace(fly, view.pos, lens=wide, span=(0.03, 3.4), strength=K.amber(a.exposure), tail=1.4, width=0.0017, colour=K.AMBER)
    for f in frames:
        trace.key(f, max(0.0, clock.at(f)))
        trace.glow(f, K.amber(a.exposure + burn * min(1.0, max(0.0, (f - (last - 4)) / 4.0))))
    key_look(last - 4, a.exposure, a.warmth)
    key_look(last, a.exposure + burn, a.warmth)


def green2_arrival(first, last):
    """Plan 2 : la balle retombe sur le green du 2, de haut, fait un rebond, roule un peu et s'arrête à
    1,5 m du trou ; le putter vient se poser derrière elle."""
    arrive(stop_5(), first, CUES[4]['land'], 38.5, last, 70.0, fall=(0.9, 1.1), hops=((2.0, 1.1, 0.30), (1.2, 0.45, 0.05)), run=0.5, settle=38)


# ---- trajet 5 → 6 : le dernier putt, sans coupe
def last_putt(first, last):
    """Un seul plan sur le green du 2 : le putter frappe, la balle roule un mètre et demi et tombe dans
    le trou. La caméra la devance au ras du green, puis s'élève et vient à l'aplomb du trou, sur le
    cadrage de l'arrêt 6 ; l'image est posée pour l'ombre du godet à mesure qu'elle monte."""
    place = place_green2()
    a = stop_5(place=place)
    fya = focus_of(a.cam, B5)[1]
    b = stop_6(place=place, ball=a.ball, clear=a.view)
    fyb = focus_of(b.cam, B6)[1]
    bpy.data.objects.remove(a.cam)
    cam, va, vb = b.cam, a.view, b.view
    impact, land, up_by = CUES[5]['impact'], CUES[5]['land'], 41
    # L'herbe entre les deux cadrages, et au loin dans le regard de la caméra qui monte. Le disque serré
    # que l'arrêt 6 plante autour du trou est laissé tel quel ; une couronne plus dense le prolonge.
    rng = np.random.default_rng(71)
    n = int(1_400_000 * DENSITY)
    xy = np.stack([-1.6 + 4.6 * rng.random(n), -1.4 + 4.4 * rng.random(n)], axis=1)
    m = int(1_200_000 * DENSITY)
    r, t = np.sqrt(0.65**2 + (1.3**2 - 0.65**2) * rng.random(m)), 2 * math.pi * rng.random(m)
    ring = np.stack([G2_HOLE[0] + r * np.cos(t), G2_HOLE[1] + r * np.sin(t)], axis=1)
    far = spread(V((1.6, -0.55, 0.0)), V((1.6, -0.55, 0.0)) + V((math.cos(math.radians(128)), math.sin(math.radians(128)), 0)), (500_000, 1.5, 12.0, 35, 1.0), seed=75)
    xy = beside(np.concatenate([xy, ring, far]), va, 21)
    place[0].grow(xy[np.hypot(xy[:, 0] - G2_HOLE[0], xy[:, 1] - G2_HOLE[1]) > 0.65], a.obstacles, seed=73)
    K.setup()
    # Le putter quitte la scène dès que la caméra l'a laissé derrière elle.
    K.swing(a.club, 'putter', putter_clock(impact), first=first, back=4, reach=0.004, finish=0.22, last=impact + int(opt('leave', 8)), soft=True)
    where = K.putt(K.Ball(a.ball), G2_HOLE, impact, land, first=first, last=last, bow=opt('bow', 0.012), speeds=(0.055, 0.04), rest=B6, final=b.ball_turn)
    frames = K.half_frames(first, last)
    pts = [V(where[f]) for f in frames]
    # La visée suit la balle à plat, sans retard ; elle ne tombe pas d'un coup avec elle dans le trou,
    # et ne descend au fond du godet qu'à mesure que la caméra s'élève (vu de bas, viser le fond, c'est
    # viser le green en avant du trou).
    depth = K.follow([V((0, 0, p.z)) for p in pts], V((0, 0, B5.z)), weight=0.45)
    pos, target, lens, focus, fstop = [], [], [], [], []
    for k, f in enumerate(frames):
        gxy = float(K.smooth((f - impact) / (land + 4.0 - impact)))  # elle devance la balle
        gz = float(K.smooth((f - (land - 8.0)) / (up_by - (land - 8.0))))  # puis s'élève
        if f >= up_by + 1:
            p, mm, t, fs, fo = vb.pos, vb.lens, vb.target, vb.fstop, (vb.focus - vb.pos).length
        else:
            p = V((va.pos.x + (vb.pos.x - va.pos.x) * gxy, va.pos.y + (vb.pos.y - va.pos.y) * gxy, va.pos.z + (vb.pos.z - va.pos.z) * gz))
            mm = math.exp(math.log(va.lens) + (math.log(vb.lens) - math.log(va.lens)) * gz)
            w = float(K.smooth((f - impact) / 1.5))
            look = V((pts[k].x, pts[k].y, B5.z + (depth[k].z - B5.z) * float(K.smooth((gz - 0.25) / 0.75))))
            t = va.target.lerp(aim(p, look, mm, 0.62, fya + (fyb - fya) * gz), w)
            fs = math.exp(math.log(va.fstop) + (math.log(vb.fstop) - math.log(va.fstop)) * gz)
            fo = (look - p).length + ((vb.focus - vb.pos).length - (B6 - vb.pos).length) * gz
        pos.append(p)
        target.append(t)
        lens.append(mm)
        fstop.append(fs)
        focus.append(fo)
    K.track(cam, frames, pos, target, lens=lens, focus=focus, fstop=fstop)
    # Le développement passe de celui du green au soleil à celui de l'ombre du godet.
    for f in range(first, last + 1):
        g = float(K.smooth((f - land) / (up_by - 1.0 - land)))
        key_look(f, a.exposure + (b.exposure - a.exposure) * g, a.warmth + (b.warmth - a.warmth) * g)


LEGS = [
    [(1, 12, tee_shot), (13, 24, wide_finish), (25, 44, fairway_arrival)],
    [(1, 24, fairway_shot), (25, 44, green_arrival)],
    [(1, 44, chip_and_run)],
    [(1, 26, birdie_putt), (27, 44, tee2_descent)],
    [(1, 23, par3_shot), (24, 44, green2_arrival)],
    [(1, 44, last_putt)],
]


def render_leg(k):
    shots = LEGS[k]
    if not shots:
        raise SystemExit(f'trajet {k} → {k + 1} : pas encore écrit (voir LEGS dans render/scene.py)')
    first, _, last = args.frames.partition('-')
    first = int(first) if first else 1
    last = int(last) if last else (first if args.frames else LEG_FRAMES)
    os.makedirs(OUT, exist_ok=True)
    if k in CUES and not args.name:
        save_cues()
    for start, end, build in shots:
        todo = [n for n in range(max(first, start), min(last, end) + 1) if args.force or not os.path.exists(os.path.join(OUT, f'l{k}_{n:04d}.png'))]
        if not todo:
            continue
        t0 = time.time()
        reset(args.samples or 16)
        scene.render.use_persistent_data = not args.no_persistent  # l'herbe ne bouge pas : son arbre de tri se garde d'une image à l'autre
        scene.render.use_motion_blur = args.shutter is None or args.shutter > 0
        scene.render.motion_blur_shutter = args.shutter or 0.5
        scene.frame_start, scene.frame_end = 1, LEG_FRAMES
        build(start, end)
        if args.blur_steps:
            for o in scene.objects:
                o.cycles.motion_steps = args.blur_steps
        print(f'PLAN {k} images {start}-{end} construction {time.time() - t0:.1f}s')
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
