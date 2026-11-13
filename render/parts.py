# Briques des scènes (échelle réelle, en mètres) : outils, matières, balle, tee, bois 3, herbe, rosée,
# sol et ciel. Repère d'un coup : la balle part vers +X, le joueur (droitier) se tient côté +Y.
import math
import os
import warnings

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

warnings.filterwarnings('ignore', category=DeprecationWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, 'assets')
PRINTS = os.path.join(HERE, 'prints')
V = Vector
BALL_R = 0.021335


# ---------------------------------------------------------------- outils
def link(o):
    bpy.context.scene.collection.objects.link(o)
    return o


def mesh_obj(name, verts, faces, smooth=True):
    """Maillage à partir de tableaux numpy : verts (N,3), faces (M,3) ou (M,4)."""
    verts = np.asarray(verts, dtype=np.float32)
    faces = np.asarray(faces, dtype=np.int32)
    k = faces.shape[1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set('co', verts.ravel())
    me.loops.add(faces.size)
    me.loops.foreach_set('vertex_index', faces.ravel())
    me.polygons.add(len(faces))
    me.polygons.foreach_set('loop_start', np.arange(len(faces), dtype=np.int32) * k)
    me.polygons.foreach_set('loop_total', np.full(len(faces), k, dtype=np.int32))
    if smooth:
        me.polygons.foreach_set('use_smooth', np.ones(len(faces), dtype=bool))
    me.update()
    me.validate()
    return link(bpy.data.objects.new(name, me))


def lathe(name, profile, segments=64, smooth=True):
    """Solide de révolution autour de Z à partir d'un profil [(rayon, z), …]."""
    prof = np.asarray(profile, dtype=np.float32)
    n = len(prof)
    a = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    verts = np.zeros((n, segments, 3), dtype=np.float32)
    verts[:, :, 0] = prof[:, 0:1] * np.cos(a)[None]
    verts[:, :, 1] = prof[:, 0:1] * np.sin(a)[None]
    verts[:, :, 2] = prof[:, 1:2]
    i = np.arange(n - 1)[:, None]
    j = np.arange(segments)[None]
    j2 = (j + 1) % segments
    faces = np.stack([i * segments + j, i * segments + j2, (i + 1) * segments + j2, (i + 1) * segments + j], axis=-1)
    return mesh_obj(name, verts.reshape(-1, 3), faces.reshape(-1, 4), smooth)


def srgb(h):
    c = [int(h[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def mat(name, color=(0.8, 0.8, 0.8), rough=0.5, metal=0.0, **inputs):
    """Matière Principled. inputs : noms d'entrées avec _ à la place des espaces (coat_weight=0.5…)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    for k, v in inputs.items():
        key = k.replace('_', ' ').title().replace('Ior', 'IOR')
        if key in b.inputs:
            b.inputs[key].default_value = v
    return m


def bsdf(m):
    return m.node_tree.nodes['Principled BSDF']


def assign(o, *materials):
    for m in materials:
        o.data.materials.append(m)
    return o


def look_at(o, target):
    o.rotation_euler = (V(target) - o.location).to_track_quat('-Z', 'Y').to_euler()


# ---------------------------------------------------------------- ciel
def sky(hdr, rotation=0.0, strength=1.0, light=None):
    """Ciel photographié : il éclaire la scène et sert de fond.
    `light` : force de l'éclairage si elle doit différer de ce que voit la caméra (pour une silhouette)."""
    world = bpy.data.worlds.new('World')
    bpy.context.scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(os.path.join(ASSETS, hdr + '.hdr'))
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, rotation)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    bg = nt.nodes['Background']
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = strength
    if light is not None:
        path = nt.nodes.new('ShaderNodeLightPath')
        pick = nt.nodes.new('ShaderNodeMix')
        pick.data_type = 'FLOAT'
        pick.inputs['A'].default_value = light
        pick.inputs['B'].default_value = strength
        nt.links.new(path.outputs['Is Camera Ray'], pick.inputs['Factor'])
        nt.links.new(pick.outputs['Result'], bg.inputs['Strength'])
    return world


def sun(azimuth, elevation, strength=2.5, color=(1.0, 0.74, 0.48), angle=2.0):
    """Soleil d'appoint, quand celui du ciel est voilé. Angles en degrés, azimut 0 = +X."""
    l = bpy.data.lights.new('Soleil', 'SUN')
    l.energy = strength
    l.color = color
    l.angle = math.radians(angle)
    o = link(bpy.data.objects.new('Soleil', l))
    az, el = math.radians(azimuth), math.radians(elevation)
    d = V((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    o.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return o


# ---------------------------------------------------------------- balle
def geodesic(f):
    """Sommets d'un icosaèdre géodésique de fréquence f : 10·f² + 2 points sur la sphère."""
    t = (1 + 5**0.5) / 2
    ico = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], dtype=float)
    tris = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    pts = []
    for a, b, c in tris:
        for i in range(f + 1):
            for j in range(f + 1 - i):
                pts.append((ico[a] * i + ico[b] * j + ico[c] * (f - i - j)) / f)
    p = np.array(pts)
    p /= np.linalg.norm(p, axis=1)[:, None]
    _, idx = np.unique(np.round(p, 5), axis=0, return_index=True)
    return p[np.sort(idx)]


def ball_material(stamp=None):
    m = mat('Balle', (0.88, 0.88, 0.86), rough=0.24, coat_weight=0.55, coat_roughness=0.07, subsurface_weight=0.12, subsurface_radius=(0.004, 0.004, 0.0035), subsurface_scale=1.0)
    if stamp and os.path.exists(stamp):
        nt = m.node_tree
        b = bsdf(m)
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sep = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['Object'], sep.inputs[0])
        # Projection le long de −Y de l'objet : u = x, v = z, ramenés sur 0–1 autour du centre.
        comb = nt.nodes.new('ShaderNodeCombineXYZ')
        size = 0.030
        for axis, out in (('X', 'X'), ('Z', 'Y')):
            mul = nt.nodes.new('ShaderNodeMath')
            mul.operation = 'MULTIPLY_ADD'
            mul.inputs[1].default_value = 1 / size
            mul.inputs[2].default_value = 0.5
            nt.links.new(sep.outputs[axis], mul.inputs[0])
            nt.links.new(mul.outputs[0], comb.inputs[out])
        img = nt.nodes.new('ShaderNodeTexImage')
        img.image = bpy.data.images.load(stamp)
        img.extension = 'CLIP'
        nt.links.new(comb.outputs[0], img.inputs['Vector'])
        side = nt.nodes.new('ShaderNodeMath')  # seulement la face −Y
        side.operation = 'LESS_THAN'
        side.inputs[1].default_value = -0.008
        nt.links.new(sep.outputs['Y'], side.inputs[0])
        mask = nt.nodes.new('ShaderNodeMath')
        mask.operation = 'MULTIPLY'
        nt.links.new(img.outputs['Alpha'], mask.inputs[0])
        nt.links.new(side.outputs[0], mask.inputs[1])
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = (0.88, 0.88, 0.86, 1)
        nt.links.new(mask.outputs[0], mix.inputs['Factor'])
        nt.links.new(img.outputs['Color'], mix.inputs['B'])
        nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    return m


def ball(location=(0, 0, BALL_R), stamp=None, subdivisions=7, depth=0.00026):
    """Balle de 42,67 mm à 362 alvéoles en relief (réseau icosaédrique, comme les vraies)."""
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=subdivisions, radius=1.0)
    o = bpy.context.object
    o.name = 'Balle'
    me = o.data
    n = len(me.vertices)
    co = np.zeros(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    d = co.reshape(-1, 3)
    d /= np.linalg.norm(d, axis=1)[:, None]
    centres = geodesic(6).astype(np.float32)
    # Rayon de chaque alvéole : une fraction de la distance à sa plus proche voisine.
    cc = centres @ centres.T
    np.fill_diagonal(cc, -1)
    rad = 0.445 * np.arccos(np.clip(cc.max(axis=1), -1, 1))
    best = np.full(n, -1.0, dtype=np.float32)
    idx = np.zeros(n, dtype=np.int64)
    for s in range(0, n, 20000):
        dots = d[s : s + 20000] @ centres.T
        idx[s : s + 20000] = dots.argmax(axis=1)
        best[s : s + 20000] = dots.max(axis=1)
    t = np.clip(np.arccos(np.clip(best, -1, 1)) / rad[idx], 0, 1)
    # Calotte à bord adouci.
    prof = (1 - t * t) * (1 - np.clip((t - 0.86) / 0.14, 0, 1) ** 2 * 0.35)
    r = BALL_R - depth * prof
    me.vertices.foreach_set('co', (d * r[:, None]).astype(np.float32).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
    me.update()
    o.location = location
    assign(o, ball_material(stamp))
    return o


# ---------------------------------------------------------------- tee
def tee(top=(0, 0, 0.014), length=0.054):
    """Tee en bois : la coupelle est en haut, `top` est le bord de la coupelle."""
    prof = [(0.0002, -length), (0.0016, -length + 0.006), (0.0023, -length + 0.014), (0.0023, -0.012), (0.0027, -0.008), (0.0040, -0.004), (0.0054, -0.0012), (0.0058, 0.0), (0.0053, 0.0), (0.0040, -0.0011), (0.0020, -0.0019), (0.0001, -0.0021)]
    o = lathe('Tee', prof, 48)
    o.location = top
    m = mat('Tee', (0.80, 0.62, 0.40), rough=0.5, coat_weight=0.15, coat_roughness=0.3)
    nt = m.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (600, 600, 30)
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 1.0
    noise.inputs['Detail'].default_value = 6
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    nt.links.new(mp.outputs['Vector'], noise.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.62, 0.44, 0.25, 1)
    ramp.color_ramp.elements[1].color = (0.86, 0.70, 0.48, 1)
    nt.links.new(noise.outputs['Fac'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bsdf(m).inputs['Base Color'])
    assign(o, m)
    return o


# ---------------------------------------------------------------- bois 3
def wood3(loft=15.0, lie=57.0):
    """Tête de bois 3 à l'adresse. Origine : bas du centre de la face ; la face regarde +X, le talon
    et le manche sont côté +Y. Renvoie un vide parent, pour déplacer tout le club."""
    L = math.radians(loft)
    a, b = 0.056, 0.051  # demi-longueur (face → arrière), demi-largeur (pointe → talon)
    xc = -0.042  # centre du corps
    zmid, h_top, h_bot = 0.0145, 0.0205, 0.0145
    n_r, n_s = 40, 144
    rho = np.sin(np.linspace(0, 1, n_r + 1) * math.pi / 2)  # anneaux serrés vers le bord
    th = np.linspace(0, 2 * math.pi, n_s, endpoint=False)
    c, s = np.cos(th), np.sin(th)
    # Contour vu de dessus : superellipse plus carrée devant (la face), plus ronde derrière.
    ex = np.where(c > 0, 3.6, 2.15)
    rad = (np.abs(c) ** ex + np.abs(s) ** ex) ** (-1 / ex)
    # Forme en poire : la pointe (−Y) plus large que le talon (+Y), où s'attache le manche.
    ox, oy = a * rad * c, b * rad * s * (0.98 - 0.07 * s)
    # Une pointe un peu plus haute que le talon, un arrière qui s'abaisse.
    lift_y = 0.07 * (-s)
    lift_x = -0.24 * np.clip(-c, 0, 1) ** 1.6

    def shell(height, p, q, sign):
        z = height * (1 - rho[:, None] ** p) ** (1 / q)
        v = np.zeros((n_r + 1, n_s, 3))
        v[:, :, 0] = xc + rho[:, None] * ox[None]
        v[:, :, 1] = rho[:, None] * oy[None]
        # La pente de la couronne s'installe depuis le centre : tous les rayons s'y rejoignent à la même hauteur.
        tilt = 1 + lift_y[None] * rho[:, None] + lift_x[None] * rho[:, None] ** 2 if sign > 0 else 1
        v[:, :, 2] = zmid + sign * z * tilt
        return v

    top = shell(h_top, 2.5, 2.7, +1)
    bot = shell(h_bot, 3.6, 2.6, -1)
    verts = np.concatenate([top.reshape(-1, 3), bot[:-1].reshape(-1, 3)])  # l'anneau du bord est partagé
    n_top = (n_r + 1) * n_s

    def idx(part, i, j):
        j = j % n_s
        if part == 'top' or i == n_r:
            return i * n_s + j
        return n_top + i * n_s + j

    faces, part_of = [], []
    for part in ('top', 'bot'):
        for i in range(n_r):
            for j in range(n_s):
                q = [idx(part, i, j), idx(part, i, j + 1), idx(part, i + 1, j + 1), idx(part, i + 1, j)]
                faces.append(q if part == 'bot' else q[::-1])
                part_of.append(0 if part == 'top' else 1)
    head = mesh_obj('Bois3', verts, np.array(faces))
    me = head.data
    me.polygons.foreach_set('material_index', np.array(part_of, dtype=np.int32))
    rho_v = np.zeros(len(verts), dtype=np.float32)
    back_v = np.zeros(len(verts), dtype=np.float32)
    rho_v[:n_top] = np.repeat(rho, n_s)
    back_v[:n_top] = np.tile(np.clip(-c, 0, 1), n_r + 1)
    me.attributes.new('rho', 'FLOAT', 'POINT').data.foreach_set('value', rho_v)
    me.attributes.new('back', 'FLOAT', 'POINT').data.foreach_set('value', back_v)

    # La face : le corps est tranché net par le plan incliné du loft, et la coupe est refermée.
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    normal = V((math.cos(L), 0.0, math.sin(L)))
    cut = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-7, plane_co=V((0.0, 0.0, 0.017)), plane_no=normal, clear_outer=True)
    rim = [e for e in cut['geom_cut'] if isinstance(e, bmesh.types.BMEdge)]
    for f in bmesh.ops.holes_fill(bm, edges=rim)['faces']:
        f.material_index = 2
        f.smooth = False
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()

    # Tête tout en noir : couronne brillante en carbone tressé, liseré ambre à l'arrière, repère
    # d'alignement à l'avant ; flancs satinés ; face noire à stries blanches.
    crown = mat('Couronne', (0.012, 0.013, 0.015), rough=0.3, coat_weight=1.0, coat_roughness=0.035)
    nt = crown.node_tree
    cb = bsdf(crown)

    def cal(kind, a, b=None, c=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = kind
        for k, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]

    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])
    # Carbone tressé : un damier fin en diagonale, qui s'efface vers la face.
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(45))
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    chk = nt.nodes.new('ShaderNodeTexChecker')
    chk.inputs['Scale'].default_value = 800
    nt.links.new(mp.outputs['Vector'], chk.inputs['Vector'])
    fade = nt.nodes.new('ShaderNodeMapRange')
    fade.inputs['From Min'].default_value = -0.012
    fade.inputs['From Max'].default_value = -0.034
    nt.links.new(sep.outputs['X'], fade.inputs['Value'])
    weave = cal('MULTIPLY', chk.outputs['Fac'], fade.outputs[0])
    # Liseré ambre le long du bord arrière, et un point d'alignement à l'avant.
    att_r = nt.nodes.new('ShaderNodeAttribute')
    att_r.attribute_name = 'rho'
    att_b = nt.nodes.new('ShaderNodeAttribute')
    att_b.attribute_name = 'back'
    ring = cal('MULTIPLY', cal('GREATER_THAN', att_r.outputs['Fac'], 0.930), cal('LESS_THAN', att_r.outputs['Fac'], 0.952))
    trim = cal('MULTIPLY', ring, cal('GREATER_THAN', att_b.outputs['Fac'], 0.12))
    flat = nt.nodes.new('ShaderNodeCombineXYZ')
    nt.links.new(sep.outputs['X'], flat.inputs['X'])
    nt.links.new(sep.outputs['Y'], flat.inputs['Y'])
    dist = nt.nodes.new('ShaderNodeVectorMath')
    dist.operation = 'DISTANCE'
    dist.inputs[1].default_value = (-0.017, 0.0, 0)
    nt.links.new(flat.outputs[0], dist.inputs[0])
    amber = cal('MAXIMUM', trim, cal('LESS_THAN', dist.outputs['Value'], 0.0016))
    base = nt.nodes.new('ShaderNodeMix')
    base.data_type = 'RGBA'
    base.inputs['A'].default_value = (0.009, 0.010, 0.012, 1)
    base.inputs['B'].default_value = (0.022, 0.024, 0.027, 1)
    nt.links.new(weave, base.inputs['Factor'])
    gold = nt.nodes.new('ShaderNodeMix')
    gold.data_type = 'RGBA'
    gold.inputs['B'].default_value = (0.90, 0.55, 0.12, 1)
    nt.links.new(amber, gold.inputs['Factor'])
    nt.links.new(base.outputs['Result'], gold.inputs['A'])
    nt.links.new(gold.outputs['Result'], cb.inputs['Base Color'])
    nt.links.new(amber, cb.inputs['Metallic'])
    nt.links.new(cal('MULTIPLY_ADD', weave, 0.12, 0.26), cb.inputs['Roughness'])
    sole = mat('Flancs', (0.030, 0.031, 0.034), rough=0.30, metal=1.0)
    face = mat('Face', (0.022, 0.022, 0.024), rough=0.34, metal=1.0)
    nt = face.node_tree
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def calc(kind, a, b=None, c=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = kind
        for k, v in enumerate((a, b, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = v
            else:
                nt.links.new(v, n.inputs[k])
        return n.outputs[0]

    pitch, thick, z0, zr, yr = 0.0046, 0.00055, 0.0180, 0.0135, 0.031
    # Une strie blanche tous les 4,2 mm, dans une enveloppe ovale (plus courtes en haut et en bas).
    row = calc('ABSOLUTE', calc('SUBTRACT', calc('FRACT', calc('DIVIDE', sep.outputs['Z'], pitch)), 0.5))
    line = calc('LESS_THAN', row, thick / pitch / 2)
    zc = calc('DIVIDE', calc('SUBTRACT', sep.outputs['Z'], z0), zr)
    ylim = calc('MULTIPLY', calc('SQRT', calc('MAXIMUM', calc('SUBTRACT', 1.0, calc('MULTIPLY', zc, zc)), 0.0)), yr)
    within = calc('LESS_THAN', calc('ABSOLUTE', sep.outputs['Y']), ylim)
    mask = calc('MULTIPLY', line, within)
    paint = nt.nodes.new('ShaderNodeMix')
    paint.data_type = 'RGBA'
    paint.inputs['A'].default_value = (0.022, 0.022, 0.024, 1)
    paint.inputs['B'].default_value = (0.86, 0.86, 0.84, 1)
    nt.links.new(mask, paint.inputs['Factor'])
    nt.links.new(paint.outputs['Result'], bsdf(face).inputs['Base Color'])
    nt.links.new(calc('SUBTRACT', 1.0, mask), bsdf(face).inputs['Metallic'])
    nt.links.new(calc('MULTIPLY_ADD', mask, 0.2, 0.34), bsdf(face).inputs['Roughness'])
    assign(head, crown, sole, face)
    bev = head.modifiers.new('Bevel', 'BEVEL')
    bev.width = 0.0009
    bev.segments = 3
    bev.limit_method = 'ANGLE'
    bev.angle_limit = math.radians(32)
    bpy.context.view_layer.objects.active = head
    head.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(38))

    # Hosel, bague et manche : un seul solide de révolution, incliné de l'angle de lie vers le joueur.
    r_h = 0.0064
    prof = [(0.0, -0.012), (r_h, -0.012), (r_h, 0.030), (r_h - 0.0004, 0.031), (0.0060, 0.0315), (0.0046, 0.047), (0.0044, 0.048), (0.0047, 0.30), (0.0058, 0.75), (0.0075, 1.05), (0.0, 1.05)]
    shaft = lathe('Manche', prof, 40)
    steel = mat('Hosel', (0.030, 0.031, 0.034), rough=0.34, metal=1.0)
    ferr = mat('Bague', (0.70, 0.71, 0.73), rough=0.18, metal=1.0)
    graph = mat('Graphite', (0.010, 0.011, 0.013), rough=0.38, coat_weight=0.3, coat_roughness=0.25)
    assign(shaft, steel, ferr, graph)
    zf = np.array([np.mean([shaft.data.vertices[i].co.z for i in p.vertices]) for p in shaft.data.polygons])
    shaft.data.polygons.foreach_set('material_index', np.where(zf < 0.0308, 0, np.where(zf < 0.0345, 1, 2)).astype(np.int32))
    top_z = zmid + h_top
    shaft.location = (-0.015, 0.0385, top_z - 0.012)
    shaft.rotation_euler = (-(math.pi / 2 - math.radians(lie)), 0, 0)

    root = link(bpy.data.objects.new('Club', None))
    head.parent = root
    shaft.parent = root
    return root


# ---------------------------------------------------------------- herbe
def grass_material(name='Brin', dark=(0.030, 0.105, 0.012), light=(0.105, 0.25, 0.03), glow=(0.27, 0.55, 0.06), translucency=0.38):
    m = mat(name, light, rough=0.42, sheen_weight=0.25)
    nt = m.node_tree
    b = bsdf(m)
    geo = nt.nodes.new('ShaderNodeNewGeometry')
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
    dry = ramp.color_ramp.elements.new(0.965)
    dry.color = (0.30, 0.30, 0.07, 1)
    ramp.color_ramp.elements[1].position = 0.9
    nt.links.new(geo.outputs['Random Per Island'], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], b.inputs['Base Color'])
    tr = nt.nodes.new('ShaderNodeBsdfTranslucent')  # la lumière traverse le brin à contre-jour
    tr.inputs['Color'].default_value = (*glow, 1)
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs[0].default_value = translucency
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


def grass(xy, height, width, seed=1, lean=(0.15, 0.6), material=None, name='Herbe'):
    """Vrais brins : un ruban de trois quadrilatères par brin, courbé et effilé.
    xy (N,2) positions, height et width (N,) en mètres. Renvoie l'objet et les pointes (N,3)."""
    rng = np.random.default_rng(seed)
    n = len(xy)
    yaw = rng.random(n) * 2 * math.pi
    ln = lean[0] + (lean[1] - lean[0]) * rng.random(n)
    cx, cy = np.cos(yaw), np.sin(yaw)
    seg = 3
    verts = np.zeros((n, (seg + 1) * 2, 3), dtype=np.float32)
    for k in range(seg + 1):
        t = k / seg
        w = width * (1 - 0.86 * t)
        fwd = ln * height * t * t
        z = height * t * (1 - 0.15 * t)
        for side, sg in enumerate((-1, 1)):
            verts[:, k * 2 + side, 0] = xy[:, 0] + cx * fwd - cy * w * sg
            verts[:, k * 2 + side, 1] = xy[:, 1] + cy * fwd + cx * w * sg
            verts[:, k * 2 + side, 2] = z
    base = (np.arange(n) * (seg + 1) * 2)[:, None]
    faces = np.zeros((n, seg, 4), dtype=np.int32)
    for k in range(seg):
        faces[:, k, :] = base + np.array([k * 2, k * 2 + 1, k * 2 + 3, k * 2 + 2])
    o = mesh_obj(name, verts.reshape(-1, 3), faces.reshape(-1, 4))
    assign(o, material or grass_material())
    tips = np.stack([xy[:, 0] + cx * ln * height, xy[:, 1] + cy * ln * height, height * 0.85], axis=1)
    return o, tips


def scatter_cone(n, origin, direction, near, far, half_angle, seed=1, falloff=1.0):
    """Points au sol dans un secteur partant de `origin` : dense près de la caméra, plus rare au loin."""
    rng = np.random.default_rng(seed)
    u = rng.random(n)
    r = near + (far - near) * u ** (1.0 + falloff)
    a = math.atan2(direction[1], direction[0]) + (rng.random(n) * 2 - 1) * half_angle
    return np.stack([origin[0] + r * np.cos(a), origin[1] + r * np.sin(a)], axis=1)


def dew(points, radius=(0.00035, 0.0009), seed=3):
    """Gouttes de rosée : une petite sphère par point (N,3)."""
    rng = np.random.default_rng(seed)
    n = len(points)
    t = (1 + 5**0.5) / 2
    ico = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], dtype=np.float32)
    ico /= np.linalg.norm(ico[0])
    tris = np.array([(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)], dtype=np.int32)
    r = (radius[0] + (radius[1] - radius[0]) * rng.random(n) ** 2).astype(np.float32)
    verts = points[:, None, :].astype(np.float32) + ico[None] * r[:, None, None]
    faces = tris[None] + (np.arange(n, dtype=np.int32) * 12)[:, None, None]
    o = mesh_obj('Rosee', verts.reshape(-1, 3), faces.reshape(-1, 3))
    m = mat('Goutte', (1, 1, 1), rough=0.1, transmission_weight=1.0, IOR=1.33)
    assign(o, m)
    return o


def ground(color_near=(0.035, 0.11, 0.015), color_far=(0.20, 0.22, 0.10), size=900, haze=(25, 260)):
    """Sol sous les brins, jusqu'à l'horizon : il se fond dans le ciel photographié au loin."""
    bpy.ops.mesh.primitive_plane_add(size=size)
    o = bpy.context.object
    o.name = 'Sol'
    m = mat('Sol', color_near, rough=0.9)
    nt = m.node_tree
    b = bsdf(m)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 60
    noise.inputs['Detail'].default_value = 5
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    var = nt.nodes.new('ShaderNodeValToRGB')
    var.color_ramp.elements[0].color = (*[c * 0.7 for c in color_near], 1)
    var.color_ramp.elements[1].color = (*[c * 1.5 for c in color_near], 1)
    nt.links.new(noise.outputs['Fac'], var.inputs[0])
    ln = nt.nodes.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    nt.links.new(tc.outputs['Object'], ln.inputs[0])
    far = nt.nodes.new('ShaderNodeMapRange')
    far.inputs['From Min'].default_value = haze[0]
    far.inputs['From Max'].default_value = haze[1]
    nt.links.new(ln.outputs['Value'], far.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['B'].default_value = (*color_far, 1)
    nt.links.new(far.outputs[0], mix.inputs['Factor'])
    nt.links.new(var.outputs[0], mix.inputs['A'])
    nt.links.new(mix.outputs['Result'], b.inputs['Base Color'])
    assign(o, m)
    return o


# ---------------------------------------------------------------- image
def bloom(strength=0.3, threshold=1.2, size=0.55):
    """Halo doux autour des hautes lumières (soleil rasant, rosée), appliqué après le rendu."""
    sc = bpy.context.scene
    sc.render.compositor_device = 'CPU'  # pas de carte graphique ici
    ng = bpy.data.node_groups.new('Finition', 'CompositorNodeTree')
    sc.compositing_node_group = ng
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    rl = ng.nodes.new('CompositorNodeRLayers')
    rl.scene = sc
    gl = ng.nodes.new('CompositorNodeGlare')
    for name in ('Bloom', 'BLOOM'):
        try:
            gl.inputs['Type'].default_value = name
            break
        except TypeError:
            pass
    gl.inputs['Threshold'].default_value = threshold
    gl.inputs['Strength'].default_value = strength
    gl.inputs['Size'].default_value = size
    out = ng.nodes.new('NodeGroupOutput')
    ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
    ng.links.new(gl.outputs['Image'], out.inputs['Image'])
