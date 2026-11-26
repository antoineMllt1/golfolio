# Le joueur habillé, d'après les photos d'Antoine : corps anatomique (human.py), haut blanc à manches
# longues porté sorti, chino beige, baskets blanches, gant blanc à la main gauche, casquette marine et
# cheveux bruns ondulés qui rebiquent dessous. Jamais montré de face : de dos, à contre-jour ou flou.
#
# Tout est construit dans le repère du modèle (regard −Y, gauche +X) puis amené dans la scène
# (regard +X, pied gauche à l'origine).
import math

import bmesh
import bpy
import numpy as np

import human
import parts as P

SOLE = 0.022  # épaisseur de semelle sous le pied


# ---------------------------------------------------------------- formes
def spline(pts, per_seg):
    """Courbe de Catmull-Rom passant par pts. Renvoie les points et leur paramètre."""
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


def sweep(name, pts, radii, around=16, per_seg=6, up=(0, 0, 1)):
    """Tube à section elliptique le long d'une courbe. radii : un rayon ou (largeur, épaisseur) par point."""
    path, u = spline(pts, per_seg)
    r = np.asarray(radii, dtype=float)
    if r.ndim == 1:
        r = np.stack([r, r], axis=1)
    k = np.arange(len(pts))
    rx, ry = np.interp(u, k, r[:, 0]), np.interp(u, k, r[:, 1])
    tan = np.gradient(path, axis=0)
    tan /= np.linalg.norm(tan, axis=1)[:, None]
    m = len(path)
    nrm = np.zeros((m, 3))
    ref = np.asarray(up, dtype=float)
    v = ref - tan[0] * (ref @ tan[0])
    if np.linalg.norm(v) < 1e-4:
        v = np.array([1.0, 0, 0]) - tan[0] * tan[0][0]
    nrm[0] = v / np.linalg.norm(v)
    for i in range(1, m):
        v = nrm[i - 1] - tan[i] * (nrm[i - 1] @ tan[i])
        nrm[i] = v / np.linalg.norm(v)
    bin_ = np.cross(tan, nrm)
    th = np.linspace(0, 2 * math.pi, around, endpoint=False)
    verts = path[:, None, :] + nrm[:, None, :] * (rx[:, None] * np.cos(th)[None])[:, :, None] + bin_[:, None, :] * (ry[:, None] * np.sin(th)[None])[:, :, None]
    i = np.arange(m - 1)[:, None]
    j = np.arange(around)[None]
    j2 = (j + 1) % around
    faces = np.stack([i * around + j, i * around + j2, (i + 1) * around + j2, (i + 1) * around + j], axis=-1)
    return P.mesh_obj(name, verts.reshape(-1, 3), faces.reshape(-1, 4))


def vertex_normals(verts, faces):
    n = np.zeros_like(verts)
    fn = np.cross(verts[faces[:, 1]] - verts[faces[:, 0]], verts[faces[:, 2]] - verts[faces[:, 0]]) + np.cross(verts[faces[:, 2]] - verts[faces[:, 0]], verts[faces[:, 3]] - verts[faces[:, 0]])
    for k in range(4):
        np.add.at(n, faces[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def smooth(verts, faces, iterations, factor=0.5):
    """Lissage laplacien : efface le détail anatomique sous le tissu."""
    n = len(verts)
    edges = np.concatenate([faces[:, [k, (k + 1) % 4]] for k in range(4)])
    edges = np.unique(np.sort(edges, axis=1), axis=0)
    deg = np.zeros(n)
    np.add.at(deg, edges[:, 0], 1)
    np.add.at(deg, edges[:, 1], 1)
    v = verts.copy()
    for _ in range(iterations):
        acc = np.zeros_like(v)
        np.add.at(acc, edges[:, 0], v[edges[:, 1]])
        np.add.at(acc, edges[:, 1], v[edges[:, 0]])
        v += factor * (acc / np.maximum(deg, 1)[:, None] - v)
    return v


# ---------------------------------------------------------------- matières
def fabric(name, color, rough=0.9, sheen=0.35, glow=0.0, weave=1400.0):
    m = P.mat(name, color, rough=rough, sheen_weight=sheen, sheen_roughness=0.5)
    nt = m.node_tree
    b = P.bsdf(m)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    noise = nt.nodes.new('ShaderNodeTexNoise')  # grain du tissu
    noise.inputs['Scale'].default_value = weave
    noise.inputs['Detail'].default_value = 3
    nt.links.new(tc.outputs['Object'], noise.inputs['Vector'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.25
    bump.inputs['Distance'].default_value = 0.0004
    nt.links.new(noise.outputs['Fac'], bump.inputs['Height'])
    nt.links.new(bump.outputs[0], b.inputs['Normal'])
    if glow:  # le coton fin laisse passer un peu de lumière à contre-jour
        tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
        tr.inputs['Color'].default_value = (*color, 1)
        mix = nt.nodes.new('ShaderNodeMixShader')
        mix.inputs[0].default_value = glow
        nt.links.new(b.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return m


def materials():
    hair = bpy.data.materials.new('Cheveux')
    hair.use_nodes = True
    nt = hair.node_tree
    h = nt.nodes.new('ShaderNodeBsdfHairPrincipled')
    h.parametrization = 'MELANIN'
    h.inputs['Melanin'].default_value = 0.78
    h.inputs['Melanin Redness'].default_value = 0.55
    h.inputs['Roughness'].default_value = 0.32
    h.inputs['Radial Roughness'].default_value = 0.45
    h.inputs['Random Color'].default_value = 0.25
    nt.links.new(h.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
    return dict(
        top=fabric('Haut blanc', (0.80, 0.80, 0.78), glow=0.18),
        chino=fabric('Chino beige', (0.50, 0.43, 0.32), rough=0.85, sheen=0.25, weave=1000),
        cap=fabric('Casquette marine', (0.010, 0.015, 0.040), rough=0.8, weave=900),
        skin=P.mat('Peau', (0.60, 0.40, 0.30), rough=0.48, subsurface_weight=0.5, subsurface_radius=(0.012, 0.006, 0.004), subsurface_scale=1.0),
        hair=hair,
        scalp=P.mat('Cheveux, dessous', (0.045, 0.026, 0.014), rough=0.7),
        shoe=P.mat('Basket', (0.82, 0.82, 0.80), rough=0.5),
        sole=P.mat('Semelle gomme', (0.66, 0.60, 0.48), rough=0.7),
        glove=P.mat('Gant', (0.84, 0.84, 0.82), rough=0.55, sheen_weight=0.2),
        steel=P.mat('Acier', (0.72, 0.73, 0.75), rough=0.18, metal=1.0),
        grip=P.mat('Grip', (0.02, 0.02, 0.022), rough=0.8),
    )


# ---------------------------------------------------------------- régions du corps
def group_of(label):
    base = label.split('.')[0]
    if base.startswith('toe') or base == 'foot':
        return 'foot'
    if base.startswith(('pelvis', 'upperleg', 'lowerleg')):
        return 'leg'
    if base.startswith(('root', 'spine', 'breast')):
        return 'torso'
    if base.startswith(('clavicle', 'shoulder', 'upperarm', 'lowerarm')):
        return 'arm'
    if base.startswith(('wrist', 'finger', 'metacarpal')):
        return 'hand'
    return 'head'


def submesh(verts, faces, mask):
    keep = mask[faces].all(axis=1)
    f = faces[keep]
    used = np.unique(f)
    remap = -np.ones(len(verts), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return used, remap[f]


# ---------------------------------------------------------------- le joueur
def golfer_finish(location=(0, 0, 0), yaw=0.0):
    """Le joueur au finish, tel qu'on le voit de dos. Renvoie le vide parent."""
    M = materials()
    body = human.Body()
    # Deux passes : la seconde pose la pointe de la chaussure droite exactement au sol.
    vm, marks = human.finish_pose(body)
    lab = np.array(body.labels)[body.bone_idx[np.arange(len(vm)), body.bone_w.argmax(axis=1)]]
    grp = np.array([group_of(l) for l in lab])
    side_r = np.array([l.endswith('.R') for l in lab])
    tip = vm[(grp == 'foot') & side_r][:, 2].min()
    vm, marks = human.finish_pose(body, trail_ankle=0.235 - tip - 0.004)
    origin = marks['left_foot']

    def scene(p):
        return human.to_scene(p, origin) + [0, 0, SOLE]

    rest, faces = body.verts, body.faces
    z = rest[:, 2]
    hip, neck, ankle = body.head('upperleg01.L')[2], body.head('neck01')[2], body.head('foot.L')[2]
    chest = body.head('spine01')[2]
    hem, waist, collar, cuff = hip - 0.085, hip + 0.085, neck + 0.012, ankle + 0.035
    # Poignets : la manche s'arrête un peu avant la main.
    near_wrist = np.zeros(len(rest), dtype=bool)
    along_arm = np.zeros(len(rest))
    for s in 'LR':
        sh, el, wr = body.head(f'upperarm01.{s}'), body.head(f'lowerarm01.{s}'), body.head(f'wrist.{s}')
        fore = np.array([l.startswith('lowerarm') and l.endswith(s) for l in lab])
        t = ((rest - el) @ (wr - el)) / ((wr - el) @ (wr - el))
        near_wrist |= fore & (t > 0.90)
        arm_side = (grp == 'arm') & np.array([l.endswith(s) for l in lab])
        along_arm[arm_side] = np.clip(((rest[arm_side] - sh) @ (wr - sh)) / ((wr - sh) @ (wr - sh)), 0, 1)
    trousers = (((grp == 'leg') & (z > cuff)) | (grp == 'torso')) & (z < waist)
    shirt = (((grp == 'torso') | (grp == 'leg')) & (z > hem) & (z < collar)) | ((grp == 'arm') & ~near_wrist)
    nrm = vertex_normals(vm, faces)
    root = P.link(bpy.data.objects.new('Joueur', None))

    def garment(name, mask, offset, iterations, material):
        used, f = submesh(vm, faces, mask)
        v = vm[used] + nrm[used] * offset[used][:, None]
        v = smooth(v, f, iterations)
        # Le tissu ne rentre jamais dans le corps.
        gap = np.einsum('ij,ij->i', v - vm[used], nrm[used])
        v += nrm[used] * np.clip(0.006 - gap, 0, None)[:, None]
        o = P.mesh_obj(name, scene(v), f)
        P.assign(o, material)
        sub = o.modifiers.new('Lisse', 'SUBSURF')
        sub.levels = sub.render_levels = 1
        o.parent = root
        return o

    loose = np.clip((chest - z) / (chest - hem), 0, 1)
    shirt_off = np.where(grp == 'arm', 0.010 + 0.012 * along_arm, 0.010 + 0.022 * loose)
    garment('Haut', shirt, shirt_off, 5, M['top'])
    leg_off = np.interp(z, [cuff, 0.50, hip, waist], [0.042, 0.026, 0.014, 0.009])
    garment('Chino', trousers, leg_off, 7, M['chino'])

    # Peau : seulement ce qui dépasse des vêtements (tête, cou, mains).
    covered = shirt | trousers | (grp == 'foot')
    visible = ~covered[faces].all(axis=1)
    f_skin = faces[visible]
    skin = P.mesh_obj('Peau', scene(vm), f_skin)
    left_hand = (grp == 'hand') & ~side_r
    P.assign(skin, M['skin'], M['glove'])
    skin.data.polygons.foreach_set('material_index', left_hand[f_skin].all(axis=1).astype(np.int32))
    skin.parent = root

    R, H = body.solve()
    # Baskets : l'enveloppe du pied au repos, gonflée, avec une semelle plate ; elle suit l'os du pied.
    for s in 'LR':
        foot = (grp == 'foot') & (side_r if s == 'R' else ~side_r)
        bm = bmesh.new()
        for co in rest[foot]:
            bm.verts.new(co)
        hull = bmesh.ops.convex_hull(bm, input=bm.verts)
        bmesh.ops.delete(bm, geom=[g for g in hull['geom_interior'] if isinstance(g, bmesh.types.BMVert)], context='VERTS')
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        bm.normal_update()
        centre = rest[foot].mean(axis=0)
        for v in bm.verts:
            out = np.array(v.co) - centre
            out[2] = 0
            ln = np.linalg.norm(out)
            v.co = np.array(v.co) + (out / ln * 0.007 if ln > 1e-6 else 0)
            v.co.z = -SOLE if v.co.z < 0.022 else v.co.z + 0.008
        b = body.id[f'foot.{s}']
        for v in bm.verts:
            v.co = (R[b] @ (np.array(v.co) - body.heads[b]) + H[b]).tolist()
        me = bpy.data.meshes.new(f'Basket {s}')
        bm.to_mesh(me)
        bm.free()
        shoe = P.link(bpy.data.objects.new(f'Basket {s}', me))
        co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        me.vertices.foreach_set('co', scene(co.reshape(-1, 3)).astype(np.float32).ravel())
        me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
        P.assign(shoe, M['shoe'])
        sub = shoe.modifiers.new('Lisse', 'SUBSURF')
        sub.levels = sub.render_levels = 2
        shoe.parent = root

    # Tête : repère du crâne posé, pour la casquette et les cheveux.
    hb = body.id['head']
    skull = (grp == 'head') & (z > body.heads[hb][2] + 0.02)
    lo, hi = rest[skull].min(axis=0), rest[skull].max(axis=0)
    c_rest, (rx, ry, rz) = (lo + hi) / 2, (hi - lo) / 2

    def head_space(local):
        """Points donnés autour du centre du crâne (repère du modèle au repos) → scène."""
        return scene((np.asarray(local) + c_rest - body.heads[hb]) @ R[hb].T + H[hb])

    rng = np.random.default_rng(4)
    rim = 0.20 * rz  # hauteur du bord de la casquette au-dessus du centre du crâne

    def skull_point(phi, zz, extra=0.0):
        """Point du crâne à l'azimut phi (0 = nuque, ±π = visage) et à la hauteur zz."""
        phi, zz = np.broadcast_arrays(np.asarray(phi, float), np.asarray(zz, float))
        k = np.sqrt(np.clip(1 - (zz / rz) ** 2, 0.42, 1))
        return np.stack([(rx * k + extra) * np.sin(phi), (ry * k + extra) * np.cos(phi), zz], axis=-1)

    # Sous-couche sombre, pour qu'on ne voie pas la peau entre les mèches.
    seg, rings = 56, 22
    phi = np.linspace(-2.25, 2.25, seg)
    zz = np.linspace(rim + 0.01, -0.62 * rz, rings)
    grid = skull_point(phi[None, :], zz[:, None], 0.004)
    i = np.arange(rings - 1)[:, None]
    j = np.arange(seg - 1)[None]
    f = np.stack([i * seg + j, i * seg + j + 1, (i + 1) * seg + j + 1, (i + 1) * seg + j], axis=-1).reshape(-1, 4)
    under = P.mesh_obj('Cheveux, dessous', head_space(grid.reshape(-1, 3)), f)
    P.assign(under, M['scalp'])
    under.parent = root

    # Mèches : chacune est un faisceau de cheveux qui descend le long du crâne puis rebique.
    n_locks, per_lock, n_pts = 150, 42, 12
    s = np.linspace(0, 1, n_pts)
    pos, rad = [], []
    for _ in range(n_locks):
        a = (rng.random() * 2 - 1) * 2.2
        back = 1 - min(abs(a) / 2.2, 1)  # 1 sur la nuque, 0 vers les tempes
        z0 = rim + 0.012 - rng.random() * (0.10 + 0.45 * back) * rz
        length = (0.055 + 0.050 * back) * (0.75 + 0.5 * rng.random())
        flick = 0.5 + 0.8 * rng.random()
        w1, w2 = rng.random(2) * 6.28
        down = z0 - length * s * (1 - 0.42 * flick * s * s)
        out = 0.003 + 0.030 * flick * s**2.3 + 0.004 * np.sin(2 * math.pi * 1.4 * s + w1)
        wave = (0.010 * np.sin(2 * math.pi * 1.2 * s + w2) * s) / max(rx, ry)
        centre = skull_point(a + wave, down, out)
        for _ in range(per_lock):
            jitter = rng.normal(0, 1, 3) * 0.0028
            spread = rng.normal(0, 1, 3) * 0.0045
            pos.append(centre + jitter[None] + spread[None] * s[:, None])
            rad.append(0.00011 * (1 - 0.75 * s))
    pos = head_space(np.concatenate(pos))
    curves = bpy.data.hair_curves.new('Cheveux')
    curves.add_curves([n_pts] * (n_locks * per_lock))
    curves.attributes['position'].data.foreach_set('vector', pos.astype(np.float32).ravel())
    (curves.attributes.get('radius') or curves.attributes.new('radius', 'FLOAT', 'POINT')).data.foreach_set('value', np.concatenate(rad).astype(np.float32))
    curves.materials.append(M['hair'])
    hair = P.link(bpy.data.objects.new('Cheveux', curves))
    hair.parent = root

    # Casquette : calotte, visière vers l'avant (cachée de dos), bouton.
    seg, rings = 48, 16
    phi = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    lat = np.linspace(0, math.pi / 2, rings)
    top = rz + 0.012 - rim
    dome = np.stack([(rx + 0.011) * np.cos(lat)[:, None] * np.sin(phi)[None], (ry + 0.011) * np.cos(lat)[:, None] * np.cos(phi)[None], rim + top * np.sin(lat)[:, None] * np.ones(seg)[None]], axis=-1)
    i = np.arange(rings - 1)[:, None]
    j = np.arange(seg)[None]
    j2 = (j + 1) % seg
    f = np.stack([i * seg + j, i * seg + j2, (i + 1) * seg + j2, (i + 1) * seg + j], axis=-1).reshape(-1, 4)
    cap = P.mesh_obj('Casquette', head_space(dome.reshape(-1, 3)), f)
    P.assign(cap, M['cap'])
    cap.parent = root
    ang = np.linspace(-1.0, 1.0, 21)
    reach = np.linspace(0.0, 1.0, 7)
    bv = np.zeros((len(reach), len(ang), 3))
    for ai, a in enumerate(ang):
        for ri, r in enumerate(reach):
            far = 0.078 * (1 - 0.55 * a * a) * r
            bv[ri, ai] = [(rx + 0.010 + far * 0.5) * math.sin(a), -(ry + 0.010 + far) * math.cos(a), rim + 0.004 - 0.020 * r - 0.012 * a * a]
    i = np.arange(len(reach) - 1)[:, None]
    jj = np.arange(len(ang) - 1)[None]
    f = np.stack([i * len(ang) + jj, i * len(ang) + jj + 1, (i + 1) * len(ang) + jj + 1, (i + 1) * len(ang) + jj], axis=-1).reshape(-1, 4)
    brim = P.mesh_obj('Visiere', head_space(bv.reshape(-1, 3)), f)
    P.assign(brim, M['cap'])
    brim.modifiers.new('Epaisseur', 'SOLIDIFY').thickness = 0.004
    brim.parent = root

    # Le fer, en travers derrière la nuque.
    grip = scene(marks['grip'])[0]
    d = (scene(marks['grip'] + marks['club']) - scene(marks['grip']))[0]
    butt, tip = grip - d * 0.10, grip + d * 0.84
    for name, a, b, r, mat_ in (('Grip', butt, grip + d * 0.16, (0.0125, 0.0105), M['grip']), ('Manche', grip + d * 0.16, tip, (0.0072, 0.0047), M['steel'])):
        o = sweep(name, [a, b], r, around=12, per_seg=4)
        P.assign(o, mat_)
        o.parent = root
    side = np.cross(d, [0, 0, 1])
    side /= np.linalg.norm(side)
    blade = d * 0.45 - np.array([0, 0, 1]) * 0.55 + side * 0.7
    blade /= np.linalg.norm(blade)
    o = sweep('Tete de fer', [tip - d * 0.01, tip + blade * 0.04, tip + blade * 0.085], [(0.011, 0.008), (0.024, 0.006), (0.027, 0.005)], around=14, per_seg=5, up=d)
    P.assign(o, M['steel'])
    o.parent = root

    root.location = location
    root.rotation_euler = (0, 0, yaw)
    return root
