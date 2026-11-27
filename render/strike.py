# La frappe et le vol : une seule routine pour les six coups (Blender 5.x, module bpy).
#
# Repère d'un coup, comme dans parts.py : la balle part vers +X, le joueur (droitier) est côté +Y.
# Rien n'est simulé : tout est posé par images clés calculées ici (numpy), une clé par demi-image ;
# le flou de mouvement de Cycles fait le reste (scene.render.use_motion_blur, obturateur 0,5).
#
# Les pièces, dans l'ordre où un trajet les emploie (voir les trajets de render/scene.py) :
#   K.setup()                                    clés linéaires : pas de dépassement entre deux clés
#   clock = K.Clock(impact=11, slow=0.0022)      le temps réel d'une image : ralenti à l'impact,
#                                                de plus en plus rapide en s'en éloignant
#   K.swing(club, 'long', clock)                 le club : recul hors champ, descente, impact, traversée
#   ball = K.Ball(obj)                           la balle sur son porteur : place, écrasement, roule
#   fly = K.Flight.of('long', centre)            sa trajectoire réelle (mètres, secondes)
#   K.launch(ball, fly, clock, last=21)          écrasée à l'impact, puis en vol
#   K.putt(ball, hole, impact, land)             ou bien : elle roule jusqu'au trou et y tombe
#   K.burst(K.divot(turf_mat), …)                la motte, les brins, le tee qui sautent
#   K.Trace(fly, cam_pos, lens)                  la trace ambre de la balle dans le ciel (fly : un vol,
#                                                ou K.Path(images, places) pour la chute d'une arrivée)
#   K.track(cam, frames, pos, target, …)         la caméra, image par image
#   K.arrival(…)                                 la fin du vol vue de l'arrêt suivant : chute, rebonds, roule
#   K.burst(K.spray(22, soleil), …)              la gerbe de rosée au premier rebond
#   K.settle(club, 39, 44, lie)                  le club du coup suivant vient se poser derrière la balle
#
# Un coup dure 44 images à 27 images par seconde : le recul du club n'est qu'une amorce (il sort du
# champ en trois images), le haut du geste est hors champ, la descente rentre dans le cadre deux images
# avant l'impact.
import math

import bpy
import numpy as np
from mathutils import Quaternion, Vector

import parts as P

V = Vector
G = 9.81

# Un club : angle de lie (degrés), rayon de l'arc de la tête autour du pivot (mètres ; le pivot est
# côté joueur, dans le prolongement du manche), angle d'attaque (degrés, positif : la tête descend
# encore à l'impact et prend l'herbe après la balle), vitesse de la tête à l'impact (m/s), part de
# cette vitesse gardée après l'impact, hauteur du recul (radians) ; puis le vol : vitesse de la balle
# (m/s), angle de lancement (degrés), pesanteur apparente (la portance d'une balle qui tourne la
# réduit) et freinage (voir Flight).
CLUBS = {
    'bois3': dict(lie=57.0, radius=1.62, attack=-1.0, speed=47.0, keep=0.80, top=1.40, ball=66.0, launch=11.5, g=5.2, drag=0.055),
    'long': dict(lie=60.5, radius=1.48, attack=3.0, speed=42.0, keep=0.78, top=1.40, ball=60.0, launch=14.0, g=5.6, drag=0.060),
    'fer7': dict(lie=62.5, radius=1.42, attack=4.0, speed=38.0, keep=0.76, top=1.40, ball=53.0, launch=18.0, g=6.6, drag=0.070),
    'wedge': dict(lie=64.0, radius=1.25, attack=3.5, speed=6.5, keep=0.85, top=0.50, ball=8.2, launch=30.0, g=G, drag=0.0),  # approche roulée : 6 m de vol
    'putter': dict(lie=70.0, radius=1.30, attack=0.0, speed=1.15, keep=0.90, top=0.20, ball=1.9, launch=0.0, g=G, drag=0.0),
}


def setup():
    """À appeler avant de poser des clés : interpolation linéaire entre elles (une clé par demi-image
    suit les courbes d'assez près, et rien ne dépasse à l'impact)."""
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'


def smooth(u):
    """Passage doux de 0 à 1."""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def ease_out(u, power=3.0):
    """De 0 à 1, vite d'abord, puis en se posant."""
    return 1.0 - (1.0 - np.clip(u, 0.0, 1.0)) ** power


def half_frames(first, last, step=0.5):
    """Les instants où poser les clés : chaque image et chaque demi-image. step=0.25 : chaque quart
    d'image, pour un plan où la balle passe tout près d'une caméra qui se retourne (l'obturateur
    s'ouvre un quart d'image avant l'image et se ferme un quart d'image après : avec une clé à ces
    deux instants, la visée reste sur la balle pendant toute la pose et elle ne bave pas)."""
    return [first + step * k for k in range(int(round((last - first) / step)) + 1)]


# ---------------------------------------------------------------- le temps
class Clock:
    """Le temps réel (secondes, 0 à l'impact) de chaque image. À l'impact, une image dure `slow`
    secondes (le ralenti) ; chaque image d'écart en dure `before` fois plus avant lui, `after` fois
    plus après, sans dépasser `cap` : la frappe se lit, puis le film rattrape le vol."""

    def __init__(self, impact, slow, before=1.7, after=1.9, cap=1e9):
        self.impact, self.slow, self.before, self.after, self.cap = impact, slow, before, after, cap

    def at(self, frame):
        k = frame - self.impact
        grow = self.after if k >= 0 else self.before
        k, t, j = abs(k), 0.0, 0
        while k > 1e-9:
            step = min(1.0, k)
            t += step * min(self.slow * grow**j, self.cap)
            k -= step
            j += 1
        return t if frame >= self.impact else -t


# ---------------------------------------------------------------- le club
def swing(club, kind, clock, first=1, back=5, reach=0.009, finish=2.5, last=None, leave=True, soft=False):
    """Le geste, vu par sa tête : elle part de l'adresse (image `first`), recule hors champ en `back`
    images, revient sur un arc autour d'un pivot placé côté joueur, traverse la balle à l'image
    clock.impact et accompagne. `club` : le vide parent du club, posé à l'adresse ; `reach` : avancée
    de la face entre l'adresse et le fond de l'écrasement de la balle (mètres). Renvoie l'angle de la
    tête (radians, 0 à l'adresse) à chaque instant posé : {image: angle}. Après l'image `last`, le
    club quitte la scène (leave) : sans joueur pour le tenir, il ne doit pas rester en l'air si la
    caméra se retourne. soft : après l'impact la tête ralentit et s'arrête en douceur à l'angle
    `finish` (un putt : le joueur tient sa fin de geste), au lieu de traverser à pleine vitesse."""
    S = CLUBS[kind]
    lie, attack = math.radians(S['lie']), math.radians(S['attack'])
    along, up = V((1, 0, 0)), V((0, math.cos(lie), math.sin(lie)))  # le plan du geste : la ligne de jeu et le manche
    axis = along.cross(up)  # un angle positif mène la tête vers la cible
    start = club.location.copy()
    # Le pivot est en avant de la balle quand la tête descend encore à l'impact : le point bas de l'arc
    # est alors après la balle, dans l'herbe.
    pivot = start + S['radius'] * (math.sin(attack) * along + math.cos(attack) * up)
    rate = S['speed'] / S['radius']
    club.rotation_mode = 'QUATERNION'
    base = club.rotation_quaternion.copy()
    last = last if last is not None else clock.impact + 6
    angles = {}
    for f in half_frames(first, last):
        if f <= first + back:  # le recul : rien pendant une demi-image (la première image est celle de l'arrêt), puis de plus en plus vite
            phi = -S['top'] * max(0.0, (f - first - 0.5) / (back - 0.5)) ** 2.5
        else:
            t = clock.at(f)
            phi = reach / S['radius'] + rate * t * (1.0 if t < 0 else S['keep'])
            if soft and t > 0:
                phi = reach / S['radius'] + finish * (1.0 - math.exp(-rate * S['keep'] * t / finish))
            phi = max(-S['top'], min(finish, phi))
        turn = Quaternion(axis, phi)
        club.location = pivot + turn @ (start - pivot)
        club.rotation_quaternion = turn @ base
        club.keyframe_insert('location', frame=f)
        club.keyframe_insert('rotation_quaternion', frame=f)
        angles[f] = phi
    if leave:
        club.location = club.location + V((0, 0, -4.0))
        club.keyframe_insert('location', frame=last + 0.05)
    return angles


def settle(club, first, last, lie, reach=2.6, behind=0.05):
    """Le club du coup suivant vient se poser derrière la balle, entre les images `first` et `last` :
    il descend le long de son manche (angle de lie en degrés), vite d'abord, puis en douceur. Avant
    `first`, il attend hors champ. `club` : le vide parent, déjà posé à l'adresse."""
    lie = math.radians(lie)
    rest, up = club.location.copy(), V((0, math.cos(lie), math.sin(lie)))
    for f in [first - 1] + half_frames(first, last):
        u = (f - first) / (last - first)
        club.location = rest + up * (reach * (1 - ease_out(u, 4.0))) + V((-behind, 0, 0)) * (1 - smooth(u)) if u < 1 else rest
        club.keyframe_insert('location', frame=f)


# ---------------------------------------------------------------- la balle
class Ball:
    """La balle et son porteur. Le porteur (un vide, axes du monde) donne la place et l'écrasement dans
    l'axe du coup ; la balle, son enfant, garde l'orientation de son tampon et roule."""

    def __init__(self, obj, radius=P.BALL_R):
        self.obj, self.radius = obj, radius
        self.carrier = P.link(bpy.data.objects.new('Porteur', None))
        self.carrier.location = obj.location
        self.rest = obj.rotation_euler.to_quaternion()
        obj.parent = self.carrier
        obj.location = (0, 0, 0)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = self.rest

    def key(self, frame, pos, squash=1.0):
        """Place de la balle (son centre) ; squash : son épaisseur dans l'axe du coup (0,85 à l'impact)."""
        self.carrier.location = pos
        side = 1.0 / math.sqrt(squash)
        self.carrier.scale = (squash, side, side)
        self.carrier.keyframe_insert('location', frame=frame)
        self.carrier.keyframe_insert('scale', frame=frame)

    def turn(self, frame, quat):
        self.obj.rotation_quaternion = quat
        self.obj.keyframe_insert('rotation_quaternion', frame=frame)

    def roll(self, frames, points, final=None, start=None):
        """La balle roule le long de `points` (une place par instant de `frames`) et finit dans
        l'orientation `final` (quaternion) : son tampon tourne de plus en plus lentement, et s'arrête
        où l'image de l'arrêt le montre. Ou bien `start` : elle part de cette orientation (un putt,
        dont la première image est celle de l'arrêt). Renvoie l'orientation de la fin."""
        pts = [V(p) for p in points]
        left = [0.0] * len(pts)  # chemin qui reste à faire, à plat
        for k in range(len(pts) - 2, -1, -1):
            d = pts[k + 1] - pts[k]
            left[k] = left[k + 1] + math.hypot(d.x, d.y)
        heading = pts[-1] - pts[0]
        axis = V((0, 0, 1)).cross(V((heading.x, heading.y, 0)).normalized())
        if final is None:
            final = Quaternion(axis, left[0] / self.radius) @ start
        for f, rest in zip(frames, left):
            self.turn(f, Quaternion(axis, -rest / self.radius) @ final)
        return final


class Flight:
    """Le vol d'une balle, en mètres et en secondes. Modèle simple, réglé à l'œil sur de vrais vols :
    la balle avance à speed·cos(launch), freinée de `drag` par seconde, et monte sous une pesanteur
    apparente `g` plus faible que la vraie (la portance) ; un rien d'effet la ramène vers la gauche."""

    def __init__(self, origin, speed, launch, g=G, drag=0.0, draw=(-0.010, 0.00005)):
        self.origin, self.speed, self.launch, self.g, self.drag, self.draw = np.array(origin, dtype=float), speed, math.radians(launch), g, drag, draw

    @classmethod
    def of(cls, kind, origin, **kw):
        S = CLUBS[kind]
        return cls(origin, S['ball'], S['launch'], S['g'], S['drag'], **kw)

    @property
    def time(self):
        """Durée du vol jusqu'à retomber à la hauteur de départ."""
        return 2 * self.speed * math.sin(self.launch) / self.g

    def at(self, t):
        t = np.maximum(np.asarray(t, dtype=float), 0.0)
        x = self.speed * math.cos(self.launch) * t * (1 - self.drag * t)
        z = self.speed * math.sin(self.launch) * t - 0.5 * self.g * t * t
        y = self.draw[0] * x + self.draw[1] * x * x
        return self.origin + np.stack([x, y, z], axis=-1)


def launch(ball, flight, clock, first=1, last=None, squash=0.85, step=0.5):
    """La balle attend, s'écrase à l'impact (une image, puis une autre où elle se reforme en partant),
    et vole. Renvoie {image: place} pour la caméra. step : écart entre deux clés (voir half_frames)."""
    impact = clock.impact
    last = last if last is not None else impact + 8
    rest = V(flight.origin)
    ball.key(first, rest)
    ball.key(impact - 0.12, rest)  # elle ne bouge pas avant que la face n'arrive
    ball.turn(impact, ball.rest)
    where = {f: rest.copy() for f in half_frames(first, impact - step, step)}
    for f in half_frames(impact, last, step):
        k = f - impact
        p = V(flight.at(clock.at(f)))
        if k == 0:
            p = rest + V((0.5 * (1 - squash) * ball.radius, 0, 0))  # le dos de la balle est enfoncé par la face
        # Écrasée à l'impact, à moitié reformée une demi-image après, un rien étirée à l'image suivante.
        ball.key(f, p, float(np.interp(k, [0.0, 0.5, 1.0, 1.5], [squash, 0.5 + 0.5 * squash, 1.06, 1.0])))
        where[f] = p
    # En vol la balle tourne sur elle-même (effet rétro) : son tampon ne reste pas figé face à nous.
    spin = V((0, -1, 0))
    for f in half_frames(impact + 0.5, last):
        ball.turn(f, Quaternion(spin, 2.4 * (f - impact)) @ ball.rest)
    return where


def putt(ball, hole, impact, land, first=1, last=None, bow=0.0, speeds=(0.08, 0.05), rest=None, final=None, drop=3.0, cup=P.CUP_R, depth=P.CUP_DEPTH):
    """Un putt qui tombe. La balle attend, part à l'image `impact`, roule vers le trou `hole` (x, y) sur
    une ligne un peu courbe (`bow` : flèche en mètres, vers la gauche du putt, plus marquée en fin de
    course, quand la balle ralentit ; 0 : tout droit), arrive au bord à l'image `land`, bascule
    par-dessus et tombe au fond du godet en `drop` images (trois : à peu près le temps réel), où elle
    s'arrête à `rest` (son centre ; par défaut un peu au-delà de l'axe) dans l'orientation `final`
    (sinon celle où la roule la laisse).
    speeds : mètres par image au départ et au bord du trou ; entre les deux le film file (le temps
    est resserré, comme pour un vol). Renvoie {image: place}."""
    last = last if last is not None else land + 5
    start = V(ball.carrier.location)
    z0, zb = start.z, -depth + ball.radius
    centre = V((hole[0], hole[1], z0))
    line = (centre - start).normalized()
    lip = centre - line * cup  # le centre de la balle au-dessus du bord : elle bascule
    left = V((0, 0, 1)).cross(line)
    length = (lip - start).length
    n = land - impact
    m0, m1 = speeds[0] * n / length, speeds[1] * n / length

    def on_line(u):  # part du chemin faite, puis place : la flèche est aux deux tiers
        w = (u**3 - 2 * u * u + u) * m0 + (3 * u * u - 2 * u**3) + (u**3 - u * u) * m1
        return start + (lip - start) * w + left * (bow * 2.6 * w * (1 - w * w))

    ball.key(first, start)
    ball.key(impact - 0.12, start)
    where = {f: start.copy() for f in half_frames(first, impact - 0.5)}
    rolling = half_frames(impact, land)
    for f in rolling:
        where[f] = on_line((f - impact) / n)
    way = (where[land] - where[land - 0.5]).normalized()  # le sens de la balle au bord du trou
    way.z = 0
    rest = V(rest) if rest is not None else V((hole[0], hole[1], zb)) + way * 0.020
    # La chute : part du temps de chute, avancée depuis le bord, hauteur. Elle heurte la paroi d'en
    # face, puis le fond, revient un peu et s'immobilise.
    part = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5]
    along = [0.0, 0.022, 0.046, 0.066, 0.080, 0.072, 0.064]
    height = [z0, z0 - 0.010, z0 - 0.042, z0 - 0.082, zb, zb + 0.007, zb]
    still = land + math.ceil(2 * 1.5 * drop) / 2  # au fond, à la demi-image près
    falling = half_frames(land + 0.5, still)
    for f in falling:
        k = (f - land) / drop
        p = where[land] + way * float(np.interp(k, part, along))
        where[f] = V((p.x, p.y, float(np.interp(k, part, height))))
    settle = half_frames(still, max(last, still + 1.0))
    for f in settle:
        where[f] = where[still].lerp(rest, float(smooth(f - still)))
    for f in sorted(where):
        if f >= impact:
            ball.key(f, where[f])
    turned = ball.roll(rolling, [where[f] for f in rolling], start=ball.rest)
    # Dans le godet elle tourne encore un peu, puis s'immobilise.
    spin = V((0, 0, 1)).cross(way)
    for f in falling:
        ball.turn(f, Quaternion(spin, 1.3 * (f - land)) @ turned)
    down = Quaternion(spin, 1.3 * (still - land)) @ turned
    end = final if final is not None else down
    for f in settle:
        ball.turn(f, down.slerp(end, float(smooth(f - still))))
    return where


def arrival(rest, first, land, stop, fall=(1.15, 0.95), hops=((2.0, 3.0, 0.45), (1.5, 0.9, 0.10)), run=2.2, heading=(1.0, 0.0), radius=P.BALL_R, last=None):
    """La fin d'un vol, vue de l'arrêt suivant. La balle descend du ciel (elle avance de fall[0] mètres
    et descend de fall[1] mètres par image), touche le sol à l'image `land`, rebondit (hops : durée en
    images, longueur, hauteur de chaque rebond), puis roule `run` mètres en ralentissant et s'arrête à
    l'image `stop`, à `rest` (centre de la balle). `heading` : sens du coup, à plat. Renvoie les
    instants et les places : (frames, points)."""
    rest = V(rest)
    way = V((heading[0], heading[1], 0)).normalized()
    start = land + sum(h[0] for h in hops)  # début de la roule
    total = run + sum(h[1] for h in hops)
    # La roule ralentit jusqu'à l'arrêt ; son élan de départ prolonge celui du dernier rebond.
    frames = half_frames(first, last if last is not None else math.ceil(stop))
    points = []
    for f in frames:
        z = 0.0
        if f <= land:
            k = land - f
            back, z = total + fall[0] * k, fall[1] * k + 0.012 * k * k  # la chute se redresse en approchant
        elif f < start:
            back, t0 = total, land
            for n, length, height in hops:
                if f <= t0 + n:
                    u = (f - t0) / n
                    back -= length * u
                    z = 4 * height * u * (1 - u)
                    break
                back -= length
                t0 += n
        else:
            u = min(1.0, (f - start) / (stop - start))
            back = run * (1 - u) ** 2
        points.append(rest - way * back + V((0, 0, z)))
    return frames, points


class Path:
    """Un chemin déjà calculé (les instants et les places que renvoie arrival), à donner à Trace à la
    place d'un vol : le « temps » y est le numéro d'image."""

    def __init__(self, frames, points):
        self.frames, self.points = np.array(frames, dtype=float), np.array([tuple(p) for p in points], dtype=float)

    def at(self, t):
        t = np.asarray(t, dtype=float)
        return np.stack([np.interp(t, self.frames, self.points[:, k]) for k in range(3)], axis=-1)


# ---------------------------------------------------------------- ce qui saute
def _soil():
    m = P.mat('Motte', (0.045, 0.030, 0.018), rough=0.95)
    return m


def divot(turf, size=(0.075, 0.046, 0.011), seed=4):
    """La motte qu'un fer arrache après la balle : une galette de terre irrégulière, coiffée d'herbe.
    `turf` : la matière du gazon. Renvoie un vide parent, à poser et à lancer avec burst."""
    rng = np.random.default_rng(seed)
    v, f = P.icosphere(2)
    v = v * (1 + 0.22 * rng.standard_normal((len(v), 1))) * (np.array(size) / 2)
    v[:, 2] = np.minimum(v[:, 2], size[2] * 0.25)  # le dessus est plat : c'est le gazon
    clod = P.assign(P.mesh_obj('Motte', v, f), _soil())
    n = 260
    a, r = rng.random(n) * 2 * math.pi, np.sqrt(rng.random(n))
    xy = np.stack([r * np.cos(a) * size[0] * 0.46, r * np.sin(a) * size[1] * 0.46], axis=1)
    tuft, _ = P.blades(xy, 0.007 + 0.005 * rng.random(n), 0.0007 + 0.0005 * rng.random(n), rng.random(n) * 2 * math.pi, 0.2 + 0.6 * rng.random(n), material=turf, name='HerbeMotte', tip=0.55)
    tuft.location.z = size[2] * 0.2
    root = P.link(bpy.data.objects.new('MotteVolante', None))
    clod.parent = tuft.parent = root
    return root


def crumbs(count, size=(0.002, 0.006), seed=5):
    """Des miettes de terre."""
    rng = np.random.default_rng(seed)
    v, f = P.icosphere(0)
    mat, out = _soil(), []
    for _ in range(count):
        s = size[0] + (size[1] - size[0]) * rng.random() ** 2
        out.append(P.assign(P.mesh_obj('Miette', v * s * (0.6 + 0.8 * rng.random((1, 3))), f, smooth=False), mat))
    return out


def loose_blades(count, turf, length=(0.008, 0.014), seed=6):
    """Des brins d'herbe coupés."""
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(count):
        h = length[0] + (length[1] - length[0]) * rng.random()
        o, _ = P.blades(np.zeros((1, 2)), np.array([h]), np.array([0.0009]), np.array([0.0]), np.array([0.5]), material=turf, name='BrinVolant', tip=0.55)
        out.append(o)
    return out


def spray(count, sun, size=(0.0015, 0.003), seed=8):
    """Des gouttes de rosée, pour la gerbe que soulève une balle qui retombe dans l'herbe mouillée :
    des billes d'eau qui accrochent le soleil `sun` (vecteur unitaire), à lancer avec burst."""
    rng = np.random.default_rng(seed)
    v, f = P.icosphere(1)
    m = P.drop_material(sun, glint=(60.0, 30.0, 160.0))
    return [P.assign(P.mesh_obj('Gerbe', v * (size[0] + (size[1] - size[0]) * rng.random()), f), m) for _ in range(count)]


def burst(objects, origin, clock, last, speed=(4.0, 10.0), lift=(25.0, 60.0), fan=28.0, scatter=0.02, tumble=40.0, seed=7, ground=0.004, hidden=True):
    """Lance des objets à l'impact : chacun part de `origin` (à `scatter` mètres près) à une vitesse de
    speed m/s, entre lift degrés au-dessus du sol, dans un éventail de ±fan degrés autour de +X, en
    tournoyant (tumble, radians par seconde), et retombe. Le temps est celui de l'horloge du coup : au
    ralenti de l'impact, les débris restent un instant en l'air pendant que la balle est déjà loin.
    hidden : avant l'impact les objets attendent sous le sol (la motte en sort) ; sinon ils restent
    à leur place jusqu'à l'impact (le tee)."""
    rng = np.random.default_rng(seed)
    impact = clock.impact
    for o in objects:
        v = speed[0] + (speed[1] - speed[0]) * rng.random()
        el = math.radians(lift[0] + (lift[1] - lift[0]) * rng.random())
        az = math.radians(fan * (2 * rng.random() - 1))
        vel = V((v * math.cos(el) * math.cos(az), v * math.cos(el) * math.sin(az), v * math.sin(el)))
        start = V(origin) + V(tuple(scatter * (2 * rng.random(3) - 1))) if hidden else o.location.copy()
        axis = V(tuple(rng.standard_normal(3))).normalized()
        rate = tumble * (0.5 + rng.random())
        o.rotation_mode = 'QUATERNION'
        base = o.rotation_quaternion.copy()
        o.location = start - V((0, 0, 0.5)) if hidden else start
        o.keyframe_insert('location', frame=impact - 0.04)
        o.keyframe_insert('rotation_quaternion', frame=impact - 0.04)
        down = None
        for f in half_frames(impact, last):
            t = clock.at(f)
            p = start + vel * t + V((0, 0, -0.5 * G * t * t))
            if p.z <= ground and t > 0:  # retombé : il reste où il a touché
                down = down or (V((p.x, p.y, ground)), Quaternion(axis, rate * t) @ base)
                p, q = down
            else:
                q = Quaternion(axis, rate * t) @ base
            o.location, o.rotation_quaternion = p, q
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('rotation_quaternion', frame=f)


# ---------------------------------------------------------------- la trace de la balle dans le ciel
# L'ambre du traceur du site (#f2a93b). AgX délave les couleurs vives en les éclaircissant : c'est
# cet orangé plus rouge, émis à la force amber(exposition), qui s'affiche au plus près (vers #e8a060).
AMBER = (1.0, 0.25, 0.0)


def amber(exposure, glow=2.4):
    """Force d'émission qui garde la trace ambre à l'écran pour une exposition donnée (glow : la force
    à −0,6, l'exposition du plan large). À rappeler image par image si l'exposition monte (Trace.glow)."""
    return glow * 2.0 ** (-0.6 - exposure)


class Trace:
    """La trajectoire en trait lumineux ambre, de largeur apparente constante, qui se dessine derrière
    la balle : au loin la balle n'est plus qu'un point, c'est sa trace qu'on suit. `flight` : le vol ;
    `eye` : la caméra (la largeur du trait en dépend) ; `lens` : sa focale ; `span` : secondes de vol
    tracées ; `tail` : secondes au bout desquelles le trait s'efface derrière la balle (0 : il reste) ;
    `taper` : de combien le trait s'affine en s'éloignant (0 : largeur apparente constante ; 0,4 : quatre
    fois plus loin, il est presque deux fois plus fin). `colour` est en linéaire : AMBER est l'ambre du
    site (#f2a93b). `foot` : secondes de vol sur lesquelles le trait apparaît à son début (0 : il commence
    net, comme un piquet planté dans l'herbe) ; `dot` : le point lumineux à la tête du trait (à retirer
    quand la vraie balle se voit). Poser ensuite key(image, temps de vol) pour chaque image."""

    def __init__(self, flight, eye, lens=50.0, span=(0.02, 4.0), strength=7.0, tail=0.0, steps=140, width=0.00055, colour=(1.0, 0.60, 0.16), taper=0.0, foot=0.0, dot=True):
        t = np.linspace(span[0], span[1], steps)
        pts = flight.at(t)
        self.flight, self.eye, self.k, self.taper = flight, np.array(eye, dtype=float), width * 50.0 / lens, taper
        self.born = (span[0], foot)
        self.near = float(np.linalg.norm(pts[0] - self.eye))
        rad = self.radius(pts)
        tan = np.gradient(pts, axis=0)
        tan /= np.linalg.norm(tan, axis=1)[:, None]
        n1 = np.cross(tan, np.array([0, 0, 1.0]))
        n1 /= np.linalg.norm(n1, axis=1)[:, None]
        n2 = np.cross(tan, n1)
        th = np.linspace(0, 2 * math.pi, 8, endpoint=False)
        ring = pts[:, None, :] + rad[:, None, None] * (n1[:, None, :] * np.cos(th)[None, :, None] + n2[:, None, :] * np.sin(th)[None, :, None])
        i, j = np.arange(steps - 1)[:, None], np.arange(8)[None]
        faces = np.stack([i * 8 + j, i * 8 + (j + 1) % 8, (i + 1) * 8 + (j + 1) % 8, (i + 1) * 8 + j], axis=-1).reshape(-1, 4)
        self.line = P.mesh_obj('Trajectoire', ring.reshape(-1, 3), faces)
        self.line.data.attributes.new('vol', 'FLOAT', 'POINT').data.foreach_set('value', np.repeat(t, 8).astype(np.float32))
        # Le trait n'existe que jusqu'à la balle : au-delà, il est transparent.
        # Matière noire qui n'émet que sa couleur : éclairée par le ciel, elle virerait au blanc.
        m = P.mat('Trace', (0, 0, 0), rough=1.0, emission_color=(*colour, 1), emission_strength=strength)
        nt = m.node_tree
        att = nt.nodes.new('ShaderNodeAttribute')
        att.attribute_name = 'vol'
        self.head = nt.nodes.new('ShaderNodeValue')
        shown = nt.nodes.new('ShaderNodeMath')
        shown.operation = 'LESS_THAN'
        nt.links.new(att.outputs['Fac'], shown.inputs[0])
        nt.links.new(self.head.outputs[0], shown.inputs[1])
        amount = shown.outputs[0]
        if tail > 0:  # et il s'efface derrière elle, comme une comète
            fade = nt.nodes.new('ShaderNodeMapRange')
            fade.interpolation_type = 'SMOOTHSTEP'
            sub = nt.nodes.new('ShaderNodeMath')
            sub.operation = 'SUBTRACT'
            nt.links.new(self.head.outputs[0], sub.inputs[0])
            sub.inputs[1].default_value = tail
            nt.links.new(att.outputs['Fac'], fade.inputs['Value'])
            nt.links.new(sub.outputs[0], fade.inputs['From Min'])
            nt.links.new(self.head.outputs[0], fade.inputs['From Max'])
            both = nt.nodes.new('ShaderNodeMath')
            both.operation = 'MULTIPLY'
            nt.links.new(shown.outputs[0], both.inputs[0])
            nt.links.new(fade.outputs[0], both.inputs[1])
            amount = both.outputs[0]
        if foot > 0:  # le début du trait sort du flou : pas de pied net
            rise = nt.nodes.new('ShaderNodeMapRange')
            rise.interpolation_type = 'SMOOTHSTEP'
            rise.inputs['From Min'].default_value = span[0]
            rise.inputs['From Max'].default_value = span[0] + foot
            nt.links.new(att.outputs['Fac'], rise.inputs['Value'])
            both = nt.nodes.new('ShaderNodeMath')
            both.operation = 'MULTIPLY'
            nt.links.new(amount, both.inputs[0])
            nt.links.new(rise.outputs[0], both.inputs[1])
            amount = both.outputs[0]
        clear = nt.nodes.new('ShaderNodeBsdfTransparent')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(amount, mix.inputs[0])
        nt.links.new(clear.outputs[0], mix.inputs[1])
        nt.links.new(P.bsdf(m).outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], nt.nodes['Material Output'].inputs['Surface'])
        P.assign(self.line, m)
        self.line.visible_shadow = False
        self.lit = [P.bsdf(m).inputs['Emission Strength']]
        self.dot = None
        if dot:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0)
            self.dot = bpy.context.object
            self.dot.name = 'PointBalle'
            P.assign(self.dot, P.mat('PointBalle', (0, 0, 0), rough=1.0, emission_color=(*colour, 1), emission_strength=strength))
            self.lit.append(P.bsdf(self.dot.data.materials[0]).inputs['Emission Strength'])
            self.dot.visible_shadow = False

    def glow(self, frame, strength):
        """Clé sur la force de la trace : à baisser quand l'exposition du plan monte, pour qu'elle reste
        ambre pendant que le ciel blanchit (voir amber)."""
        for socket in self.lit:
            socket.default_value = strength
            socket.keyframe_insert('default_value', frame=frame)

    def radius(self, points):
        """Rayon du trait en chaque point : proportionnel à la distance à la caméra (largeur apparente
        constante), moins ce que `taper` lui retire au loin."""
        d = np.linalg.norm(np.asarray(points, dtype=float) - self.eye, axis=-1)
        return self.k * d * (self.near / np.maximum(d, self.near)) ** self.taper

    def key(self, frame, t):
        """À l'image `frame`, la balle en est à `t` secondes de vol."""
        self.head.outputs[0].default_value = t
        self.head.outputs[0].keyframe_insert('default_value', frame=frame)
        if self.dot is None:
            return
        p = self.flight.at(t)
        self.dot.location = p
        r = 2.6 * float(self.radius(p))
        if self.born[1] > 0:  # le point naît avec le trait
            r *= max(0.02, float(smooth((t - self.born[0]) / self.born[1])))
        self.dot.scale = (r, r, r)
        self.dot.keyframe_insert('location', frame=frame)
        self.dot.keyframe_insert('scale', frame=frame)


# ---------------------------------------------------------------- la caméra
def track(cam, frames, pos, target, lens=None, focus=None, fstop=None):
    """Pose la caméra à chaque instant de `frames` : place, point visé (horizon droit), et si on les
    donne focale (mm), distance de mise au point (m) et ouverture. Les rotations sont des quaternions
    qui se suivent sans saut : un fouetté de 140° en deux images reste un fouetté."""
    cam.rotation_mode = 'QUATERNION'
    prev = None
    for k, f in enumerate(frames):
        p = V(pos[k])
        q = (V(target[k]) - p).to_track_quat('-Z', 'Y')
        if prev is not None and q.dot(prev) < 0:
            q.negate()
        prev = q.copy()
        cam.location, cam.rotation_quaternion = p, q
        cam.keyframe_insert('location', frame=f)
        cam.keyframe_insert('rotation_quaternion', frame=f)
        if lens is not None:
            cam.data.lens = float(lens[k])
            cam.data.keyframe_insert('lens', frame=f)
        if focus is not None:
            cam.data.dof.focus_distance = float(focus[k])
            cam.data.dof.keyframe_insert('focus_distance', frame=f)
        if fstop is not None:
            cam.data.dof.aperture_fstop = float(fstop[k])
            cam.data.dof.keyframe_insert('aperture_fstop', frame=f)


def follow(points, start, weight=0.7):
    """Le point que vise une caméra qui suit la balle avec un temps de retard : elle part de `start`
    et rattrape à chaque instant la part `weight` de son écart à la balle."""
    look, out = V(start), []
    for p in points:
        look = look + (V(p) - look) * weight
        out.append(look.copy())
    return out
