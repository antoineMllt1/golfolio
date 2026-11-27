# Le plan du finish : Antoine de dos, en silhouette à contre-jour, pendant que la balle s'envole.
# Il n'est pas modélisé : c'est sa photo de practice détourée (render/assets/joueur/finish.png, jamais
# versionnée), posée debout dans la scène comme une figurine plate, face à la caméra et dos au soleil.
# Le décor est un vrai panorama photographié ; seule l'herbe proche est calculée.
#
#   python render/finish.py -- --rot 324 --scale 100 --samples 32 --out render/out/test --name finish
#
# --rot 324 est le ciel de l'image validée par Antoine (render/out/test/finish.png) : la colline dans la
# brume à gauche, le soleil derrière lui. Sans --rot, le soleil est placé par --sun : un autre décor.
#
# Le trajet 0 → 1 du film reprend ce plan en mouvement (render/scene.py, plan « wide_finish ») :
# build(options(), shot=(première image, dernière image)) pose alors la trace qui se dessine jusqu'à
# la coupe, dans un cadre presque fixe. Sans `shot`, l'image fixe validée est inchangée.
#
# Repère : la balle part vers +X, le joueur (droitier) est côté +Y, la caméra est derrière lui (−X).
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parts as P  # noqa: E402
import strike as K  # noqa: E402

V = Vector
ARGS = None  # les réglages du plan : options() par défaut, ou la ligne de commande
CUT = os.path.join(P.ASSETS, 'joueur', 'finish.png')
PX = 1.76 / 1271  # mètres par pixel : la silhouette fait 1271 px de haut pour 1,76 m
HEAD = (0.64, 0.31)  # où la tête de la trace finit dans l'image du plan en mouvement (voir animate)
BURN = 1.8  # surexposition des deux dernières images du plan en mouvement : la coupe se fait dans le blanc


def rim_map(path):
    """Liseré de lumière le long du contour, côté soleil : écrit à côté du détourage, renvoie son chemin."""
    out = path.replace('.png', '_rim.png')
    a = Image.open(path).split()[3]
    inner = a.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.2))
    rim = np.clip(np.asarray(a, dtype=np.float32) - np.asarray(inner, dtype=np.float32), 0, 255) / 255
    # Plus fort en haut et à droite (le soleil est devant lui, un peu à droite de l'image).
    blur = np.asarray(a.filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255
    gy, gx = np.gradient(blur)
    facing = np.clip(-(gx * 0.8 + gy * 0.6) * 16, 0, 1)  # contour tourné vers le haut et la droite
    val = np.clip(rim * facing, 0, 1)
    Image.fromarray((val * 255).astype(np.uint8)).save(out)
    return out


def player(feet_y=0.9):
    """La figurine plate. Le centre du corps est à y = feet_y, les pieds au sol."""
    im = Image.open(CUT)
    w, h = im.size
    left = feet_y + 205 * PX  # le centre du corps est à 205 px du bord gauche de l'image
    y0, y1, z0, z1 = left, left - w * PX, -0.004, h * PX - 0.004
    me = bpy.data.meshes.new('Joueur')
    me.from_pydata([(0, y0, z0), (0, y1, z0), (0, y1, z1), (0, y0, z1)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UV')
    for loop, co in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        loop.uv = co
    o = P.link(bpy.data.objects.new('Joueur', me))
    m = bpy.data.materials.new('Joueur')
    m.use_nodes = True
    nt = m.node_tree
    b = P.bsdf(m)
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = bpy.data.images.load(CUT)
    tex.extension = 'CLIP'
    rim = nt.nodes.new('ShaderNodeTexImage')
    rim.image = bpy.data.images.load(rim_map(CUT))
    rim.image.colorspace_settings.name = 'Non-Color'
    rim.extension = 'CLIP'
    dim = nt.nodes.new('ShaderNodeMix')  # à contre-jour la silhouette est sombre
    dim.data_type = 'RGBA'
    dim.blend_type = 'MULTIPLY'
    dim.inputs['Factor'].default_value = 1.0
    dim.inputs['B'].default_value = (ARGS.dark, ARGS.dark, ARGS.dark * 1.05, 1)
    nt.links.new(tex.outputs['Color'], dim.inputs['A'])
    nt.links.new(dim.outputs['Result'], b.inputs['Base Color'])
    nt.links.new(tex.outputs['Alpha'], b.inputs['Alpha'])
    b.inputs['Roughness'].default_value = 1.0
    b.inputs['Specular IOR Level'].default_value = 0.0
    b.inputs['Emission Color'].default_value = (1.0, 0.72, 0.42, 1)
    nt.links.new(rim.outputs['Color'], b.inputs['Emission Strength'])
    gain = nt.nodes.new('ShaderNodeMath')
    gain.operation = 'MULTIPLY'
    gain.inputs[1].default_value = ARGS.rim
    nt.links.new(rim.outputs['Color'], gain.inputs[0])
    nt.links.new(gain.outputs[0], b.inputs['Emission Strength'])
    # Un peu de lumière traverse le coton blanc à contre-jour.
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
    nt.links.new(tex.outputs['Color'], tr.inputs['Color'])
    mix = nt.nodes.new('ShaderNodeMixShader')
    amount = nt.nodes.new('ShaderNodeMath')
    amount.operation = 'MULTIPLY'
    amount.inputs[1].default_value = 0.0
    nt.links.new(tex.outputs['Alpha'], amount.inputs[0])
    nt.links.new(amount.outputs[0], mix.inputs[0])
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    o.data.materials.append(m)
    return o


def flight(t_end, cam):
    """La trajectoire de la balle depuis le tee : un trait lumineux fin, de largeur apparente constante."""
    t = np.linspace(0.02, t_end, 90)
    v, a = 66.0, math.radians(11.5)
    x = v * math.cos(a) * t * (1 - 0.055 * t)
    z = 0.04 + v * math.sin(a) * t - 0.5 * 5.2 * t * t
    y = -0.010 * x + 0.00005 * x * x  # presque droit, un rien de draw
    pts = np.stack([x, y, z], axis=1)
    dist = np.linalg.norm(pts - np.array(cam), axis=1)
    rad = 0.00055 * dist
    tan = np.gradient(pts, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    up = np.array([0, 0, 1.0])
    n1 = np.cross(tan, up)
    n1 /= np.linalg.norm(n1, axis=1)[:, None]
    n2 = np.cross(tan, n1)
    th = np.linspace(0, 2 * math.pi, 8, endpoint=False)
    ring = pts[:, None, :] + rad[:, None, None] * (n1[:, None, :] * np.cos(th)[None, :, None] + n2[:, None, :] * np.sin(th)[None, :, None])
    i = np.arange(len(pts) - 1)[:, None]
    j = np.arange(8)[None]
    faces = np.stack([i * 8 + j, i * 8 + (j + 1) % 8, (i + 1) * 8 + (j + 1) % 8, (i + 1) * 8 + j], axis=-1).reshape(-1, 4)
    line = P.mesh_obj('Trajectoire', ring.reshape(-1, 3), faces)
    glow = P.mat('Trace', (1, 1, 1), rough=1.0, emission_color=(1.0, 0.60, 0.16, 1), emission_strength=ARGS.trace)
    P.assign(line, glow)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=float(rad[-1] * 2.6), location=tuple(pts[-1]))
    P.assign(bpy.context.object, glow)
    for o in (line, bpy.context.object):
        o.visible_shadow = False


def patch_ground(radius=7.5, color=(0.030, 0.085, 0.012)):
    """Un disque de sol qui s'efface sur son bord : au-delà, c'est le sol du panorama photographié."""
    bpy.ops.mesh.primitive_circle_add(vertices=96, radius=radius * 1.35, fill_type='NGON')
    o = bpy.context.object
    m = P.mat('Sol', color, rough=0.9)
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    fade = nt.nodes.new('ShaderNodeMapRange')
    fade.interpolation_type = 'SMOOTHSTEP'
    fade.inputs['From Min'].default_value = radius * 0.62
    fade.inputs['From Max'].default_value = radius * 1.25
    fade.inputs['To Min'].default_value = 1.0
    fade.inputs['To Max'].default_value = 0.0
    nt.links.new(ln.outputs['Value'], fade.inputs['Value'])
    nt.links.new(fade.outputs[0], P.bsdf(m).inputs['Alpha'])
    haze = nt.nodes.new('ShaderNodeMapRange')  # le sol pâlit vers le bord, comme pris dans la brume
    haze.interpolation_type = 'SMOOTHSTEP'
    haze.inputs['From Min'].default_value = radius * 0.35
    haze.inputs['From Max'].default_value = radius * 1.1
    nt.links.new(ln.outputs['Value'], haze.inputs['Value'])
    tint = nt.nodes.new('ShaderNodeMix')
    tint.data_type = 'RGBA'
    tint.inputs['A'].default_value = (*color, 1)
    tint.inputs['B'].default_value = (0.42, 0.36, 0.26, 1)
    nt.links.new(haze.outputs[0], tint.inputs['Factor'])
    nt.links.new(tint.outputs['Result'], P.bsdf(m).inputs['Base Color'])
    P.assign(o, m)
    return o


def build(args, shot=None):
    """Construit le plan. shot : (première image, dernière image) pour le plan en mouvement du film ;
    renvoie alors la caméra, pour les clés d'exposition du trajet."""
    global ARGS
    ARGS = args
    scene = bpy.context.scene
    hdr = args.sky
    img = bpy.data.images.load(os.path.join(P.ASSETS, hdr + '.hdr'))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[h // 2 :, :, :3].sum(axis=2)
    col = int(np.argmax(lum.max(axis=0)))
    az0 = math.pi - 2 * math.pi * ((col + 0.5) / w - 0.5)
    bpy.data.images.remove(img)
    rotation = math.radians(args.rot) if args.rot is not None else math.radians(args.sun) - az0
    P.sky(hdr, rotation=rotation, strength=1.0, light=args.fill)
    if args.lamp > 0:
        P.sun(azimuth=args.sun, elevation=args.sun_height, strength=args.lamp)
    scene.view_settings.exposure = args.exposure

    # Caméra dans l'axe du coup, derrière le tee, tournée de 8° vers le joueur : il est au centre droit
    # de l'image et la trajectoire monte à sa droite sans passer derrière lui.
    cam_pos = V((-6.0, 0.0, 0.42))
    target = V((-0.06, 0.835, 1.02))
    cd = bpy.data.cameras.new('Cam')
    cd.lens = 50
    cd.sensor_width = 36
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = 2.8
    cd.dof.focus_distance = 6.0
    cam = P.link(bpy.data.objects.new('Camera', cd))
    cam.location = cam_pos
    P.look_at(cam, target)
    scene.camera = cam

    player()
    if shot is None:
        flight(args.t, cam_pos)
    else:
        animate(cam, cam_pos, target, *shot)
    patch_ground()
    view = (target - cam_pos).normalized()
    view.z = 0
    if args.nograss:
        P.bloom(strength=0.35, threshold=1.0)
        return cam
    xy = np.concatenate(
        [
            P.scatter_cone(1_300_000, cam_pos - view * 0.4, view, 0.2, 9.5, math.radians(31), seed=1, falloff=0.7),
            P.scatter_cone(200_000, (0.0, 0.9), view, 0.0, 1.4, math.pi, seed=2, falloff=0.0),
        ]
    )
    rng = np.random.default_rng(5)
    r = np.hypot(xy[:, 0], xy[:, 1])
    keep = rng.random(len(xy)) < np.clip((9.0 - r) / 3.0, 0, 1)  # l'herbe se raréfie vers le bord du disque
    xy = xy[keep]
    n = len(xy)
    clump = 1 + 0.22 * np.sin(xy[:, 0] * 9.1 + 1.3) * np.cos(xy[:, 1] * 7.3 + 0.4)
    hgt = (0.011 + 0.008 * rng.random(n) ** 1.4) * clump
    wid = 0.0008 + 0.0006 * rng.random(n)
    P.grass(xy, hgt, wid, seed=11, lean=(0.1, 0.9))
    P.bloom(strength=args.halo, threshold=1.6)
    return cam


def animate(cam, cam_pos, target, first, last):
    """Le plan en mouvement : la trace ambre de la balle se dessine dans le ciel à droite d'Antoine,
    comme le traceur d'une retransmission : le cadre ne bouge presque pas, c'est la tête du trait qui
    avance jusqu'à la coupe. Le trait sort du flou au-dessus du tee (pas de pied planté dans l'herbe),
    s'affine franchement en s'éloignant, part un rien à droite et revient à gauche (un draw de
    droitier) : il penche, puis se recourbe en haut. Vue de six mètres derrière, la balle prend presque
    toute sa hauteur apparente en une demi-seconde : le temps de vol avance donc lentement d'abord. Sur
    ces deux premières secondes la portance tient la balle sur sa ligne de départ (pesanteur apparente
    2,0) : la tête du trait monte jusqu'au bout, elle ne retombe pas dans l'image.
    Le cadre est tourné de deux degrés vers la droite par rapport à l'image fixe (la trace part de
    x = 0,65 et reste à gauche du carnet du site, qui couvre l'image au-delà de x = 0,72 sur un écran
    16:10) ; il revient d'un degré vers la gauche en accompagnant le draw, et la tête du trait finit à
    HEAD, là où le plan d'arrivée reprend la balle. Le plan finit dans le blanc en deux images : la
    trace baisse d'autant pour rester ambre."""
    K.setup()
    scene = bpy.context.scene
    lens = cam.data.lens
    fly = K.Flight((0.0, 0.0, 0.04), 66.0, 11.5, g=2.0, drag=0.055, draw=(-0.030, 0.00045))
    trace = K.Trace(fly, cam_pos, lens=lens, span=(0.0, 2.4), strength=K.amber(ARGS.exposure, ARGS.glow), width=0.0017, taper=0.6, colour=K.AMBER, steps=240, foot=0.08)
    aim = target - cam_pos
    az0, pitch0, reach = math.atan2(aim.y, aim.x) - math.radians(ARGS.turn), math.atan2(aim.z, math.hypot(aim.x, aim.y)), aim.length
    slide = V((0.25, 0, 0.0))  # la caméra avance d'un rien : le plan respire
    t1 = 0.03 + 2.2
    head = V(fly.at(t1)) - (cam_pos + slide)
    az1 = math.atan2(head.y, head.x) + math.atan((HEAD[0] - 0.5) * 36.0 / lens)
    pitch1 = math.atan2(head.z, math.hypot(head.x, head.y)) - math.atan((0.5 - HEAD[1]) * 20.25 / lens)
    frames = K.half_frames(first, last)
    pos, look, fstop = [], [], []
    for f in frames:
        u = (f - first) / (last - first)
        trace.key(f, 0.03 + 2.2 * u**2.8)
        w = float(K.smooth(u))
        az, tilt = az0 + (az1 - az0) * w, pitch0 + (pitch1 - pitch0) * w
        pos.append(cam_pos + slide * u)
        look.append(pos[-1] + reach * V((math.cos(tilt) * math.cos(az), math.cos(tilt) * math.sin(az), math.sin(tilt))))
        # Le diaphragme se ferme un peu : la tête du trait, à cent mètres, ne se dissout pas dans le flou.
        fstop.append(math.exp(math.log(2.8) + (math.log(8.0) - math.log(2.8)) * float(K.smooth((u - 0.15) / 0.5))))
        e = ARGS.exposure + BURN * float(K.smooth((f - (last - 2)) / 2.0))
        scene.view_settings.exposure = e
        scene.keyframe_insert('view_settings.exposure', frame=f)
        trace.glow(f, K.amber(e, ARGS.glow))
    K.track(cam, frames, pos, look, focus=[6.0] * len(frames), fstop=fstop)


def options(argv=()):
    """Les réglages du plan (ceux de l'image validée par défaut)."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--sky', default='golf_course_sunrise')
    ap.add_argument('--sun', type=float, default=8.0, help='azimut du soleil en degrés (0 = droit devant le joueur)')
    ap.add_argument('--sun-height', type=float, default=7.0)
    ap.add_argument('--lamp', type=float, default=0.0, help="soleil d'appoint (0 = aucun)")
    ap.add_argument('--fill', type=float, default=0.55, help="force de l'éclairage du ciel sur la scène")
    ap.add_argument('--exposure', type=float, default=-0.6)
    ap.add_argument('--rim', type=float, default=1.6)
    ap.add_argument('--rot', type=float, default=None, help='rotation brute du ciel en degrés (remplace --sun)')
    ap.add_argument('--nograss', action='store_true')
    ap.add_argument('--dark', type=float, default=0.5, help='assombrissement de la silhouette (1 = aucun)')
    ap.add_argument('--trace', type=float, default=7.0)
    ap.add_argument('--glow', type=float, default=2.4, help='force de la trace ambre du plan en mouvement')
    ap.add_argument('--turn', type=float, default=2.0, help='plan en mouvement : degrés dont le cadre est tourné vers la droite')
    ap.add_argument('--halo', type=float, default=0.18, help='force du halo des hautes lumières')
    ap.add_argument('--t', type=float, default=1.1, help='secondes de vol déjà tracées')
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--scale', type=int, default=50)
    ap.add_argument('--out', default='render/out/test')
    ap.add_argument('--name', default='finish')
    return ap.parse_args(list(argv))


if __name__ == '__main__':
    ARGS = options(sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else [])
    T0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = ARGS.samples
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 8
    sc.cycles.transparent_max_bounces = 12
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
    sc.render.resolution_percentage = ARGS.scale
    sc.render.image_settings.file_format = 'PNG'
    sc.view_settings.view_transform = 'AgX'
    try:
        sc.view_settings.look = 'AgX - Medium High Contrast'
    except TypeError:
        pass
    build(ARGS)
    os.makedirs(ARGS.out, exist_ok=True)
    sc.render.filepath = os.path.abspath(os.path.join(ARGS.out, ARGS.name + '.png'))
    T1 = time.time()
    bpy.ops.render.render(write_still=True)
    print(f'RESULT {sc.render.filepath} construction {T1 - T0:.1f}s rendu {time.time() - T1:.1f}s')
