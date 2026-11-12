# Essai de faisabilité (pas le film) : une balle sur son tee, de vrais brins d'herbe et un ciel physique,
# rendus avec Cycles sur CPU sans aucun fichier téléchargé. Sert à mesurer le temps par image.
#   pip install bpy numpy && python render/probe.py -- --w 960 --h 540 --samples 16 --out probe.png [--mb]
import argparse
import math
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1 :] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--w', type=int, default=960)
ap.add_argument('--h', type=int, default=540)
ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--out', default='probe.png')
ap.add_argument('--mb', action='store_true')
ap.add_argument('--blades', type=int, default=900000)
args = ap.parse_args(argv)
T0 = time.time()

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = args.samples
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.03
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.max_bounces = 6
scene.render.resolution_x, scene.render.resolution_y = args.w, args.h
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
try:
    scene.view_settings.look = 'AgX - Medium High Contrast'
except TypeError:
    pass
print('threads', scene.render.threads, 'version', bpy.app.version_string)

# ---- sky: built-in physical sky, low sun
world = bpy.data.worlds.new('W')
scene.world = world
world.use_nodes = True
wn, wl = world.node_tree.nodes, world.node_tree.links
sky = wn.new('ShaderNodeTexSky')
types = [e.identifier for e in sky.bl_rna.properties['sky_type'].enum_items]
print('sky types:', types)
for t in ('MULTIPLE_SCATTERING', 'NISHITA', 'SINGLE_SCATTERING', 'HOSEK_WILKIE'):
    if t in types:
        sky.sky_type = t
        break
print('sky used:', sky.sky_type, [p.identifier for p in sky.bl_rna.properties if not p.is_readonly][:30])
for k, v in dict(sun_elevation=math.radians(9), sun_rotation=math.radians(205), sun_size=math.radians(1.2), sun_intensity=1.0, air_density=1.0, altitude=0.0).items():
    if hasattr(sky, k):
        setattr(sky, k, v)
wl.new(sky.outputs[0], wn['Background'].inputs['Color'])
wn['Background'].inputs['Strength'].default_value = 0.12
scene.view_settings.exposure = 0.6


def mat(name, color, rough=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    return m, b


# ---- ground with gentle relief
bpy.ops.mesh.primitive_grid_add(x_subdivisions=200, y_subdivisions=200, size=120)
ground = bpy.context.object
co = np.zeros(len(ground.data.vertices) * 3)
ground.data.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
co[:, 2] = 0.9 * np.sin(co[:, 0] / 17.0) * np.cos(co[:, 1] / 23.0) * np.clip(np.hypot(co[:, 0], co[:, 1]) / 20.0, 0, 1)
ground.data.vertices.foreach_set('co', co.ravel())
gm, gb = mat('turf', (0.03, 0.09, 0.015), 0.85)
nt = gm.node_tree
noise = nt.nodes.new('ShaderNodeTexNoise')
noise.inputs['Scale'].default_value = 40
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.018, 0.065, 0.012, 1)
ramp.color_ramp.elements[1].color = (0.05, 0.14, 0.02, 1)
nt.links.new(noise.outputs[0], ramp.inputs[0])
nt.links.new(ramp.outputs[0], gb.inputs['Base Color'])
ground.data.materials.append(gm)
bpy.ops.object.shade_smooth()

# ---- grass: real blades as mesh near the camera (3 quads each, bent, tapered), numpy-built
rng = np.random.default_rng(7)
N = args.blades
R = 5.5
r = R * np.sqrt(rng.random(N)) * (0.25 + 0.75 * rng.random(N))  # denser near the centre
a = rng.random(N) * 2 * math.pi
bx, by = r * np.cos(a), r * np.sin(a) - 1.0
h = (0.016 + 0.014 * rng.random(N)) * (1.0 + 0.5 * np.clip((r - 2.5) / 3.0, 0, 1))
wdt = 0.0013 + 0.0009 * rng.random(N)
yaw = rng.random(N) * 2 * math.pi
lean = 0.25 + 0.5 * rng.random(N)
SEG = 3
verts = np.zeros((N, (SEG + 1) * 2, 3), dtype=np.float32)
for s in range(SEG + 1):
    t = s / SEG
    w = wdt * (1 - 0.85 * t)
    fwd = lean * h * t * t
    z = h * t * (1 - 0.15 * t)
    cx, cy = np.cos(yaw), np.sin(yaw)
    for side, sg in enumerate((-1, 1)):
        verts[:, s * 2 + side, 0] = bx + cx * fwd - cy * w * sg
        verts[:, s * 2 + side, 1] = by + cy * fwd + cx * w * sg
        verts[:, s * 2 + side, 2] = z
faces = np.zeros((N, SEG, 4), dtype=np.int32)
base = (np.arange(N) * (SEG + 1) * 2)[:, None]
for s in range(SEG):
    faces[:, s, :] = base + np.array([s * 2, s * 2 + 1, s * 2 + 3, s * 2 + 2])
me = bpy.data.meshes.new('grass')
me.vertices.add(N * (SEG + 1) * 2)
me.vertices.foreach_set('co', verts.ravel())
me.loops.add(N * SEG * 4)
me.loops.foreach_set('vertex_index', faces.ravel())
me.polygons.add(N * SEG)
me.polygons.foreach_set('loop_start', np.arange(N * SEG, dtype=np.int32) * 4)
me.polygons.foreach_set('loop_total', np.full(N * SEG, 4, dtype=np.int32))
me.update()
me.validate()
grass = bpy.data.objects.new('grass', me)
scene.collection.objects.link(grass)
bm_, bb = mat('blade', (0.045, 0.16, 0.02), 0.45)
nt = bm_.node_tree
info = nt.nodes.new('ShaderNodeNewGeometry')
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].color = (0.03, 0.11, 0.012, 1)
ramp.color_ramp.elements[1].color = (0.11, 0.26, 0.03, 1)
nt.links.new(info.outputs['Random Per Island'], ramp.inputs[0])
nt.links.new(ramp.outputs[0], bb.inputs['Base Color'])
for name, val in (('Subsurface Weight', 0.0), ('Transmission Weight', 0.0), ('Sheen Weight', 0.3)):
    if name in bb.inputs:
        bb.inputs[name].default_value = val
# light passing through the blades (backlit grass)
tr = nt.nodes.new('ShaderNodeBsdfTranslucent')
tr.inputs['Color'].default_value = (0.25, 0.55, 0.06, 1)
mix = nt.nodes.new('ShaderNodeMixShader')
mix.inputs[0].default_value = 0.35
out = nt.nodes['Material Output']
nt.links.new(bb.outputs[0], mix.inputs[1])
nt.links.new(tr.outputs[0], mix.inputs[2])
nt.links.new(mix.outputs[0], out.inputs['Surface'])
me.materials.append(bm_)

# ---- ball (dimples as bump for the probe) on a wooden tee
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=0.02135, location=(0, -1.0, 0.058))
ball = bpy.context.object
bpy.ops.object.shade_smooth()
wm, wb = mat('ball', (0.86, 0.86, 0.84), 0.22)
nt = wm.node_tree
if 'Coat Weight' in wb.inputs:
    wb.inputs['Coat Weight'].default_value = 0.6
    wb.inputs['Coat Roughness'].default_value = 0.08
if 'Subsurface Weight' in wb.inputs:
    wb.inputs['Subsurface Weight'].default_value = 0.15
    wb.inputs['Subsurface Radius'].default_value = (0.004, 0.004, 0.004)
tc = nt.nodes.new('ShaderNodeTexCoord')
vor = nt.nodes.new('ShaderNodeTexVoronoi')
vor.inputs['Scale'].default_value = 330
ramp = nt.nodes.new('ShaderNodeValToRGB')
ramp.color_ramp.elements[0].position = 0.25
ramp.color_ramp.elements[1].position = 0.75
bump = nt.nodes.new('ShaderNodeBump')
bump.inputs['Strength'].default_value = 0.9
bump.inputs['Distance'].default_value = 0.0006
nt.links.new(tc.outputs['Object'], vor.inputs['Vector'])
nt.links.new(vor.outputs['Distance'], ramp.inputs[0])
nt.links.new(ramp.outputs[0], bump.inputs['Height'])
nt.links.new(bump.outputs[0], wb.inputs['Normal'])
ball.data.materials.append(wm)
bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.0022, radius2=0.0058, depth=0.055, location=(0, -1.0, 0.012))
tee = bpy.context.object
tm, _ = mat('tee', (0.55, 0.36, 0.17), 0.5)
tee.data.materials.append(tm)
bpy.ops.object.shade_smooth()

# ---- a flag far away + tree-line stand-ins, to see how distance reads through depth of field
pm, _ = mat('pin', (0.9, 0.85, 0.2), 0.4)
bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=2.2, location=(6, 46, 1.4))
bpy.context.object.data.materials.append(pm)
fm, _ = mat('flag', (0.85, 0.08, 0.05), 0.6)
bpy.ops.mesh.primitive_plane_add(size=1, location=(6.28, 46, 2.3), rotation=(math.radians(90), 0, 0))
bpy.context.object.scale = (0.55, 0.36, 1)
bpy.context.object.data.materials.append(fm)
lm, _ = mat('leaf', (0.02, 0.06, 0.015), 0.8)
for i in range(46):
    x = -60 + i * 2.7 + rng.random() * 2
    y = 62 + rng.random() * 14
    s = 5 + rng.random() * 6
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=(x, y, s * 0.9))
    o = bpy.context.object
    o.scale = (s * 0.7, s * 0.7, s)
    o.data.materials.append(lm)

# ---- camera: low, long lens, shallow depth of field
cd = bpy.data.cameras.new('cam')
cd.lens = 85
cd.sensor_width = 36
cd.dof.use_dof = True
cd.dof.aperture_fstop = 2.8
cd.dof.focus_distance = 0.86
cam = bpy.data.objects.new('cam', cd)
scene.collection.objects.link(cam)
cam.location = (-0.32, -1.80, 0.10)
d = Vector((0.05, -1.0, 0.07)) - cam.location
cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
scene.camera = cam
if args.mb:
    scene.render.use_motion_blur = True
    scene.render.motion_blur_shutter = 0.5
    cam.keyframe_insert('location', frame=1)
    cam.location = (-0.30, -1.72, 0.105)
    cam.keyframe_insert('location', frame=2)
    scene.frame_set(1)

T1 = time.time()
scene.render.filepath = args.out
bpy.ops.render.render(write_still=True)
T2 = time.time()
print(f'RESULT build={T1 - T0:.1f}s render={T2 - T1:.1f}s {args.w}x{args.h} spp={args.samples} blades={N} mb={args.mb}')
