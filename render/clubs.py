# Fers (long, 7, wedge) et putter, à l'échelle réelle. Même repère que parts.wood3 : origine au bas du
# centre de la face, la face regarde +X, le talon et le manche sont côté +Y, semelle à z = 0.
#
# Les têtes ne sont pas assemblées facette par facette : chacune est décrite par un champ de distance
# (plans, cylindres, congés de rayon choisi, en millimètres), puis maillée finement. Les normales viennent
# du champ lui-même : aucune facette, des arêtes adoucies qui accrochent la lumière.
#
#   python render/clubs.py -- --club fer7 --view dos --scale 50 --samples 32     # une vue de contrôle
#   python render/clubs.py -- --club tous --view toutes                          # la planche complète
import itertools
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import parts as P  # noqa: E402

V = Vector


# ---------------------------------------------------------------- champs de distance
def _rmax(a, b, r):
    """Intersection de deux volumes (distances négatives dedans), arête arrondie au rayon r."""
    return np.hypot(np.maximum(a + r, 0), np.maximum(b + r, 0)) + np.minimum(np.maximum(a, b) + r, 0) - r


def _rmin(a, b, r):
    """Réunion de deux volumes, raccordés par un congé de rayon r."""
    return -_rmax(-a, -b, r)


def _rmax_n(ds, r):
    """Intersection de plusieurs volumes, toutes les arêtes arrondies au même rayon."""
    s, m = 0.0, -np.inf
    for d in ds:
        s = s + np.maximum(d + r, 0) ** 2
        m = np.maximum(m, d)
    return np.sqrt(s) + np.minimum(m + r, 0) - r


def _step(a, b, t):
    """Passage doux de 0 à 1 quand t va de a à b."""
    u = np.clip((t - a) / (b - a), 0, 1)
    return u * u * (3 - 2 * u)


def _eval(f, pts, chunk=1_500_000):
    out = np.empty(len(pts), dtype=np.float32)
    for s in range(0, len(pts), chunk):
        out[s : s + chunk] = f(pts[s : s + chunk])
    return out


def _mesh_field(f, lo, hi, h, coarse=4):
    """Surface f = 0 d'un champ de distance, maillée en quadrilatères de côté h (un sommet par cellule
    traversée, ramené sur la surface exacte). Renvoie sommets, faces et normales du champ."""
    lo = np.asarray(lo, dtype=np.float64)
    big = h * coarse
    nc = np.ceil((np.asarray(hi) - lo) / big).astype(int) + 1
    axes = [lo[k] + big * np.arange(nc[k]) for k in range(3)]
    grid = np.stack(np.meshgrid(*axes, indexing='ij'), axis=-1).reshape(-1, 3)
    dc = _eval(f, grid.astype(np.float32)).reshape(nc)
    # Le champ n'est calculé finement que dans les grosses cellules proches de la surface.
    near = np.abs(dc) < 1.5 * 1.7321 * big
    cell = np.zeros(nc - 1, dtype=bool)
    corners = list(itertools.product((0, 1), repeat=3))
    for dx, dy, dz in corners:
        cell |= near[dx : dx + nc[0] - 1, dy : dy + nc[1] - 1, dz : dz + nc[2] - 1]

    def up(a):
        return a.repeat(coarse, 0).repeat(coarse, 1).repeat(coarse, 2)

    d = up(dc[:-1, :-1, :-1])
    ijk = np.argwhere(up(cell))
    d[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = _eval(f, (lo + ijk * h).astype(np.float32))
    del ijk

    inside = d < 0
    nx, ny, nz = d.shape
    count = np.zeros((nx - 1, ny - 1, nz - 1), dtype=np.uint8)
    for dx, dy, dz in corners:
        count += inside[dx : dx + nx - 1, dy : dy + ny - 1, dz : dz + nz - 1]
    active = (count > 0) & (count < 8)
    del count
    cells = np.argwhere(active)
    index = np.full(active.shape, -1, dtype=np.int32)
    index[active] = np.arange(len(cells), dtype=np.int32)

    # Un sommet par cellule : la moyenne des points où la surface coupe ses arêtes.
    corner = np.array(corners)
    val = np.stack([d[cells[:, 0] + c[0], cells[:, 1] + c[1], cells[:, 2] + c[2]] for c in corner], axis=1).astype(np.float64)
    acc = np.zeros((len(cells), 3))
    num = np.zeros(len(cells))
    for a in range(8):
        for b in range(a + 1, 8):
            if np.abs(corner[a] - corner[b]).sum() != 1:
                continue
            va, vb = val[:, a], val[:, b]
            cross = (va < 0) != (vb < 0)
            t = np.where(cross, va / np.where(cross, va - vb, 1.0), 0.0)
            acc += cross[:, None] * (corner[a] + t[:, None] * (corner[b] - corner[a]))
            num += cross
    centre = lo + (cells + 0.5) * h
    v = lo + (cells + acc / num[:, None]) * h

    # Une face par arête de la grille traversée : elle relie les quatre cellules qui la touchent.
    quads = []
    for ax in range(3):
        a1, a2 = (ax + 1) % 3, (ax + 2) % 3
        sa, sb = [slice(1, -1)] * 3, [slice(1, -1)] * 3
        sa[ax], sb[ax] = slice(0, -1), slice(1, None)
        first = inside[tuple(sa)]
        e = np.argwhere(first != inside[tuple(sb)])
        flip = ~first[e[:, 0], e[:, 1], e[:, 2]]

        def at(d1, d2):
            c = e.copy()
            c[:, a1] += d1
            c[:, a2] += d2
            return index[c[:, 0], c[:, 1], c[:, 2]]

        q = np.stack([at(0, 0), at(1, 0), at(1, 1), at(0, 1)], axis=1)
        q[flip] = q[flip][:, ::-1]
        quads.append(q)
    quads = np.concatenate(quads)

    def grad(p, eps=0.02):
        g = np.empty_like(p)
        for k in range(3):
            dp = np.zeros(3)
            dp[k] = eps
            g[:, k] = (f(p + dp) - f(p - dp)) / (2 * eps)
        return g

    # Les sommets sont ramenés sur la surface exacte, sans quitter leur cellule.
    for _ in range(3):
        g = grad(v)
        v = v - (f(v) / np.maximum((g * g).sum(axis=1), 1e-9))[:, None] * g
        v = np.clip(v, centre - 0.7 * h, centre + 0.7 * h)
    n = grad(v)
    n /= np.maximum(np.linalg.norm(n, axis=1), 1e-9)[:, None]
    return v, quads, n


def _field_obj(name, f, lo, hi, h, to_world, attribute=None, offset=(0.0, 0.0, 0.0)):
    """Objet Blender à partir d'un champ exprimé en millimètres. `to_world` : matrice 3×3 du repère du
    champ vers celui du club, puis décalage `offset` (mm). `attribute` : nom d'un attribut qui garde
    les coordonnées du champ, pour les matières."""
    v, quads, n = _mesh_field(f, lo, hi, h)
    o = P.mesh_obj(name, (v @ to_world.T + np.asarray(offset)) * 0.001, quads)
    me = o.data
    if attribute:
        me.attributes.new(attribute, 'FLOAT_VECTOR', 'POINT').data.foreach_set('vector', v.astype(np.float32).ravel())
    if len(me.vertices) == len(n):  # les normales exactes du champ, plutôt que celles des facettes
        me.normals_split_custom_set_from_vertices((n @ to_world.T).astype(np.float32))
    return o


# ---------------------------------------------------------------- fers
# Cotes en millimètres et en degrés. H : hauteur de la face en son centre, mesurée le long de la face.
IRONS = {
    'long': dict(loft=21.0, lie=60.5, H=39.5, tau=12.5, t_top=6.3, sole=19.5, x_low=-10.0, camber=50.0, offset=3.3, r_b=15.0, pitch=2.6, groove=0.62, s_top=57.0, lead=2.0, rough=0.30, brushing=0.05, tone=1.0, length=978.0, first_step=265.0),
    'fer7': dict(loft=33.0, lie=62.5, H=42.0, tau=14.0, t_top=5.6, sole=17.5, x_low=-9.0, camber=45.0, offset=2.6, r_b=16.5, pitch=2.6, groove=0.62, s_top=56.0, lead=2.0, rough=0.30, brushing=0.05, tone=1.0, length=940.0, first_step=240.0),
    'wedge': dict(loft=56.0, lie=64.0, H=47.5, tau=15.5, t_top=5.2, sole=21.5, x_low=-14.0, camber=40.0, offset=1.3, r_b=20.0, pitch=2.5, groove=0.60, s_top=60.0, lead=2.2, rough=0.42, brushing=0.14, tone=0.86, length=895.0, first_step=215.0),
}
HOSEL_R = 6.6  # rayon extérieur du hosel
HOSEL_Y = 36.5  # où l'axe du manche perce le sol, côté talon
TOE_Q, TOE_R = -39.5, 42.0  # pointe : abscisse du point le plus éloigné, rayon du contour
SCORE = 25.5  # demi-longueur des stries
T_FLOOR, T_INSERT = 2.9, 1.5  # épaisseur de la paroi derrière la face, épaisseur de l'insert
DRAFT = math.tan(math.radians(12))  # dépouille des parois de la cavité


def _iron_fields(S):
    """Champs de la tête et de l'insert d'un fer, dans le repère de la face : p vers l'avant (la face
    est le plan p = 0), q vers le talon, r vers le haut le long de la face."""
    L, lie, tau = (math.radians(S[k]) for k in ('loft', 'lie', 'tau'))
    cL, sL, cl, sl, tt, ct = math.cos(L), math.sin(L), math.cos(lie), math.sin(lie), math.tan(tau), math.cos(tau)
    H, t_top, sole = S['H'], S['t_top'], S['sole']
    toe_h = H - TOE_Q * tt  # hauteur du haut de la pointe
    r_w = 0.62 * toe_h  # hauteur du point le plus éloigné de la pointe
    z_neck = (H - 40.0 * tt) * cL  # hauteur où le bord supérieur rejoint le hosel
    heel_cut = math.radians(45.0 + 0.57 * (S['loft'] - 21.0))  # pan coupé qui termine la lame côté talon
    geo = {'x_h': -HOSEL_R, 'web': 7.5}  # axe du hosel et rayon du raccord, calés plus bas sur la lame
    # Le muscle : du bord de fuite de la semelle au bas de la cavité, en deux pans.
    t_pt = np.array([-sole, 0.0])
    b_pt = np.array([-t_top * cL - S['r_b'] * sL, -t_top * sL + S['r_b'] * cL])
    way = (b_pt - t_pt) / np.linalg.norm(b_pt - t_pt)
    out = np.array([-way[1], way[0]])
    m_pt = (t_pt + b_pt) / 2 + 1.1 * out

    def plane(a, b):
        d = (b - a) / np.linalg.norm(b - a)
        return a, np.array([-d[1], d[0]])

    (a1, n1), (a2, n2) = plane(t_pt, m_pt), plane(m_pt, b_pt)
    # La cavité : sous le bord supérieur, en retrait de la pointe, au-dessus du muscle, avant le talon.
    w_top, w_toe, r_cb, q_ch = 4.2, 5.2, S['r_b'] + 1.6, 20.0
    ch = math.radians(72)
    screws = [(TOE_Q + w_toe + 7.0, r_cb + 0.5 * (toe_h - 9.0 - r_cb)), (q_ch - 4.5, r_cb + 0.5 * (H - (q_ch - 4.5) * tt - w_top / ct - r_cb))]

    def frame(pt):
        p, q, r = pt[:, 0], pt[:, 1], pt[:, 2]
        return p, q, r, p * cL - r * sL, p * sL + r * cL

    def outline(q, r):
        d_top = (r - H + q * tt) * ct
        d_toe = np.hypot(q - (TOE_Q + TOE_R), r - r_w) - TOE_R
        return d_top, d_toe

    def cavity(p, q, r, d_top, d_toe):
        c = _rmax_n([d_top + w_top, d_toe + w_toe, r_cb - r, (q - q_ch) * math.sin(ch) - (r - r_cb) * math.cos(ch)], 3.5)
        return c + (p + t_top) * DRAFT

    def head(pt):
        p, q, r, x, z = frame(pt)
        d_top, d_toe = outline(q, r)
        dy = q - HOSEL_Y
        side = dy * sl - z * cl  # distance au plan de l'axe du manche, comptée vers le talon
        # La semelle, bombée dans les deux sens. Le dernier arrondi la remonte un peu : on la descend d'autant.
        d_sole = (x - S['x_low']) ** 2 / (2 * S['camber']) + q * q / 600.0 - z - 0.29 * S['lead']
        # Le tour de la lame : bord supérieur, pointe, semelle et, côté talon, un pan coupé qui ramène
        # le dos vers le hosel (il passe par son axe : le raccord s'y fait à angle franc).
        cut = -(x - geo['x_h']) * math.cos(heel_cut) + side * math.sin(heel_cut)
        rim = _rmax(_rmax(d_top, d_toe, 11.0), _rmax(d_sole, cut, 8.0), 10.0 - 5.0 * _step(0, 30, q))
        # Le dos : une lame d'épaisseur constante, épaissie en bas par le muscle.
        xm = x - (sole - 13.0) * _step(12, 38, q)
        muscle = _rmax((xm - a1[0]) * n1[0] + (z - a1[1]) * n1[1], (xm - a2[0]) * n2[0] + (z - a2[1]) * n2[1], 2.5)
        back = _rmin(-(p + t_top), muscle, 1.2)
        # Arêtes nettes mais adoucies ; elles s'arrondissent en approchant du hosel, où la lame se fond.
        melt = _step(26, 40, q)
        blade = _rmax(back, rim, 1.2 + 3.0 * _step(-26, -36, q) * (1 - _step(8, 18, z)) + 4.0 * melt)
        blade = _rmax(blade, p, 0.7 + 3.3 * melt)  # la face, plane
        # Le hosel : un cylindre incliné de l'angle de lie. Plus la face est couchée, plus la lame passe
        # loin derrière lui : le congé qui les raccorde s'élargit en montant vers le bord supérieur.
        hosel = _rmax(np.hypot(x - geo['x_h'], side) - HOSEL_R, dy * cl + z * sl - S['s_top'], 0.25)
        d = _rmin(blade, hosel, 5.5 + (geo['web'] - 5.5) * _step(6.0, z_neck, z))
        # La cavité creusée dans le dos.
        pocket = _rmax(cavity(p, q, r, d_top, d_toe), p + T_FLOOR, 0.7)
        d = _rmax(d, -pocket, 0.45)
        # Le dessous, taillé d'un seul geste : bord d'attaque arrondi, talon relevé et roulé sous le hosel.
        under = _rmax(d_sole, side - (HOSEL_R + 0.6), 15.0)
        return _rmax(d, under, S['lead'] + 7.0 * _step(30, 41, q))

    def insert(pt):
        p, q, r, x, z = frame(pt)
        d_top, d_toe = outline(q, r)
        top = -(p + T_FLOOR + T_INSERT)
        d = _rmax(cavity(p, q, r, d_top, d_toe) + 0.15, top, 0.45)
        d = np.maximum(d, p + T_FLOOR - 0.3)
        for qs, rs in screws:  # lamage de chaque vis
            d = _rmax(d, -_rmax(np.hypot(q - qs, r - rs) - 2.15, p + T_FLOOR + T_INSERT - 0.6, 0.12), 0.18)
        return d

    to_world = np.array([[cL, 0, -sL], [0, 1, 0], [sL, 0, cL]])
    # Le bord d'attaque arrondi recule un peu derrière l'origine : on le mesure, puis on place l'axe du
    # hosel d'après lui (offset = avance du hosel sur le bord d'attaque).
    xs, zs = np.meshgrid(np.arange(-8.0, 1.0, 0.05), np.arange(0.0, 6.0, 0.05))
    probe = np.stack([xs.ravel(), np.zeros(xs.size), zs.ravel()], axis=1)
    lead_x = probe[head(probe @ to_world) < 0, 0].max()
    geo['x_h'] = lead_x + S['offset'] - HOSEL_R
    # Écart entre le dos du hosel et la face, à la hauteur où le bord supérieur le rejoint.
    gap = (geo['x_h'] - HOSEL_R) + z_neck * sL / cL
    geo['web'] = float(np.clip(gap + 6.0, 9.0, 20.0))
    return dict(head=head, insert=insert, to_world=to_world, screws=screws, x_h=geo['x_h'], r_cb=r_cb, toe_h=toe_h, trig=(cL, sL, cl, sl))


class _Net:
    """Câblage d'une matière : des nœuds de calcul enchaînés, les nombres posés directement sur les entrées."""

    def __init__(self, material):
        self.nt = material.node_tree
        self.bsdf = P.bsdf(material)

    def node(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def put(self, socket, value):
        if hasattr(value, 'is_linked'):
            self.nt.links.new(value, socket)
        else:
            socket.default_value = value

    def calc(self, op, a, b=None, c=None, clamp=False):
        n = self.node('ShaderNodeMath', operation=op, use_clamp=clamp)
        for k, v in enumerate((a, b, c)):
            if v is not None:
                self.put(n.inputs[k], v)
        return n.outputs[0]

    def ramp(self, value, lo, hi, out0=0.0, out1=1.0):
        """Passage doux de out0 à out1 quand la valeur va de lo à hi."""
        n = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP')
        for name, v in (('Value', value), ('From Min', lo), ('From Max', hi), ('To Min', out0), ('To Max', out1)):
            self.put(n.inputs[name], v)
        return n.outputs[0]

    def mix(self, factor, a, b):
        """Mélange de deux couleurs (triplets) ou de deux valeurs."""
        color = isinstance(a, tuple) or isinstance(b, tuple) or getattr(a, 'type', '') == 'RGBA' or getattr(b, 'type', '') == 'RGBA'
        n = self.node('ShaderNodeMix', data_type='RGBA' if color else 'FLOAT')
        ia, ib, out = (6, 7, 2) if color else (2, 3, 0)
        self.put(n.inputs[0], factor)
        for socket, v in ((n.inputs[ia], a), (n.inputs[ib], b)):
            self.put(socket, (*v, 1.0) if isinstance(v, tuple) else v)
        return n.outputs[out]

    def field(self, name='pqr'):
        """Les trois coordonnées du champ, gardées sur le maillage (en millimètres)."""
        att = self.node('ShaderNodeAttribute', attribute_name=name)
        sep = self.node('ShaderNodeSeparateXYZ')
        self.nt.links.new(att.outputs['Vector'], sep.inputs[0])
        return att.outputs['Vector'], sep.outputs[0], sep.outputs[1], sep.outputs[2]

    def streaks(self, vector, scale, detail=3.0):
        """Bruit étiré : les fines traces du brossage."""
        mul = self.node('ShaderNodeVectorMath', operation='MULTIPLY')
        self.nt.links.new(vector, mul.inputs[0])
        mul.inputs[1].default_value = scale
        tex = self.node('ShaderNodeTexNoise')
        self.nt.links.new(mul.outputs[0], tex.inputs['Vector'])
        tex.inputs['Scale'].default_value = 1.0
        tex.inputs['Detail'].default_value = detail
        return tex.outputs[0]

    def brushed(self, amount, axis=(0.0, 1.0, 0.0)):
        """Reflets étirés en travers du brossage (qui suit `axis`, dans le repère du club). L'effet
        s'efface là où la surface regarde le long de l'axe, où il n'a plus de sens."""
        tr = self.node('ShaderNodeVectorTransform', vector_type='VECTOR', convert_from='OBJECT', convert_to='WORLD')
        tr.inputs['Vector'].default_value = axis
        geo = self.node('ShaderNodeNewGeometry')
        dot = self.node('ShaderNodeVectorMath', operation='DOT_PRODUCT')
        self.nt.links.new(tr.outputs[0], dot.inputs[0])
        self.nt.links.new(geo.outputs['Normal'], dot.inputs[1])
        along = self.calc('MULTIPLY', dot.outputs['Value'], dot.outputs['Value'])
        self.put(self.bsdf.inputs['Anisotropic'], self.calc('MULTIPLY', self.calc('SUBTRACT', 1.0, along, clamp=True), amount, clamp=True))
        self.nt.links.new(tr.outputs[0], self.bsdf.inputs['Tangent'])

    def bump(self, height_mm, strength=1.0):
        n = self.node('ShaderNodeBump')
        n.inputs['Strength'].default_value = strength
        n.inputs['Distance'].default_value = 0.001
        self.put(n.inputs['Height'], height_mm)
        self.nt.links.new(n.outputs[0], self.bsdf.inputs['Normal'])


def _iron_steel(S, F, rows, r0):
    """Acier satiné de la tête. Sur la face : la zone de frappe sablée et les stries gravées."""
    m = P.mat('Acier', (0.60, 0.61, 0.62), rough=S['rough'], metal=1.0)
    N = _Net(m)
    vec, p, q, r = N.field()
    aq = N.calc('ABSOLUTE', q)
    face = N.calc('LESS_THAN', N.calc('ABSOLUTE', p), 0.03)
    zone = N.calc('MULTIPLY', face, N.ramp(aq, SCORE + 1.6, SCORE + 1.3, 0.0, 1.0))
    # Distance à la strie la plus proche : des traits horizontaux aux bouts arrondis.
    half = S['groove'] / 2
    row = N.calc('MINIMUM', N.calc('MAXIMUM', N.calc('ROUND', N.calc('DIVIDE', N.calc('SUBTRACT', r, r0), S['pitch'])), 0.0), rows - 1.0)
    dr = N.calc('SUBTRACT', r, N.calc('MULTIPLY_ADD', row, S['pitch'], r0))
    dq = N.calc('MAXIMUM', N.calc('SUBTRACT', aq, SCORE - half), 0.0)
    dist = N.calc('SQRT', N.calc('ADD', N.calc('MULTIPLY', dr, dr), N.calc('MULTIPLY', dq, dq)))
    groove = N.calc('MULTIPLY', face, N.ramp(dist, half + 0.10, half - 0.10))
    # Le brossage suit la longueur de la lame ; il s'efface sur le hosel, poli en rond.
    cL, sL, cl, sl = F['trig']
    x = N.calc('SUBTRACT', N.calc('MULTIPLY', p, cL), N.calc('MULTIPLY', r, sL))
    z = N.calc('ADD', N.calc('MULTIPLY', p, sL), N.calc('MULTIPLY', r, cL))
    side = N.calc('SUBTRACT', N.calc('MULTIPLY', N.calc('SUBTRACT', q, HOSEL_Y), sl), N.calc('MULTIPLY', z, cl))
    dx = N.calc('SUBTRACT', x, F['x_h'])
    radial = N.calc('SQRT', N.calc('ADD', N.calc('MULTIPLY', dx, dx), N.calc('MULTIPLY', side, side)))
    blade = N.ramp(radial, HOSEL_R + 0.5, HOSEL_R + 5.0)
    brushing = N.calc('MULTIPLY', blade, S['brushing'])
    grain = N.calc('SUBTRACT', N.streaks(vec, (4.0, 0.10, 4.0)), 0.5)
    wide = N.calc('SUBTRACT', N.streaks(vec, (0.5, 0.05, 0.5), detail=1.0), 0.5)
    rough = N.calc('ADD', N.calc('MULTIPLY_ADD', grain, brushing, S['rough']), N.calc('MULTIPLY', wide, 0.06))
    rough = N.mix(zone, rough, N.calc('MULTIPLY_ADD', grain, 0.05, 0.44))
    N.put(N.bsdf.inputs['Roughness'], N.mix(groove, rough, 0.62))
    tone = N.calc('MULTIPLY', N.calc('MULTIPLY_ADD', N.calc('MULTIPLY', grain, brushing), 0.6, 1.0), N.mix(zone, S['tone'], S['tone'] * 0.84))
    shade = N.calc('MULTIPLY', tone, N.mix(groove, 1.0, 0.22))
    col = N.node('ShaderNodeCombineColor')
    for k, c in enumerate((0.60, 0.61, 0.62)):
        N.put(col.inputs[k], N.calc('MULTIPLY', shade, c))
    N.nt.links.new(col.outputs[0], N.bsdf.inputs['Base Color'])
    N.bump(N.calc('MULTIPLY', groove, -0.30))
    N.brushed(N.calc('MULTIPLY', brushing, 3.0))
    return m


def _insert_black():
    """Insert noir mat, finement rainuré dans le sens de la longueur."""
    m = P.mat('Insert', (0.010, 0.010, 0.012), rough=0.52, specular_ior_level=0.35)
    N = _Net(m)
    vec, p, q, r = N.field()
    wave = N.calc('SINE', N.calc('MULTIPLY', r, 2 * math.pi / 0.42))
    N.bump(N.calc('MULTIPLY', wave, 0.012), strength=0.6)
    N.put(N.bsdf.inputs['Roughness'], N.calc('MULTIPLY_ADD', wave, 0.05, 0.52))
    return m


def _smooth_by_angle(o, degrees):
    for other in bpy.context.selected_objects:
        other.select_set(False)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.shade_smooth_by_angle(angle=math.radians(degrees))
    o.select_set(False)


def _screw(name, centre, normal, across):
    """Petite vis à tête cylindrique et empreinte six pans. `centre` : dessous de la tête, en mm ;
    `normal` : direction de la tête ; `across` : une direction du plan de pose."""
    hexa = [(math.cos(a), math.sin(a)) for a in (0.0, math.pi / 3, 2 * math.pi / 3)]

    def f(pt):
        x, y, z = pt[:, 0], pt[:, 1], pt[:, 2]
        d = _rmax(np.hypot(x, y) - 1.8, z - 0.55, 0.20)
        d = np.maximum(d, -0.3 - z)
        socket = np.maximum.reduce([np.abs(x * c + y * s) - 0.72 for c, s in hexa] + [-0.20 - z])
        return _rmax(d, -socket, 0.06)

    n = np.asarray(normal, dtype=float)
    a = np.asarray(across, dtype=float)
    basis = np.stack([a, np.cross(n, a), n], axis=1)
    o = _field_obj(name, f, [-2.1, -2.1, -0.45], [2.1, 2.1, 0.8], 0.05, basis, offset=centre)
    P.assign(o, P.mat('Vis', (0.72, 0.72, 0.74), rough=0.2, metal=1.0))
    return o


def _monogram(origin, right, up, height=0.004, text='AM'):
    """Le monogramme, à plat : `origin` son centre (mètres), `right` et `up` le sens de lecture."""
    cu = bpy.data.curves.new('Monogramme', 'FONT')
    cu.body = text
    cu.align_x, cu.align_y = 'CENTER', 'CENTER'
    font = '/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    tmp = bpy.data.objects.new('tmp', cu)
    me = bpy.data.meshes.new_from_object(tmp)
    bpy.data.objects.remove(tmp)
    co = np.zeros(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    lo, hi = co.min(axis=0), co.max(axis=0)
    flat = (co - (lo + hi) / 2) * (height / (hi[1] - lo[1]))
    world = np.asarray(origin)[None] + flat[:, 0:1] * np.asarray(right)[None] + flat[:, 1:2] * np.asarray(up)[None]
    me.vertices.foreach_set('co', world.astype(np.float32).ravel())
    me.update()
    o = P.link(bpy.data.objects.new('Monogramme', me))
    P.assign(o, P.mat('Gravure', (0.62, 0.63, 0.64), rough=0.30, metal=1.0))
    return o


def _shaft(prefix, s_top, length, first_step, lie, foot, ferrule=True, steps=9, spacing=41.0, butt=7.62):
    """Bague, manche en acier à paliers et grip, autour de l'axe du manche. Cotes en mm le long de
    l'axe, comptées depuis le sol ; `foot` : point où l'axe perce le sol (mm)."""
    tip = 4.70
    grow = (butt - tip) / steps
    prof = [(0.0, s_top + 1.0), (tip, s_top + 1.0)]
    for k in range(steps):
        s = first_step + spacing * k
        prof += [(tip + grow * k, s), (tip + grow * (k + 1), s + 1.6)]
    grip0 = length - 268.0
    prof += [(butt, grip0 + 5.0), (0.0, grip0 + 5.0)]
    parts = [P.lathe(prefix + 'Manche', [(r * 0.001, s * 0.001) for r, s in prof], 48)]
    P.assign(parts[0], P.mat('Chrome', (0.86, 0.86, 0.88), rough=0.07, metal=1.0))
    grip = [(butt + 0.2, grip0), (butt + 1.9, grip0 + 0.6), (butt + 2.6, grip0 + 3.0), (butt + 3.0, grip0 + 40.0), (butt + 5.2, length - 6.0), (butt + 5.0, length - 2.0), (butt + 3.6, length), (0.0, length)]
    parts.append(P.lathe(prefix + 'Grip', [(r * 0.001, s * 0.001) for r, s in grip], 48))
    P.assign(parts[1], P.mat('Grip', (0.012, 0.012, 0.013), rough=0.75))
    if ferrule:
        r0 = HOSEL_R - 0.02
        ring = [(tip - 0.3, s_top), (r0 - 0.15, s_top), (r0, s_top + 0.2), (r0, s_top + 3.2), (r0 - 0.25, s_top + 5.5), (5.75, s_top + 10.0), (5.15, s_top + 15.0), (4.95, s_top + 18.2), (4.80, s_top + 19.0), (tip - 0.05, s_top + 19.1)]
        parts.append(P.lathe(prefix + 'Bague', [(r * 0.001, s * 0.001) for r, s in ring], 64))
        P.assign(parts[2], P.mat('Bague', (0.010, 0.010, 0.011), rough=0.22, coat_weight=0.4, coat_roughness=0.08))
    for o in parts:
        _smooth_by_angle(o, 40)
        o.location = (foot[0] * 0.001, foot[1] * 0.001, 0.0)
        o.rotation_euler = (-(math.pi / 2 - math.radians(lie)), 0, 0)
    return parts


_FIELDS = {}  # champ de chaque club construit, pour distance()


def iron(loft=None, kind='fer7', detail=0.25, monogram=True):
    """Fer forgé à dos creusé, à l'adresse : tête en acier satiné, insert noir tenu par deux vis,
    hosel court, bague noire, manche en acier à paliers. kind : 'long', 'fer7' ou 'wedge' ; loft en
    degrés (celui du modèle si None) ; detail : pas du maillage en mm. Origine : bas du centre de la
    face ; la face regarde +X, le talon et le manche sont côté +Y, semelle à z = 0. Renvoie un vide
    parent, pour déplacer tout le club."""
    S = dict(IRONS[kind])
    if loft is not None:
        S['loft'] = float(loft)
    F = _iron_fields(S)
    W = F['to_world']
    lie = math.radians(S['lie'])
    # Boîte englobante dans le repère de la face : la lame, puis le haut du hosel.
    top = np.array([F['x_h'], HOSEL_Y + S['s_top'] * math.cos(lie), S['s_top'] * math.sin(lie)]) @ W
    lo = [-S['sole'] - 6.0, TOE_Q - 2.0, -8.0]
    hi = [max(4.0, top[0] + HOSEL_R + 2.0), top[1] + HOSEL_R + 2.0, max(F['toe_h'], top[2] + HOSEL_R) + 2.0]
    head = _field_obj('Fer', F['head'], lo, hi, detail, W, attribute='pqr')
    # Les stries : de 6,5 mm au-dessus du bord d'attaque jusque sous le bord supérieur, côté talon.
    r0 = 6.5
    rows = int((S['H'] - SCORE * math.tan(math.radians(S['tau'])) - 4.0 - r0) / S['pitch']) + 1
    P.assign(head, _iron_steel(S, F, rows, r0))
    parts = [head]
    back = -(T_FLOOR + T_INSERT)  # le dessus de l'insert, dans le repère de la face
    ins = _field_obj('Insert', F['insert'], [back - 1.0, TOE_Q + 2.0, F['r_cb'] - 2.0], [-T_FLOOR + 0.8, 28.0, F['toe_h']], 0.16, W, attribute='pqr')
    P.assign(ins, _insert_black())
    parts.append(ins)
    normal, across, up = -W[:, 0], -W[:, 1], W[:, 2]
    for k, (qs, rs) in enumerate(F['screws']):
        parts.append(_screw('Vis%d' % (k + 1), W @ np.array([back + 0.6, qs, rs]), normal, across))
    if monogram:
        (q1, r1), (q2, r2) = F['screws']
        centre = W @ np.array([back - 0.02, (q1 + q2) / 2, (r1 + r2) / 2 - 0.5]) * 0.001
        parts.append(_monogram(centre, across, up))
    parts += _shaft('', S['s_top'], S['length'], S['first_step'], S['lie'], (F['x_h'], HOSEL_Y))
    root = P.link(bpy.data.objects.new('Club', None))
    for o in parts:
        o.parent = root
    root['kind'], root['loft'], root['lie'] = kind, S['loft'], S['lie']
    _FIELDS[root.name] = (F['head'], W)
    return root


# ---------------------------------------------------------------- putter
# Lame classique à cavité, cotes en millimètres : longueur, hauteur de face, largeur face → arrière,
# épaisseur de la lame avant, hauteur du plancher de la cavité, demi-longueur de la cavité.
PUTTER = dict(length=114.0, height=25.5, depth=27.0, blade=9.5, floor=6.5, cavity=30.0, neck_y=36.0, shaft_x=5.0, shaft=864.0)


def _putter_fields(loft, lie):
    """Champ de la tête du putter, dans le repère de sa face (p vers l'avant, q vers le talon, r vers le haut)."""
    L, a = math.radians(loft), math.radians(lie)
    cL, sL, ca, sa = math.cos(L), math.sin(L), math.cos(a), math.sin(a)
    G = PUTTER
    half, top, floor = G['length'] / 2, G['height'], G['floor']
    yn, xs, zs = G['neck_y'], G['shaft_x'], 43.0  # col : position le long de la tête, axe du manche, hauteur du coude

    def head(pt):
        p, y, r = pt[:, 0], pt[:, 1], pt[:, 2]
        x, z = p * cL - r * sL, p * sL + r * cL
        ay = np.abs(y)
        # Trois volumes : la lame avant, le plancher de la cavité, et les deux masses de talon et de pointe
        # dont le dessus descend vers l'arrière.
        blade = np.maximum(z - top, -(G['blade'] + 0.10 * (top - z)) - x)
        slope = np.minimum(top - 2.0, top - 2.0 + (x + G['blade']) * 0.60)
        mass = _rmax((z - slope) * 0.86, (G['cavity'] + 0.14 * (z - floor)) - ay, 1.0)
        body = _rmin(_rmin(blade, z - floor, 1.6), mass, 1.2)
        # Contour vu de dessus (coins arrière arrondis, bouts de pointe et de talon légèrement bombés),
        # face plane, semelle relevée aux deux bouts.
        end = ay - half + (x + 0.5 * G['depth']) ** 2 / 110.0 + np.maximum(z - 0.6 * top, 0.0) ** 2 / 90.0
        body = _rmax(body, _rmax(-G['depth'] - x, end, 7.0), 1.3)
        body = _rmax(body, p, 0.6)
        sole = (x + 13.0) ** 2 / 300.0 + np.maximum(ay - 34.0, 0.0) ** 2 / 110.0 - z
        body = _rmax(body, sole, 1.4)
        # Le trait d'alignement, fraisé dans le plancher de la cavité.
        line = np.maximum.reduce([np.abs(y) - 0.55, floor - 0.5 - z, -G['depth'] + 1.5 - x, x + G['blade'] + 2.2])
        body = _rmax(body, -line, 0.12)
        # Col en plongeoir, d'une seule pièce : un montant dressé sur le bord supérieur, un coude vers
        # l'avant terminé par un bossage rond, et la douille du manche inclinée de l'angle de lie.
        profile = np.maximum.reduce([-10.1 - x, z - (zs + 4.5), (top - 3.5) - z])
        profile = _rmax(profile, -_rmax(-(x + 2.6), z - (zs - 4.5), 1.5), 0.8)
        plan = _rmin(np.maximum(np.abs(y - yn) - 4.6, x - xs), np.hypot(x - xs, y - yn) - 5.9, 1.0)
        side = (y - yn) * sa - (z - zs) * ca
        along = (y - yn) * ca + (z - zs) * sa
        socket = _rmax(np.hypot(x - xs, side) - 5.5, np.maximum(along - 20.0, 1.0 - along), 0.5)
        neck = _rmin(_rmax(profile, plan, 1.0), socket, 1.2)
        return _rmin(body, neck, 1.0)

    foot_y = yn - zs * ca / sa  # où l'axe du manche perce le sol
    return dict(head=head, to_world=np.array([[cL, 0, -sL], [0, 1, 0], [sL, 0, cL]]), foot=(xs, foot_y), s_top=zs / sa + 20.0)


def _putter_steel():
    """Acier satiné du putter : face fraisée de fines passes horizontales, cavité microbillée."""
    m = P.mat('AcierPutter', (0.62, 0.63, 0.64), rough=0.16, metal=1.0)
    N = _Net(m)
    vec, p, q, r = N.field()
    face = N.calc('LESS_THAN', N.calc('ABSOLUTE', p), 0.03)
    mill = N.calc('MULTIPLY', face, N.calc('SINE', N.calc('MULTIPLY', r, 2 * math.pi / 0.62)))
    G = PUTTER
    pocket = N.calc('MULTIPLY', N.calc('LESS_THAN', p, -G['blade'] - 0.8), N.calc('MULTIPLY', N.calc('LESS_THAN', N.calc('ABSOLUTE', q), G['cavity'] - 0.5), N.calc('LESS_THAN', r, G['height'] - 4.0)))
    grain = N.calc('SUBTRACT', N.streaks(vec, (4.0, 0.10, 4.0)), 0.5)
    # Le corps est satiné fin : il renvoie l'horizon, c'est ce qui fait lire du métal sur des pans plats.
    rough = N.calc('MULTIPLY_ADD', grain, 0.05, 0.16)
    rough = N.mix(pocket, rough, 0.46)
    N.put(N.bsdf.inputs['Roughness'], N.calc('ADD', rough, N.calc('MULTIPLY', face, 0.14)))
    tone = N.calc('MULTIPLY_ADD', grain, 0.04, 1.0)
    col = N.node('ShaderNodeCombineColor')
    for k, c in enumerate((0.62, 0.63, 0.64)):
        N.put(col.inputs[k], N.calc('MULTIPLY', tone, c))
    N.nt.links.new(col.outputs[0], N.bsdf.inputs['Base Color'])
    N.bump(N.calc('MULTIPLY', mill, 0.020))
    N.brushed(N.calc('MULTIPLY', N.calc('SUBTRACT', 1.0, pocket), 0.2))
    return m


def putter(loft=3.0, lie=70.0, detail=0.25):
    """Putter lame classique, à l'adresse : tête fine en acier satiné, face plane fraisée, cavité, trait
    d'alignement noir, col en plongeoir, manche en acier. Même repère que les fers : origine au bas du
    centre de la face, la face regarde +X, le talon et le manche sont côté +Y, semelle à z = 0.
    Renvoie un vide parent."""
    F = _putter_fields(loft, lie)
    W = F['to_world']
    G = PUTTER
    head = _field_obj('Putter', F['head'], [-G['depth'] - 4.0, -G['length'] / 2 - 2.0, -3.0], [G['shaft_x'] + 12.0, G['length'] / 2 + 2.0, 68.0], detail, W, attribute='pqr')
    P.assign(head, _putter_steel())
    # Le fond du trait d'alignement, peint en noir.
    x0, x1, z = -G['depth'] + 1.7, -G['blade'] - 2.4, G['floor'] - 0.42
    line = P.mesh_obj('Trait', np.array([[x0, -0.5, z], [x1, -0.5, z], [x1, 0.5, z], [x0, 0.5, z]]) * 0.001, np.array([[0, 1, 2, 3]]), smooth=False)
    P.assign(line, P.mat('Peinture', (0.008, 0.008, 0.009), rough=0.4))
    parts = [head, line] + _shaft('P', F['s_top'] - 8.0, G['shaft'], 400.0, lie, F['foot'], ferrule=False, steps=5, spacing=28.0, butt=7.4)
    root = P.link(bpy.data.objects.new('Club', None))
    for o in parts:
        o.parent = root
    root['kind'], root['loft'], root['lie'] = 'putter', loft, lie
    _FIELDS[root.name] = (F['head'], W)
    return root


def distance(root, points):
    """Distance signée (mètres, négative dedans) de points du monde (N,3) à la tête du club `root`."""
    f, W = _FIELDS[root.name]
    bpy.context.view_layer.update()
    inv = np.array(root.matrix_world.inverted())
    local = (np.asarray(points, dtype=np.float64) @ inv[:3, :3].T + inv[:3, 3]) * 1000.0
    return _eval(f, (local @ W).astype(np.float32)) * 0.001


def address(root, ball, gap=0.003, lift=0.0):
    """Pose le club derrière la balle : la face à `gap` mètres de la balle, la semelle à la hauteur
    `lift`. `ball` : centre de la balle (mètres)."""
    L = math.radians(root['loft'])
    back = (P.BALL_R + gap - (ball[2] - lift) * math.sin(L)) / math.cos(L)
    root.location = (ball[0] - back, ball[1], lift)
    return root


def flatten_grass(xy, height, seed, lean, obstacles, margin=0.0006):
    """Hauteurs des brins, abaissées là où un brin traverserait un objet posé dans l'herbe.
    `obstacles` : fonctions points (N,3) → distance signée en mètres. Mêmes tirages que parts.grass
    pour la même graine : à appeler avec les xy, seed et lean qu'on lui passera ensuite."""
    rng = np.random.default_rng(seed)
    n = len(xy)
    yaw = rng.random(n) * 2 * math.pi
    ln = lean[0] + (lean[1] - lean[0]) * rng.random(n)
    h = np.array(height, dtype=np.float64)
    # Seuls les brins plantés assez près d'un objet peuvent le toucher.
    foot = np.stack([xy[:, 0], xy[:, 1], 0.5 * h], axis=1)
    near = np.zeros(n, dtype=bool)
    for f in obstacles:
        near |= f(foot) < h * (1.0 + lean[1]) + margin
    idx = np.nonzero(near)[0]
    for _ in range(10):
        hit = np.zeros(len(idx), dtype=bool)
        for t in (0.4, 0.7, 1.0):
            fwd = ln[idx] * h[idx] * t * t
            pts = np.stack([xy[idx, 0] + np.cos(yaw[idx]) * fwd, xy[idx, 1] + np.sin(yaw[idx]) * fwd, h[idx] * t * (1 - 0.15 * t)], axis=1)
            for f in obstacles:
                hit |= f(pts) < margin
        idx = idx[hit]
        if not len(idx):
            break
        h[idx] *= 0.7
    return h


# ---------------------------------------------------------------- vues de contrôle
def _sun_azimuth(hdr):
    """Azimut vrai (radians, 0 = +X, sens trigonométrique vu de dessus) du point le plus lumineux du
    ciel, sans rotation. Blender place la colonne u de l'image dans la direction 2π·(0,5 − u)."""
    img = bpy.data.images.load(os.path.join(P.ASSETS, hdr + '.hdr'))
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    lum = px.reshape(h, w, 4)[:, :, :3].sum(axis=2)[h // 2 :]
    y, x = np.unravel_index(np.argmax(lum), lum.shape)
    bpy.data.images.remove(img)
    return 2 * math.pi * (0.5 - (x + 0.5) / w)


def _camera(pos, target, lens, fstop, focus):
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
    bpy.context.scene.camera = cam
    return cam


# Position de la caméra, point visé, focale, ouverture, azimut du soleil (degrés, 0 = +X).
VIEWS = {
    'dos': ((-0.37, -0.235, 0.095), (-0.020, 0.002, 0.027), 105, 8.0, -105),  # trois quarts arrière : le dos et l'insert
    'face': ((0.36, -0.21, 0.155), (-0.016, -0.002, 0.020), 105, 8.0, -70),  # de devant, côté pointe : les stries
    'joueur': ((-0.012, 0.11, 0.80), (-0.012, 0.004, 0.02), 135, 8.0, -41),  # d'au-dessus, comme à l'adresse
}
PUTTER_VIEWS = {
    'dos': ((-0.35, -0.24, 0.21), (-0.020, 0.004, 0.018), 105, 8.0, -105),
    'face': ((0.40, -0.25, 0.13), (-0.012, 0.004, 0.018), 105, 8.0, -70),
    'joueur': ((-0.014, 0.11, 0.80), (-0.014, 0.006, 0.02), 110, 8.0, -41),
}


def control_view(club, view, args):
    """Un club posé derrière une balle, sur l'herbe, sous le ciel de l'aube."""
    scene = bpy.context.scene
    green = club == 'putter'
    hdr = 'spruit_sunrise'
    pos, target, lens, fstop, sun = (PUTTER_VIEWS if green else VIEWS)[view]
    sun = args.sun if args.sun is not None else sun
    # La rotation du ciel tourne le regard, pas le ciel : le soleil se retrouve à (azimut d'origine − rotation).
    P.sky(hdr, rotation=_sun_azimuth(hdr) - math.radians(sun), strength=1.0)
    scene.view_settings.exposure = args.exposure if args.exposure is not None else -0.6
    lift = 0.0025 if green else 0.006  # la balle s'enfonce un peu dans l'herbe
    centre = (0.0, 0.0, lift + P.BALL_R)
    b = P.ball(centre, stamp=os.path.join(P.PRINTS, 'ball_stamp.png'))
    b.rotation_euler = (math.radians(-8), math.radians(4), math.radians(58))
    root = putter(detail=args.detail) if green else iron(kind=club, detail=args.detail)
    address(root, centre, gap=0.004, lift=0.002 if green else 0.004)
    cam_pos, target = V(pos), V(target)
    _camera(cam_pos, target, lens, fstop, (-0.02, 0.0, 0.025))
    if args.bare:  # sans herbe : un sol gris, pour juger les formes
        bpy.ops.mesh.primitive_plane_add(size=40)
        P.assign(bpy.context.object, P.mat('Sol', (0.30, 0.31, 0.30), rough=0.8))
        return
    view_dir = target - cam_pos
    view_dir.z = 0
    view_dir.normalize()
    if view == 'joueur':
        xy = P.scatter_cone(420_000, (-0.01, 0.0), (1, 0), 0.0, 0.42, math.pi, seed=2, falloff=0.0)
    else:
        origin = cam_pos - view_dir * 0.25
        xy = np.concatenate([
            P.scatter_cone(700_000, origin, view_dir, 0.1, 9.0, math.radians(24), seed=1),
            P.scatter_cone(220_000, (0.0, 0.0), view_dir, 0.0, 0.8, math.pi, seed=2, falloff=0.0),
        ])
    rng = np.random.default_rng(5)
    n = len(xy)
    clump = 1 + 0.2 * np.sin(xy[:, 0] * 9.1 + 1.3) * np.cos(xy[:, 1] * 7.3 + 0.4) + 0.1 * np.sin(xy[:, 0] * 23 + xy[:, 1] * 17)
    if green:  # gazon de green : ras et serré
        h = (0.0035 + 0.0015 * rng.random(n)) * clump
        w = 0.00045 + 0.00030 * rng.random(n)
    else:  # fairway
        h = (0.0085 + 0.0045 * rng.random(n) ** 1.4) * clump
        w = 0.00060 + 0.00050 * rng.random(n)
    lean, seed = (0.1, 0.8), 11
    ball_c = np.array(centre)
    h = flatten_grass(xy, h, seed, lean, [lambda pts: np.linalg.norm(pts - ball_c, axis=1) - P.BALL_R, lambda pts: distance(root, pts)])
    P.grass(xy, h, w, seed=seed, lean=lean)
    P.ground(color_near=(0.030, 0.085, 0.012), color_far=(0.23, 0.21, 0.10))
    P.bloom()


if __name__ == '__main__':
    import argparse
    import time

    argv = sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--club', default='fer7', choices=['long', 'fer7', 'wedge', 'putter', 'tous'])
    ap.add_argument('--view', default='dos', choices=['dos', 'face', 'joueur', 'toutes'])
    ap.add_argument('--samples', type=int, default=32)
    ap.add_argument('--scale', type=int, default=50)
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--detail', type=float, default=0.25, help='pas du maillage des têtes, en mm')
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'test'))
    ap.add_argument('--sun', type=float, default=None, help='azimut du soleil en degrés (0 = +X)')
    ap.add_argument('--exposure', type=float, default=None)
    ap.add_argument('--bare', action='store_true', help="sans herbe, sur un sol gris")
    ap.add_argument('--suffix', default='', help='ajouté au nom du fichier (clubs_<club>_<vue><suffixe>.png)')
    args = ap.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    for club in ['long', 'fer7', 'wedge', 'putter'] if args.club == 'tous' else [args.club]:
        for view in ['dos', 'face', 'joueur'] if args.view == 'toutes' else [args.view]:
            t0 = time.time()
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
            control_view(club, view, args)
            path = os.path.join(args.out, 'clubs_%s_%s%s.png' % (club, view, args.suffix))
            t1 = time.time()
            scene.render.filepath = os.path.abspath(path)
            bpy.ops.render.render(write_still=True)
            print(f'RESULT {path} construction {t1 - t0:.1f}s rendu {time.time() - t1:.1f}s')
