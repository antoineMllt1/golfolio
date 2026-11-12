# Le film : huit petites scènes de golf (Blender 5.x / Cycles, lancé avec le module bpy).
#
#   python3 render/fetch_assets.py && python3 scripts/prints.py           # ciels et impressions
#   python render/scene.py -- --stop 0 --scale 50 --samples 24 --out render/out/test    # une image d'arrêt
#
# Pour l'instant seul l'arrêt 0 (le départ du 1, bois 3, aube) est construit.
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parts as P  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--stop', type=int, default=0)
ap.add_argument('--samples', type=int, default=24)
ap.add_argument('--scale', type=int, default=50)
ap.add_argument('--width', type=int, default=1920)
ap.add_argument('--height', type=int, default=1080)
ap.add_argument('--out', default='render/out')
ap.add_argument('--name', default='')
ap.add_argument('--sun', type=float, default=None, help="azimut du soleil en degrés (0 = +X), pour les essais")
ap.add_argument('--exposure', type=float, default=None)
ap.add_argument('--view', default='', choices=['', 'top'], help='vue de contrôle du matériel')
args = ap.parse_args(argv)
V = Vector
T0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = args.samples
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


def sun_azimuth(hdr):
    """Azimut (radians, 0 = +X) du point le plus lumineux du ciel, sans rotation."""
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


def stop_0():
    """Trou 1, le départ, à l'aube : la balle sur un tee bas, la face du bois 3 derrière elle.
    Vue de devant (côté cible), au ras du sol, à contre-jour."""
    hdr = 'spruit_sunrise'
    az0, el = sun_azimuth(hdr)
    want = math.radians(args.sun if args.sun is not None else 153)
    P.sky(hdr, rotation=want - az0, strength=1.0)
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -0.6
    print(f'soleil : azimut d’origine {math.degrees(az0):.0f}°, hauteur {math.degrees(el):.1f}°, placé à {math.degrees(want):.0f}°')

    lift = 0.016  # bas de la balle au-dessus du sol
    b = P.ball((0, 0, lift + P.BALL_R), stamp=os.path.join(P.PRINTS, 'ball_stamp.png'))
    b.rotation_euler = (math.radians(-4), math.radians(6), math.radians(62))
    P.tee(top=(0, 0, lift + 0.0015))
    club = P.wood3()
    club.location = (-(P.BALL_R + 0.007), 0.0, 0.003)

    cam_pos = V((0.96, -0.56, 0.092))
    target = V((-0.131, 0.012, 0.044))
    if args.view == 'top':  # contrôle du club, vu du joueur
        cam_pos, target = V((0.16, 0.34, 0.50)), V((-0.035, 0.0, 0.02))
        cam = camera(cam_pos, target, lens=85, fstop=8, focus=(-0.03, 0, 0.03))
    else:
        cam = camera(cam_pos, target, lens=115, fstop=2.8, focus=(0, 0, lift + P.BALL_R))

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
    return cam


STOPS = [stop_0]
STOPS[args.stop]()
os.makedirs(args.out, exist_ok=True)
path = os.path.join(args.out, (args.name or f'stop-{args.stop}') + '.png')
T1 = time.time()
scene.render.filepath = os.path.abspath(path)
bpy.ops.render.render(write_still=True)
print(f'RESULT {path} construction {T1 - T0:.1f}s rendu {time.time() - T1:.1f}s')
