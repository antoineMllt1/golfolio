# Le corps du joueur : un vrai modèle anatomique (Anny, bâti sur MakeHuman, données CC0), mis aux
# proportions d'Antoine puis posé. Tout le calcul de pose est fait ici en numpy ; Anny ne sert qu'à
# fabriquer le corps au repos, mis en cache dans render/assets/body.npz.
#
#   pip install anny            # une fois (installe aussi torch)
#   python render/human.py      # fabrique le cache et affiche les mensurations
#
# Repère du modèle au repos : il regarde vers −Y, sa gauche est +X, Z vers le haut, bras écartés.
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'assets', 'body.npz')
# Jeune homme mince et grand (réglages Anny entre 0 et 1).
PHENOTYPE = dict(gender=1.0, age=0.48, muscle=0.42, weight=0.34, height=0.66, proportions=0.62)
HEIGHT = 1.80  # le corps est ensuite mis à cette taille


def build_cache(path=CACHE):
    import anny
    import torch

    model = anny.Anny(rig='makehuman', topology='anny-quads').to(dtype=torch.float32)
    pose = torch.eye(4)[None, None].repeat(1, model.bone_count, 1, 1)
    out = model(pose_parameters=pose, phenotype_kwargs={k: float(v) for k, v in PHENOTYPE.items()}, return_bone_ends=True)
    verts = out['rest_vertices'][0].numpy().astype(np.float64)
    heads = out['rest_bone_heads'][0].numpy().astype(np.float64)
    tails = out['rest_bone_tails'][0].numpy().astype(np.float64)
    floor = verts[:, 2].min()
    scale = HEIGHT / (verts[:, 2].max() - floor)
    for a in (verts, heads, tails):
        a[:, 2] -= floor  # pieds au sol
        a *= scale
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(
        path,
        verts=verts,
        faces=model.faces.numpy().astype(np.int32),
        heads=heads,
        tails=tails,
        parents=np.array([-1 if p is None else int(p) for p in model.bone_parents], dtype=np.int32),
        bone_idx=model.vertex_bone_indices.numpy().astype(np.int32),
        bone_w=model.vertex_bone_weights.numpy().astype(np.float64),
        labels=np.array(model.bone_labels),
    )


class Body:
    """Corps au repos + squelette. `pose()` renvoie les sommets posés."""

    def __init__(self, path=CACHE):
        if not os.path.exists(path):
            build_cache(path)
        d = np.load(path, allow_pickle=False)
        self.verts, self.faces = d['verts'], d['faces']
        self.heads, self.tails, self.parents = d['heads'], d['tails'], d['parents']
        self.bone_idx, self.bone_w = d['bone_idx'], d['bone_w']
        self.labels = [str(x) for x in d['labels']]
        self.id = {n: i for i, n in enumerate(self.labels)}
        self.n = len(self.labels)
        self.reset()

    # ------------------------------------------------------------ squelette
    def reset(self):
        self.R = [None] * self.n  # rotation monde de chaque os par rapport au repos (None = suit son parent)
        self.offset = np.zeros(3)

    def head(self, name):
        return self.heads[self.id[name]].copy()

    def length(self, a, b):
        return float(np.linalg.norm(self.head(b) - self.head(a)))

    def solve(self):
        """Rotations et têtes d'os posées, parents avant enfants."""
        R = np.zeros((self.n, 3, 3))
        H = np.zeros((self.n, 3))
        done = np.zeros(self.n, dtype=bool)
        order = []
        pending = list(range(self.n))
        while pending:
            for b in list(pending):
                p = self.parents[b]
                if p < 0 or done[p]:
                    order.append(b)
                    done[b] = True
                    pending.remove(b)
        for b in order:
            p = self.parents[b]
            if p < 0:
                R[b] = self.R[b] if self.R[b] is not None else np.eye(3)
                H[b] = self.heads[b] + self.offset
            else:
                R[b] = self.R[b] if self.R[b] is not None else R[p]
                H[b] = R[p] @ (self.heads[b] - self.heads[p]) + H[p]
        return R, H

    def posed_head(self, name):
        _, H = self.solve()
        return H[self.id[name]]

    def parent_R(self, name):
        R, _ = self.solve()
        p = self.parents[self.id[name]]
        return R[p] if p >= 0 else np.eye(3)

    def rotate(self, name, rot):
        """Ajoute une rotation monde à l'os (par-dessus celle qu'il a, ou celle de son parent)."""
        b = self.id[name]
        base = self.R[b] if self.R[b] is not None else self.parent_R(name)
        self.R[b] = rot @ base

    def aim(self, name, target, child=None):
        """Tourne l'os pour que son extrémité (la tête de `child`, sinon sa queue) vise `target`."""
        b = self.id[name]
        base = self.R[b] if self.R[b] is not None else self.parent_R(name)
        end = self.heads[self.id[child]] if child else self.tails[b]
        cur = base @ (end - self.heads[b])
        want = np.asarray(target, float) - self.posed_head(name)
        self.R[b] = arc(cur, want) @ base

    def pose(self):
        R, H = self.solve()
        v = self.verts
        out = np.zeros_like(v)
        for k in range(self.bone_idx.shape[1]):
            b = self.bone_idx[:, k]
            w = self.bone_w[:, k][:, None]
            out += w * (np.einsum('nij,nj->ni', R[b], v - self.heads[b]) + H[b])
        return out


# ---------------------------------------------------------------- rotations
def axis_angle(axis, deg):
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * (K @ K)


def arc(a, b):
    """Plus petite rotation qui amène la direction a sur la direction b."""
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    v = np.cross(a, b)
    s, c = np.linalg.norm(v), float(a @ b)
    if s < 1e-9:
        return np.eye(3) if c > 0 else axis_angle(np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0]), 180)
    return axis_angle(v / s, math.degrees(math.atan2(s, c)))


def two_bone(a, c, la, lb, pole):
    """Position du coude ou du genou entre a et c, poussé vers `pole`."""
    a, c, pole = np.asarray(a, float), np.asarray(c, float), np.asarray(pole, float)
    d = min(np.linalg.norm(c - a), (la + lb) * 0.999)
    s = (c - a) / np.linalg.norm(c - a)
    x = (la * la - lb * lb + d * d) / (2 * d)
    h = math.sqrt(max(la * la - x * x, 0))
    n = pole - s * (pole @ s)
    n /= np.linalg.norm(n)
    return a + s * x + n * h


# ---------------------------------------------------------------- poses
def curl_fingers(body, side, deg=62, thumb=28):
    """Referme la main sur le grip."""
    Rw, _ = body.solve()
    Rw = Rw[body.id[f'wrist.{side}']]
    wrist = body.head(f'wrist.{side}')
    index, pinky = body.head(f'finger2-1.{side}') - wrist, body.head(f'finger5-1.{side}') - wrist
    palm = np.cross(index, pinky)
    palm /= np.linalg.norm(palm)
    # Le sens qui rapproche le bout du majeur de la base du pouce est le bon.
    tip, base, thumb_base = body.tails[body.id[f'finger3-3.{side}']], body.head(f'finger3-1.{side}'), body.head(f'finger1-2.{side}')
    axis = np.cross(tip - base, palm)
    axis /= np.linalg.norm(axis)
    sign = 1 if np.linalg.norm(axis_angle(axis, 40) @ (tip - base) + base - thumb_base) < np.linalg.norm(axis_angle(axis, -40) @ (tip - base) + base - thumb_base) else -1
    for k in (2, 3, 4, 5):
        for j in (1, 2, 3):
            body.rotate(f'finger{k}-{j}.{side}', axis_angle(Rw @ axis, sign * deg))
    for j in (2, 3):
        body.rotate(f'finger1-{j}.{side}', axis_angle(Rw @ axis, sign * thumb))


def finish_pose(body):
    """Le finish d'un droitier vu de dos : poids sur la jambe gauche, pied droit sur la pointe, buste
    tourné au-delà de la cible, mains hautes à gauche de la tête. Renvoie les sommets posés et des
    repères (mains, direction du club, tête), dans le repère du modèle (il regarde −Y)."""
    body.reset()
    Z, X = (0, 0, 1), (1, 0, 0)
    # Bassin : face à la cible, déporté au-dessus du pied gauche.
    body.R[body.id['root']] = axis_angle(Z, 10)
    body.offset = np.array([0.075, -0.02, -0.004])
    # Buste : la rotation continue en montant, avec une légère cambrure.
    for name, twist, lean in (('spine05', 5, -1), ('spine04', 6, -2), ('spine03', 7, -2), ('spine02', 7, -1), ('spine01', 6, 0)):
        body.rotate(name, axis_angle(Z, twist) @ axis_angle(X, lean))
    # Tête : elle suit la balle, donc revient vers la cible.
    for name, twist in (('neck01', -8), ('neck02', -8), ('head', -10)):
        body.rotate(name, axis_angle(Z, twist))
    body.rotate('head', axis_angle(X, -4))

    # Jambe gauche : plantée, presque tendue.
    hip, ankle = body.posed_head('upperleg01.L'), body.head('foot.L') + [0.0, -0.01, 0.0]
    knee = two_bone(hip, ankle, body.length('upperleg01.L', 'lowerleg01.L'), body.length('lowerleg01.L', 'foot.L'), (0, -1, 0))
    body.aim('upperleg01.L', knee, 'lowerleg01.L')
    body.aim('lowerleg01.L', ankle, 'foot.L')
    body.R[body.id['foot.L']] = axis_angle(Z, 22)
    # Jambe droite : genou rentré vers la cible, pied dressé sur la pointe, semelle vers l'arrière.
    hip = body.posed_head('upperleg01.R')
    ball = body.head('foot.R') + [0.045, 0.43, -0.05]
    ankle = ball + [0.0, 0.05, 0.150]
    knee = two_bone(hip, ankle, body.length('upperleg01.R', 'lowerleg01.R'), body.length('lowerleg01.R', 'foot.R'), (0.35, -1, 0))
    body.aim('upperleg01.R', knee, 'lowerleg01.R')
    body.aim('lowerleg01.R', ankle, 'foot.R')
    f = body.id['foot.R']
    body.R[f] = arc(body.tails[f] - body.heads[f], (0.0, -0.04, -0.15))
    for b, name in enumerate(body.labels):
        if name.startswith('toe') and name.endswith('.R') and name.split('-')[1].startswith('1'):
            body.R[b] = np.eye(3)  # les orteils restent à plat

    # Bras : les deux mains sur le grip, hautes, à gauche et un peu derrière la tête.
    for name, lift in (('clavicle.L', 14), ('clavicle.R', 8)):
        Rp = body.parent_R(name)
        body.rotate(name, axis_angle(Rp @ np.array([0, 1.0, 0]), -lift if name.endswith('L') else lift))
    head = body.posed_head('head')
    club = np.array([-0.95, 0.24, -0.14])
    club /= np.linalg.norm(club)
    left = head + [0.175, 0.105, 0.115]
    right = left + club * 0.085
    for side, wrist, pole in (('L', left, (0.55, -0.35, -1.0)), ('R', right, (-0.2, -0.8, -0.75))):
        sh = body.posed_head(f'upperarm01.{side}')
        elbow = two_bone(sh, wrist, body.length(f'upperarm01.{side}', f'lowerarm01.{side}'), body.length(f'lowerarm01.{side}', f'wrist.{side}'), pole)
        body.aim(f'upperarm01.{side}', elbow, f'lowerarm01.{side}')
        body.aim(f'lowerarm01.{side}', wrist, f'wrist.{side}')
        curl_fingers(body, side)
    verts = body.pose()
    marks = dict(grip=body.posed_head('wrist.L') + club * 0.03, club=club, head=head, left_foot=body.posed_head('foot.L'))
    return verts, marks


def to_scene(points, origin, yaw_deg=90.0):
    """Du repère du modèle (regard −Y) à celui de la scène : regard vers +X, `origin` ramené en (0, 0)."""
    p = np.atleast_2d(np.asarray(points, float)) - np.array([origin[0], origin[1], 0.0])
    R = axis_angle((0, 0, 1), yaw_deg)
    return p @ R.T


if __name__ == '__main__':
    if not os.path.exists(CACHE):
        build_cache()
    b = Body()
    v = b.verts
    print('sommets', len(v), 'faces', len(b.faces), 'os', b.n)
    print('taille %.3f m' % v[:, 2].max())
    for name in ('upperleg01.L', 'lowerleg01.L', 'foot.L', 'upperarm01.L', 'lowerarm01.L', 'wrist.L', 'neck01', 'head', 'spine05', 'spine01', 'clavicle.L'):
        print(f'  {name:14s} tête', np.round(b.head(name), 3), 'queue', np.round(b.tails[b.id[name]], 3))
    print('cuisse %.3f tibia %.3f bras %.3f avant-bras %.3f' % (b.length('upperleg01.L', 'lowerleg01.L'), b.length('lowerleg01.L', 'foot.L'), b.length('upperarm01.L', 'lowerarm01.L'), b.length('lowerarm01.L', 'wrist.L')))
    print('largeur d’épaules %.3f' % (b.head('upperarm01.L')[0] - b.head('upperarm01.R')[0]))
