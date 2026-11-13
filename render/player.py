# Le joueur, construit d'après les photos d'Antoine : silhouette fine, casquette marine, cheveux bruns
# ondulés qui dépassent, haut blanc à manches longues, chino beige, baskets blanches, gant blanc à la
# main gauche (droitier). Il est fait pour être vu de dos, à contre-jour ou dans le flou : jamais de visage.
#
# Repère du joueur : il regarde vers +X, sa gauche est +Y, l'origine est au sol sous son pied gauche.
import math

import bpy
import numpy as np
from mathutils import Vector

import parts as P

V = Vector


# ---------------------------------------------------------------- formes
def spline(pts, per_seg):
    """Courbe de Catmull-Rom passant par pts. Renvoie les points et leur paramètre (0 … len(pts)−1)."""
    p = np.asarray(pts, dtype=float)
    n = len(p)
    out, us = [], []
    for i in range(n - 1):
        p0, p1, p2, p3 = p[max(i - 1, 0)], p[i], p[i + 1], p[min(i + 2, n - 1)]
        for k in range(per_seg):
            t = k / per_seg
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t**3))
            us.append(i + t)
    out.append(p[-1])
    us.append(n - 1)
    return np.array(out), np.array(us)


def sweep(name, pts, radii, around=20, per_seg=8, up=(0, 0, 1), wrinkle=0.0, seed=0, round_ends=True):
    """Tube à section elliptique le long d'une courbe. radii : un rayon ou (largeur, épaisseur) par point."""
    path, u = spline(pts, per_seg)
    r = np.asarray(radii, dtype=float)
    if r.ndim == 1:
        r = np.stack([r, r], axis=1)
    k = np.arange(len(pts))
    rx, ry = np.interp(u, k, r[:, 0]), np.interp(u, k, r[:, 1])
    tan = np.gradient(path, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    if round_ends:  # deux anneaux de plus à chaque bout, pour l'arrondir
        for end, sgn in ((0, -1), (-1, 1)):
            extra = [path[end] + sgn * tan[end] * rx[end] * f for f in (0.45, 0.7)]
            scale = (0.8, 0.12)
            if end == 0:
                path = np.vstack([extra[1], extra[0], path])
                rx, ry = np.concatenate([[rx[0] * scale[1], rx[0] * scale[0]], rx]), np.concatenate([[ry[0] * scale[1], ry[0] * scale[0]], ry])
                tan = np.vstack([tan[0], tan[0], tan])
            else:
                path = np.vstack([path, extra[0], extra[1]])
                rx, ry = np.concatenate([rx, [rx[-1] * scale[0], rx[-1] * scale[1]]]), np.concatenate([ry, [ry[-1] * scale[0], ry[-1] * scale[1]]])
                tan = np.vstack([tan, tan[-1], tan[-1]])
    m = len(path)
    nrm = np.zeros((m, 3))
    ref = np.asarray(up, dtype=float)
    v = ref - tan[0] * (ref @ tan[0])
    if np.linalg.norm(v) < 1e-4:
        v = np.array([1.0, 0, 0]) - tan[0] * tan[0][0]
    nrm[0] = v / np.linalg.norm(v)
    for i in range(1, m):  # transport parallèle : la section ne vrille pas
        v = nrm[i - 1] - tan[i] * (nrm[i - 1] @ tan[i])
        nrm[i] = v / np.linalg.norm(v)
    bin_ = np.cross(tan, nrm)
    th = np.linspace(0, 2 * math.pi, around, endpoint=False)
    rng = np.random.default_rng(seed)
    arc = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))])
    fold = 0
    if wrinkle:
        a, b = rng.random(2) * 6
        fold = wrinkle * (np.sin(arc[:, None] * 31 + 2 * th[None] + a) + 0.6 * np.sin(arc[:, None] * 57 - 3 * th[None] + b))
    verts = path[:, None, :] + nrm[:, None, :] * ((rx[:, None] + fold) * np.cos(th)[None])[:, :, None] + bin_[:, None, :] * ((ry[:, None] + fold) * np.sin(th)[None])[:, :, None]
    i = np.arange(m - 1)[:, None]
    j = np.arange(around)[None]
    j2 = (j + 1) % around
    faces = np.stack([i * around + j, i * around + j2, (i + 1) * around + j2, (i + 1) * around + j], axis=-1)
    return P.mesh_obj(name, verts.reshape(-1, 3), faces.reshape(-1, 4))


def loft(name, sections, around=44, per_seg=6, power=2.5, wrinkle=0.0, seed=0):
    """Volume fait d'ellipses horizontales empilées. sections : (z, cx, cy, rx, ry, lacet en degrés)."""
    s, _ = spline([list(x) for x in sections], per_seg)
    th = np.linspace(0, 2 * math.pi, around, endpoint=False)
    c, sn = np.cos(th), np.sin(th)
    ex, ey = np.sign(c) * np.abs(c) ** (2 / power), np.sign(sn) * np.abs(sn) ** (2 / power)
    rng = np.random.default_rng(seed)
    rings = []
    a, b = rng.random(2) * 6
    for k, (z, cx, cy, rx, ry, yaw) in enumerate(s):
        w = wrinkle * (np.sin(z * 37 + 2 * th + a) + 0.6 * np.sin(z * 61 - 3 * th + b)) if wrinkle else 0
        x, y = (rx + w) * ex, (ry + w) * ey
        ya = math.radians(yaw)
        rings.append(np.stack([cx + x * math.cos(ya) - y * math.sin(ya), cy + x * math.sin(ya) + y * math.cos(ya), np.full(around, z)], axis=1))
    for end in (0, -1):  # fermeture : un anneau presque nul au centre
        z, cx, cy = s[end][0], s[end][1], s[end][2]
        ring = np.stack([np.full(around, cx) + 1e-4 * c, np.full(around, cy) + 1e-4 * sn, np.full(around, z)], axis=1)
        rings.insert(0, ring) if end == 0 else rings.append(ring)
    verts = np.array(rings)
    m = len(verts)
    i = np.arange(m - 1)[:, None]
    j = np.arange(around)[None]
    j2 = (j + 1) % around
    faces = np.stack([i * around + j, i * around + j2, (i + 1) * around + j2, (i + 1) * around + j], axis=-1)
    if s[0][0] > s[-1][0]:
        faces = faces[:, :, ::-1]
    return P.mesh_obj(name, verts.reshape(-1, 3), faces.reshape(-1, 4))


def ik(a, c, la, lb, pole):
    """Articulation (coude, genou) entre a et c pour deux segments la et lb, poussée vers `pole`."""
    a, c, pole = np.asarray(a, float), np.asarray(c, float), np.asarray(pole, float)
    d = np.linalg.norm(c - a)
    d = min(d, (la + lb) * 0.999)
    s = (c - a) / np.linalg.norm(c - a)
    x = (la * la - lb * lb + d * d) / (2 * d)
    h = math.sqrt(max(la * la - x * x, 0))
    n = pole - s * (pole @ s)
    n /= np.linalg.norm(n)
    return a + s * x + n * h


def ellipsoid(name, centre, radii, seg=32, rings=20):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=seg, ring_count=rings, radius=1, location=centre)
    o = bpy.context.object
    o.name = name
    o.scale = radii
    bpy.ops.object.shade_smooth()
    return o


# ---------------------------------------------------------------- matières
def cloth(name, color, rough=0.9, sheen=0.35, glow=0.0):
    m = P.mat(name, color, rough=rough, sheen_weight=sheen, sheen_roughness=0.5)
    if glow:  # le coton fin laisse passer un peu de lumière à contre-jour
        nt = m.node_tree
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
        tr.inputs['Color'].default_value = (*color, 1)
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = glow
        nt.links.new(P.bsdf(m).outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


def materials():
    return dict(
        top=cloth('Haut blanc', (0.80, 0.80, 0.78), glow=0.22),
        chino=cloth('Chino beige', (0.50, 0.44, 0.34), rough=0.85, sheen=0.25),
        cap=cloth('Casquette marine', (0.012, 0.018, 0.045), rough=0.8),
        skin=P.mat('Peau', (0.62, 0.42, 0.32), rough=0.5, subsurface_weight=0.4, subsurface_radius=(0.012, 0.006, 0.004), subsurface_scale=1.0),
        hair=P.mat('Cheveux', (0.085, 0.048, 0.024), rough=0.42, sheen_weight=0.4, anisotropic=0.6),
        shoe=P.mat('Basket', (0.80, 0.80, 0.78), rough=0.55),
        sole=P.mat('Semelle gomme', (0.62, 0.56, 0.44), rough=0.7),
        glove=P.mat('Gant', (0.84, 0.84, 0.82), rough=0.6, sheen_weight=0.2),
        steel=P.mat('Acier', (0.72, 0.73, 0.75), rough=0.18, metal=1.0),
        grip=P.mat('Grip', (0.02, 0.02, 0.022), rough=0.8),
    )


# ---------------------------------------------------------------- parties
def shoe(M, heel, toe, up, parent):
    heel, toe, up = np.asarray(heel, float), np.asarray(toe, float), np.asarray(up, float)
    up = up / np.linalg.norm(up)
    axis = toe - heel
    pts = [heel + axis * t for t in (0.0, 0.3, 0.68, 1.0)]
    upper = sweep('Chaussure', pts, [(0.036, 0.046), (0.044, 0.050), (0.049, 0.036), (0.034, 0.022)], around=20, per_seg=6, up=np.cross(axis, up))
    sole = sweep('Semelle', [p - up * 0.036 for p in pts], [(0.039, 0.012), (0.046, 0.012), (0.051, 0.011), (0.037, 0.010)], around=16, per_seg=6, up=np.cross(axis, up))
    P.assign(upper, M['shoe'])
    P.assign(sole, M['sole'])
    upper.parent = sole.parent = parent


def head(M, centre, parent, seed=4):
    """Tête de dos : nuque, casquette marine, cheveux ondulés qui dépassent dessous."""
    c = np.asarray(centre, float)
    rx, ry, rz = 0.095, 0.078, 0.112
    sk = ellipsoid('Tete', c, (rx, ry, rz))
    P.assign(sk, M['skin'])
    sk.parent = parent
    # Masse de cheveux : une coque autour du crâne, ouverte devant sur le visage.
    seg, rings = 48, 30
    lon = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    lat = np.linspace(-0.62, 0.35, rings) * math.pi / 2 * 1.9
    lat = np.clip(lat, -1.2, 0.7)
    rng = np.random.default_rng(seed)
    dirs = np.stack([np.cos(lat)[:, None] * np.cos(lon)[None], np.cos(lat)[:, None] * np.sin(lon)[None], np.sin(lat)[:, None] * np.ones(seg)[None]], axis=-1)
    wave = 1.07 + 0.035 * np.sin(lon[None] * 7 + lat[:, None] * 9) + 0.025 * np.sin(lon[None] * 13 - lat[:, None] * 5 + 2)
    # Plus de volume vers la nuque, là où les mèches sortent de la casquette.
    wave += 0.06 * np.clip(-np.sin(lat)[:, None], 0, 1) * np.ones(seg)[None]
    verts = c + dirs * wave[:, :, None] * np.array([rx, ry, rz])
    i = np.arange(rings - 1)[:, None]
    j = np.arange(seg)[None]
    j2 = (j + 1) % seg
    faces = np.stack([i * seg + j, i * seg + j2, (i + 1) * seg + j2, (i + 1) * seg + j], axis=-1).reshape(-1, 4)
    front = (dirs[:, :, 0] > 0.42).reshape(-1)  # le visage reste dégagé
    faces = faces[~front[faces].any(axis=1)]
    shell = P.mesh_obj('Cheveux', verts.reshape(-1, 3), faces)
    P.assign(shell, M['hair'])
    shell.parent = parent
    # Mèches qui rebiquent sous la casquette, sur la nuque et les côtés.
    for k in range(44):
        a = math.pi + (rng.random() * 2 - 1) * 2.15  # tout autour sauf devant
        el = -0.42 + rng.random() * 0.42
        d = np.array([math.cos(el) * math.cos(a), math.cos(el) * math.sin(a), math.sin(el)])
        out = np.array([d[0], d[1], 0.0])
        out /= np.linalg.norm(out)
        p0 = c + d * np.array([rx, ry, rz]) * 1.08
        ln = 0.018 + 0.018 * rng.random()
        side = np.cross(out, [0, 0, 1]) * (rng.random() - 0.5) * 0.03
        p1 = p0 + out * ln * 0.5 + np.array([0, 0, -ln * 0.9]) + side
        p2 = p1 + out * ln * 0.9 + np.array([0, 0, -ln * 0.35]) + side
        p3 = p2 + out * ln * 0.7 + np.array([0, 0, ln * (0.25 + 0.5 * rng.random())])  # la pointe rebique
        w = 0.010 + 0.006 * rng.random()
        t = sweep('Meche', [p0, p1, p2, p3], [(w, w * 0.5), (w * 0.95, w * 0.45), (w * 0.7, w * 0.35), (w * 0.25, w * 0.15)], around=8, per_seg=5, up=(0, 0, 1))
        P.assign(t, M['hair'])
        t.parent = parent
    # Casquette : calotte, visière (devant, donc cachée de dos), bouton.
    seg, rings = 40, 14
    lon = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    lat = np.linspace(0.04, math.pi / 2, rings)
    dome = np.stack([np.cos(lat)[:, None] * np.cos(lon)[None], np.cos(lat)[:, None] * np.sin(lon)[None], np.sin(lat)[:, None] * np.ones(seg)[None]], axis=-1)
    cc = c + np.array([0.004, 0, 0.022])
    dv = cc + dome * np.array([rx * 1.13, ry * 1.17, rz * 0.93])
    i = np.arange(rings - 1)[:, None]
    faces = np.stack([i * seg + j, i * seg + j2, (i + 1) * seg + j2, (i + 1) * seg + j], axis=-1).reshape(-1, 4)
    cap = P.mesh_obj('Casquette', dv.reshape(-1, 3), faces)
    P.assign(cap, M['cap'])
    cap.parent = parent
    ang = np.linspace(-1.0, 1.0, 21)
    rad = np.linspace(0.0, 1.0, 7)
    bv = np.zeros((len(rad), len(ang), 3))
    for a_i, a in enumerate(ang):
        for r_i, r in enumerate(rad):
            reach = 0.075 * (1 - 0.55 * a * a)
            bv[r_i, a_i] = cc + np.array([math.cos(a) * (rx * 1.10 + r * reach), math.sin(a) * (ry * 1.14 + r * reach * 0.5), 0.012 - 0.022 * r - 0.012 * a * a])
    i = np.arange(len(rad) - 1)[:, None]
    jj = np.arange(len(ang) - 1)[None]
    faces = np.stack([i * len(ang) + jj, i * len(ang) + jj + 1, (i + 1) * len(ang) + jj + 1, (i + 1) * len(ang) + jj], axis=-1).reshape(-1, 4)
    brim = P.mesh_obj('Visiere', bv.reshape(-1, 3), faces)
    P.assign(brim, M['cap'])
    brim.parent = parent
    sol = brim.modifiers.new('Epaisseur', 'SOLIDIFY')
    sol.thickness = 0.004
    button = ellipsoid('Bouton', cc + np.array([0, 0, rz * 0.93]), (0.009, 0.009, 0.005), 12, 8)
    P.assign(button, M['cap'])
    button.parent = parent


def iron_simple(M, grip, direction, length, parent):
    """Fer à manche acier, simplifié pour la silhouette : manche, grip, tête."""
    g, d = np.asarray(grip, float), np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    butt, tip = g - d * 0.10, g + d * (length - 0.10)
    grip_o = sweep('Grip', [butt, g + d * 0.16], [0.0125, 0.0105], around=14, per_seg=4)
    P.assign(grip_o, M['grip'])
    shaft = sweep('Manche acier', [g + d * 0.16, tip], [0.0072, 0.0047], around=12, per_seg=4, round_ends=False)
    P.assign(shaft, M['steel'])
    # Tête : une lame au bout, inclinée par rapport au manche.
    side = np.cross(d, [0, 0, 1])
    side /= np.linalg.norm(side)
    blade_dir = d * 0.45 - np.array([0, 0, 1]) * 0.55 + side * 0.7
    blade_dir /= np.linalg.norm(blade_dir)
    blade = sweep('Tete de fer', [tip - d * 0.01, tip + blade_dir * 0.04, tip + blade_dir * 0.085], [(0.011, 0.008), (0.024, 0.006), (0.027, 0.005)], around=14, per_seg=5, up=d)
    P.assign(blade, M['steel'])
    for o in (grip_o, shaft, blade):
        o.parent = parent


# ---------------------------------------------------------------- le joueur
def golfer_finish(location=(0, 0, 0), yaw=0.0):
    """Le joueur au finish, tel qu'on le voit de dos : poids sur la jambe gauche, pied droit sur la
    pointe, mains hautes à gauche de la tête, le fer en travers derrière la nuque."""
    M = materials()
    root = P.link(bpy.data.objects.new('Joueur', None))
    # Jambes (hanches hautes, bâti fin).
    hip_l, hip_r = np.array([-0.01, 0.0, 0.93]), np.array([-0.02, -0.185, 0.93])
    ankle_l = np.array([-0.015, 0.01, 0.085])
    knee_l = ik(hip_l, ankle_l, 0.44, 0.42, (0.35, 0.0, 0.0))
    ankle_r = np.array([-0.33, -0.215, 0.235])
    knee_r = ik(hip_r, ankle_r, 0.44, 0.42, (1.0, 0.25, -0.2))
    for name, hip, knee, ankle, seed in (('Jambe gauche', hip_l, knee_l, ankle_l, 1), ('Jambe droite', hip_r, knee_r, ankle_r, 2)):
        leg = sweep(name, [hip, (hip + knee) / 2, knee, (knee + ankle) / 2, ankle + (ankle - knee) * 0.04], [0.094, 0.094, 0.086, 0.081, 0.079], around=24, per_seg=8, up=(1, 0, 0), wrinkle=0.0016, seed=seed)
        P.assign(leg, M['chino'])
        leg.parent = root
    shoe(M, (-0.075, -0.012, 0.047), (0.195, 0.075, 0.036), (0, 0, 1), root)
    shoe(M, (-0.315, -0.212, 0.265), (-0.405, -0.232, 0.035), (0.95, 0.05, 0.3), root)
    # Bassin (chino) puis buste (haut blanc, sorti du pantalon), tourné vers la cible et au-delà.
    pelvis = loft('Bassin', [(0.805, -0.018, -0.092, 0.094, 0.186, 0), (0.88, -0.016, -0.092, 0.110, 0.192, 3), (0.96, -0.012, -0.092, 0.108, 0.176, 7), (1.05, -0.010, -0.092, 0.094, 0.156, 10)], power=2.6, wrinkle=0.0015, seed=3)
    P.assign(pelvis, M['chino'])
    pelvis.parent = root
    torso = loft(
        'Buste',
        [(0.885, -0.014, -0.092, 0.128, 0.200, 4), (0.96, -0.012, -0.092, 0.120, 0.186, 6), (1.05, -0.010, -0.092, 0.106, 0.166, 9), (1.15, -0.004, -0.092, 0.098, 0.152, 13), (1.30, 0.004, -0.092, 0.106, 0.182, 17), (1.41, 0.004, -0.092, 0.100, 0.212, 19), (1.465, 0.003, -0.092, 0.086, 0.196, 19), (1.50, 0.002, -0.092, 0.062, 0.118, 19), (1.52, 0.0, -0.092, 0.050, 0.058, 19)],
        power=2.3,
        wrinkle=0.0018,
        seed=5,
    )
    P.assign(torso, M['top'])
    torso.parent = root
    # Bras : les deux mains tiennent le club, hautes, à gauche de la tête.
    sh_l, sh_r = np.array([-0.066, 0.105, 1.452]), np.array([0.070, -0.290, 1.452])
    hands = np.array([-0.135, 0.165, 1.685])
    el_l = ik(sh_l, hands, 0.30, 0.27, (-0.35, 0.55, -1.0))
    el_r = ik(sh_r, hands + [0.02, -0.03, -0.05], 0.31, 0.28, (1.0, -0.2, -0.6))
    for name, sh, el, hd, seed in (('Bras gauche', sh_l, el_l, hands, 6), ('Bras droit', sh_r, el_r, hands + [0.02, -0.03, -0.05], 7)):
        arm = sweep(name, [sh, (sh + el) / 2, el, (el + hd) / 2, el + (hd - el) * 0.9], [0.058, 0.050, 0.044, 0.039, 0.034], around=18, per_seg=8, up=(0, 0, 1), wrinkle=0.0012, seed=seed)
        P.assign(arm, M['top'])
        arm.parent = root
    glove = ellipsoid('Main gauche', hands + [0.0, 0.0, 0.02], (0.040, 0.036, 0.052), 20, 14)
    P.assign(glove, M['glove'])
    glove.parent = root
    right = ellipsoid('Main droite', hands + [0.02, -0.045, -0.02], (0.038, 0.036, 0.048), 20, 14)
    P.assign(right, M['skin'])
    right.parent = root
    # Cou, tête, casquette, cheveux.
    neck = sweep('Cou', [(0.0, -0.092, 1.49), (0.004, -0.092, 1.56), (0.008, -0.092, 1.61)], [0.050, 0.047, 0.048], around=16, per_seg=5, up=(1, 0, 0), round_ends=False)
    P.assign(neck, M['skin'])
    neck.parent = root
    head(M, (0.012, -0.092, 1.655), root)
    # Le fer, en travers derrière la nuque, tête à droite.
    iron_simple(M, hands, (-0.16, -0.97, -0.10), 0.94, root)
    root.location = location
    root.rotation_euler = (0, 0, yaw)
    return root
