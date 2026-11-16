# Photoreal Cycles renders of the LSR-2 from the STL files of cad/lsr2/build.py (render, not a photo).
#   blender -b --factory-startup -P scripts/render_blender.py -- <repo_root> <stl_dir> <out_dir> [--samples N]
# stl_dir = <build out>/stl/lsr2 (fabricated parts; stl_dir/visual/<name>.stl, when present, is the finer copy used instead, and holds the
# visual-only bought parts). Scene data (EL axis, groups, exploded offsets, index discs) = build/lsr2_render_scene.json from build.py.
# Output: lsr2_hero.png, lsr2_head_closeup.png, lsr2_exploded_real.png, lsr2_castings_real.png, lsr2_el_sweep_real.png, lsr2_calibration.png
import bpy, sys, os, re, json, math, struct
import numpy as np
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
repo, stl_dir, out_dir = argv[:3]
samples = int(argv[argv.index('--samples') + 1]) if '--samples' in argv else 128
os.makedirs(out_dir, exist_ok=True)
W, H = 1920, 1200
MM = 0.001
SUN_ELEV, SUN_ROT = 35.0, math.radians(200.0)   # sun elevation (deg) and azimuth of the Nishita sky; turn SUN_ROT if the shadows fall the wrong way
SMOOTH_DEG = 30.0
BLUE, ORANGE = '#12263f', '#e8871e'

sc_path = next((p for p in (os.path.join(repo, 'build', 'lsr2_render_scene.json'),
                            os.path.join(stl_dir, '..', '..', 'build', 'lsr2_render_scene.json')) if os.path.exists(p)), None)
if sc_path is None:
    raise SystemExit('lsr2_render_scene.json not found: run make lsr2 first')
S = json.load(open(sc_path, encoding='utf-8'))
EL_P = Vector(S['el_axis']['point']) * MM
EL_D = Vector(S['el_axis']['dir']).normalized()
EL_GROUP = list(S['el_group'])
EXPLODE = {k: Vector(v) * MM for k, v in S['explode'].items()}
FLOOR_Z = S['floor_z'] * MM


# --- scene, colours, materials ---------------------------------------------------------------
def rgba(h, a=1.0):
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    h = h.lstrip('#')
    return tuple(f(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4)) + (a,)


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = W, H, 100
scene.render.film_transparent = False
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGB'
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.cycles.sample_clamp_indirect = 10.0
for attr, val in (('use_adaptive_sampling', True), ('denoiser', 'OPENIMAGEDENOISE'), ('max_bounces', 8), ('transparent_max_bounces', 24)):
    try:
        setattr(scene.cycles, attr, val)
    except Exception:
        pass
for vt in ('AgX', 'Filmic'):
    try:
        scene.view_settings.view_transform = vt
        break
    except TypeError:
        pass


def setup_device():
    scene.cycles.device = 'CPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        for t in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
            try:
                prefs.compute_device_type = t
            except TypeError:
                continue
            (getattr(prefs, 'refresh_devices', None) or prefs.get_devices)()
            gpus = [d for d in prefs.devices if d.type != 'CPU']
            if gpus:
                for d in prefs.devices:
                    d.use = d.type != 'CPU'
                scene.cycles.device = 'GPU'
                return t
        prefs.compute_device_type = 'NONE'
    except Exception as ex:
        print('device setup:', ex)
    return 'CPU'


print('render device:', setup_device(), 'samples', samples)


def pbr(name, color, metallic=0.0, rough=0.5, aniso=0.0, bump=0.0, bump_scale=800.0, stretch=1.0, alpha=1.0, emit=None, emit_k=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')

    def put(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v
    put('Base Color', rgba(color))
    put('Metallic', metallic)
    put('Roughness', rough)
    put('Anisotropic', aniso)
    put('Alpha', alpha)
    if emit:
        put('Emission Color', rgba(emit))
        put('Emission Strength', emit_k)
    if bump > 0:
        tc, mp = nt.nodes.new('ShaderNodeTexCoord'), nt.nodes.new('ShaderNodeMapping')
        tx, bp = nt.nodes.new('ShaderNodeTexNoise'), nt.nodes.new('ShaderNodeBump')
        mp.inputs['Scale'].default_value = (stretch, 1.0, 1.0)
        tx.inputs['Scale'].default_value = bump_scale
        bp.inputs['Strength'].default_value = bump
        bp.inputs['Distance'].default_value = 0.001
        nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
        nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
        nt.links.new(tx.outputs['Fac'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m


def emission(name, color, k):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e, o = nt.nodes.new('ShaderNodeEmission'), nt.nodes.new('ShaderNodeOutputMaterial')
    e.inputs['Color'].default_value = rgba(color)
    e.inputs['Strength'].default_value = k
    nt.links.new(e.outputs['Emission'], o.inputs['Surface'])
    return m


MAT = {
    'alu_brushed': pbr('alu_brushed', '#c9ced3', 1.0, 0.30, aniso=0.5, bump=0.04, bump_scale=900.0, stretch=0.03),   # CNC plates
    'cast_alu': pbr('cast_alu', '#b4b8bc', 1.0, 0.55, bump=0.18, bump_scale=1600.0),                              # bead-blasted A356
    'nmrv': pbr('nmrv', '#bfc5cb', 1.0, 0.48, bump=0.10, bump_scale=1100.0),                                      # NMRV cast housing, silver
    'motor_black': pbr('motor_black', '#16181b', 0.6, 0.45),                                                      # black anodised
    'motor_caps': pbr('motor_caps', '#b0b6bc', 1.0, 0.40, bump=0.06, bump_scale=900.0),
    'stainless': pbr('stainless', '#d0d3d6', 1.0, 0.20),
    'tube': pbr('tube', '#c8cdd2', 1.0, 0.26, aniso=0.4, bump=0.03, bump_scale=700.0, stretch=0.03),               # aluminium tube
    'pla': pbr('pla', ORANGE, 0.0, 0.42),
    'asa': pbr('asa', '#101113', 0.0, 0.50),
    'galv': pbr('galv', '#9ea4aa', 1.0, 0.45, bump=0.35, bump_scale=350.0),
    'rubber': pbr('rubber', '#0b0b0c', 0.0, 0.70),
    'sand': pbr('sand', '#cdb592', 0.0, 0.95, bump=0.3, bump_scale=2500.0),
    'floor': pbr('floor', '#c8c8c4', 0.0, 0.70),
    'glow': emission('glow', ORANGE, 10.0),
    'hi_disc': pbr('hi_disc', ORANGE, 0.0, 0.30, emit=ORANGE, emit_k=0.6),
}


def mat_for(n):
    if n in ('base', 'spacer', 'el_bracket'):
        return 'alu_brushed'
    if n in ('az_housing', 'mast_clamp', 'el_bearing_housing', 'boom_socket'):
        return 'cast_alu'
    if n.endswith('_pattern') or n == 'az_housing_corebox':
        return 'pla'
    if n == 'az_housing_cores':
        return 'sand'
    if n in ('az_shaft', 'el_shaft') or n.endswith('_motor_shaft') or n.startswith('hardware_'):
        return 'stainless'
    if n.endswith('index_disc'):
        return 'asa'
    if n == 'cross_boom' or n.startswith('yagi'):
        return 'tube'
    if n == 'mast':
        return 'galv'
    if n.endswith('_gearbox'):
        return 'nmrv'
    if n.endswith('_motor_body'):
        return 'motor_black'
    if n.endswith('_motor_caps'):
        return 'motor_caps'
    if n.endswith('_motor_cable'):
        return 'rubber'
    return 'cast_alu'


# --- geometry ----------------------------------------------------------------------------------
def read_stl(path):
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0] if len(data) > 84 else -1
    if n >= 0 and 84 + 50 * n == len(data):
        dt = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
        return np.frombuffer(data, dtype=dt, count=n, offset=84)['v'].reshape(-1, 3).astype(np.float64)
    vals = re.findall(rb'vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)', data)
    return np.array(vals).astype(np.float64).reshape(-1, 3)


def new_object(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def smooth(ob):
    # No bpy.ops: context-free smoothing works in background mode on every 4.x/5.x build.
    me = ob.data
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    if hasattr(me, 'set_sharp_from_angle'):          # Blender >= 4.1
        me.set_sharp_from_angle(angle=math.radians(SMOOTH_DEG))
    elif hasattr(me, 'use_auto_smooth'):             # Blender < 4.1
        me.use_auto_smooth = True
        me.auto_smooth_angle = math.radians(SMOOTH_DEG)
    me.update()


def assign(ob, key):
    ob.data.materials.clear()
    ob.data.materials.append(MAT[key] if isinstance(key, str) else key)


OBJ = {}
for n in S['parts']:
    p = next((q for q in (os.path.join(stl_dir, 'visual', n + '.stl'), os.path.join(stl_dir, n + '.stl')) if os.path.exists(q)), None)
    if p is None:
        print('missing STL, skipped:', n)
        continue
    v = read_stl(p) * MM
    if len(v) == 0:
        print('empty STL, skipped:', n)
        continue
    key = np.round(v * 1e6).astype(np.int64)
    _, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    f = np.asarray(inv).reshape(-1).reshape(-1, 3)
    f = f[(f[:, 0] != f[:, 1]) & (f[:, 1] != f[:, 2]) & (f[:, 0] != f[:, 2])]
    ob = new_object(n, v[idx].tolist(), f.tolist())
    assign(ob, mat_for(n))
    smooth(ob)
    OBJ[n] = ob
print('imported', len(OBJ), 'objects')


def box_mm(name, x0, x1, y0, y1, z0, z1, key):
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    v = [(a * MM, b * MM, c * MM) for a, b, c in v]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    ob = new_object(name, v, f)
    assign(ob, key)
    return ob


def cyl_mm(name, r, h, c, axis, key, seg=48):
    v, f = [], []
    for k in range(seg):
        a = 2 * math.pi * k / seg
        v += [(r * math.cos(a), r * math.sin(a), -h / 2), (r * math.cos(a), r * math.sin(a), h / 2)]
    f = [(2 * k, 2 * ((k + 1) % seg), 2 * ((k + 1) % seg) + 1, 2 * k + 1) for k in range(seg)]
    f += [[2 * k + 1 for k in range(seg)], [2 * k for k in reversed(range(seg))]]
    perm = {'z': lambda a, b, c_: (a, b, c_), 'x': lambda a, b, c_: (c_, a, b), 'y': lambda a, b, c_: (b, c_, a)}[axis]
    v = [tuple((perm(*p)[i] + c[i]) * MM for i in range(3)) for p in v]
    ob = new_object(name, v, f)
    assign(ob, key)
    smooth(ob)
    return ob


# calibration extras: photo-interrupters on both index discs and the pinhole sun sight (hidden except in lsr2_calibration.png)
def sensor(tag, to_world, u_s, n_mid, n_base, mat='glow'):
    gap, t = S['index']['gap'], S['index']['t']
    parts = [((u_s - 4, u_s + 7), (-5, 5), (n_mid - gap / 2 - 2.5, n_mid - gap / 2)),
             ((u_s - 4, u_s + 7), (-5, 5), (n_mid + gap / 2, n_mid + gap / 2 + 2.5)),
             ((u_s + 3, u_s + 7), (-5, 5), (n_mid - gap / 2 - 2.5, n_mid + gap / 2 + 2.5)),
             ((u_s + 3, u_s + 7), (-5, 5), (n_base, n_mid - gap / 2 - 2.5))]
    for i, (ur, vr, nr) in enumerate(parts):
        a, b = to_world(ur[0], vr[0], nr[0]), to_world(ur[1], vr[1], nr[1])
        lo, hi = [min(a[k], b[k]) for k in range(3)], [max(a[k], b[k]) for k in range(3)]
        ob = box_mm(f'{tag}_{i}', lo[0], hi[0], lo[1], hi[1], lo[2], hi[2], mat)
        OBJ[ob.name] = ob
        EXTRA.append(ob.name)


EXTRA = []
ix = S['index']
t = ix['t']
sensor('sensor_az', lambda u, v, n: (u, v, n), ix['az']['r_sensor'], (ix['az']['z'][0] + ix['az']['z'][1]) / 2, S['gearbox_top_z'])
sensor('sensor_el', lambda u, v, n: (u, n, v), ix['el']['r_sensor'], ix['el']['y'] + t / 2, S['housing_end_y'])
ys, zs = S['sun_sight']['y'], S['sun_sight']['z']
for ob in (box_mm('sunsight_base', -50, 50, ys - 8, ys + 8, zs, zs + 6, 'asa'), box_mm('sunsight_post', -47, -45, ys - 7, ys + 7, zs + 6, zs + 26, 'asa'),
           cyl_mm('sunsight_target', 12.0, 2.0, (45, ys, zs + 18), 'x', 'glow')):
    OBJ[ob.name] = ob
    EXTRA.append(ob.name)
    EL_GROUP.append(ob.name)
for n in EXTRA:
    OBJ[n].hide_render = True


def plane(name, size, z, key):
    h = size / 2
    ob = new_object(name, [(-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0)], [(0, 1, 2, 3)])
    assign(ob, key)
    ob.location = (0, 0, z)
    return ob


FLOOR = plane('floor', 400.0, FLOOR_Z, 'floor')


# --- world ---------------------------------------------------------------------------------------
def setup_world():
    w = bpy.data.worlds.new('sky')
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes.get('Background')
    try:
        sky = nt.nodes.new('ShaderNodeTexSky')
        sky.sky_type = 'NISHITA'
        sky.sun_elevation = math.radians(SUN_ELEV)
        sky.sun_rotation = SUN_ROT
        nt.links.new(sky.outputs['Color'], bg.inputs['Color'])
        bg.inputs['Strength'].default_value = 1.0
        return
    except Exception as ex:
        print('Nishita sky unavailable, three-point rig:', ex)
    bg.inputs['Color'].default_value = rgba('#9fb3c8')
    bg.inputs['Strength'].default_value = 0.6
    rig = (('key', (3.0, -4.0, 4.0), 900.0, 3.0), ('fill', (-4.0, -2.0, 2.0), 300.0, 4.0), ('rim', (-1.0, 4.0, 3.0), 500.0, 2.0))
    for n, loc, e, size in rig:
        li = bpy.data.lights.new(n, 'AREA')
        li.energy, li.size = e, size
        ob = bpy.data.objects.new(n, li)
        ob.location = loc
        scene.collection.objects.link(ob)
        d = Vector((0, 0, 0)) - Vector(loc)
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


setup_world()
CAM_DATA = bpy.data.cameras.new('cam')
CAM_DATA.sensor_width = 36.0
CAM_DATA.clip_start, CAM_DATA.clip_end = 0.05, 500.0
CAM = bpy.data.objects.new('cam', CAM_DATA)
scene.collection.objects.link(CAM)
scene.camera = CAM


# --- poses ---------------------------------------------------------------------------------------
def el_matrix(deg):
    return Matrix.Translation(EL_P) @ Matrix.Rotation(math.radians(S['el_sign'] * deg), 4, EL_D) @ Matrix.Translation(-EL_P)


def pose(el=0.0, explode=False):
    for n, ob in OBJ.items():
        m = el_matrix(el) if n in EL_GROUP else Matrix.Identity(4)
        if explode and n in EXPLODE:
            m = Matrix.Translation(EXPLODE[n]) @ m
        ob.matrix_world = m


def show(names):
    for n, ob in OBJ.items():
        ob.hide_render = n not in names


def points(objs):
    return [ob.matrix_world @ Vector(c) for ob in objs for c in ob.bound_box]


def frame(pts, direction, lens, m=0.92, mb=0.80):
    """Place the camera along direction (target -> camera) so that every point is inside the frame; the bottom 8 % is left for the caption."""
    fwd = -Vector(direction).normalized()
    right = fwd.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(fwd)
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2
    thx = 18.0 / lens
    thy = thx * H / W
    dist = 0.1
    for p in pts:
        d = p - c
        x, y, z = d.dot(right), d.dot(up), d.dot(fwd)
        dist = max(dist, abs(x) / (thx * m) - z, y / (thy * m) - z, -y / (thy * mb) - z)
    CAM_DATA.lens = lens
    CAM.location = c - fwd * dist
    CAM.rotation_euler = fwd.to_track_quat('-Z', 'Y').to_euler()
    return thx


def caption(thx):
    """Strip at the bottom of the frame, parented to the camera: BricoHams blue text, orange accent."""
    d = 0.3
    wd = 2 * d * thx
    hf = wd * H / W
    hs = 0.07 * hf
    yc = -hf / 2 + hs / 2
    made = []

    def quad(name, x0, x1, y0, y1, z, mat):
        ob = new_object(name, [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)])
        assign(ob, mat)
        made.append(ob)

    bg = emission('cap_bg', '#fcfcfb', 1.8)
    ac = emission('cap_or', ORANGE, 1.3)
    tx = emission('cap_bl', BLUE, 1.0)
    quad('cap_bg', -wd / 2, wd / 2, -hf / 2, -hf / 2 + hs, -d, bg)
    quad('cap_accent', -wd / 2, wd / 2, -hf / 2 + hs, -hf / 2 + hs * 1.12, -d, ac)
    for body, size, x, al in (('BricoHams · LibreSat LSR-2', 0.46, -wd / 2 + 0.03 * wd, 'LEFT'),
                              ('render, not a photo', 0.30, wd / 2 - 0.03 * wd, 'RIGHT')):
        cu = bpy.data.curves.new('cap_text', 'FONT')
        cu.body, cu.size, cu.align_x, cu.align_y = body, hs * size, al, 'CENTER'
        ob = bpy.data.objects.new('cap_text', cu)
        scene.collection.objects.link(ob)
        ob.location = (x, yc, -d + 0.0015)
        ob.data.materials.append(tx)
        made.append(ob)
    for ob in made:
        ob.parent = CAM
        for attr in ('visible_diffuse', 'visible_glossy', 'visible_transmission', 'visible_shadow', 'visible_volume_scatter'):
            if hasattr(ob, attr):
                setattr(ob, attr, False)
    return made


def render(fname, objs, pts, direction, lens, floor_z=None):
    thx = frame(pts, direction, lens)
    FLOOR.location.z = FLOOR_Z if floor_z is None else floor_z
    made = caption(thx)
    scene.render.filepath = os.path.join(out_dir, fname)
    bpy.ops.render.render(write_still=True)
    print('wrote', scene.render.filepath)
    for ob in made:
        bpy.data.objects.remove(ob)


ALL = [n for n in OBJ if n not in EXTRA]
PATTERN = [n for n in ALL if n.endswith('_pattern') or n.startswith('az_housing_core')]
YAGI = ['yagi_145', 'yagi_435', 'hardware_ant']
MASTWARE = ['mast', 'hardware_clamp']
FULL = [n for n in ALL if n not in PATTERN]
HEAD = [n for n in FULL if n not in YAGI + MASTWARE + ['cross_boom']]


def run(fname, names, el, explode, direction, lens, frame_names=None, floor_z=None):
    show(names)
    FLOOR.hide_render = False
    pose(el, explode)
    fr = [OBJ[n] for n in (frame_names or names) if n in OBJ]
    render(fname, names, points(fr), direction, lens, floor_z)


# 1. hero: whole rotator on the mast, both Yagis, EL 30 deg
run('lsr2_hero.png', FULL, 30.0, False, (1.0, -1.15, 0.38), 42)

# 2. close-up of the head like the owner's reference photo, on a table
cl = HEAD + ['cross_boom']
run('lsr2_head_closeup.png', cl, 12.0, False, (0.85, -0.95, 0.55), 50, frame_names=HEAD,
    floor_z=min(p.z for p in points([OBJ[n] for n in HEAD])) - 0.0005)

# 3. exploded along the axes (same offsets as render_lsr2.py)
ex = [n for n in FULL if n not in YAGI + ['mast']]
exo = [OBJ[n] for n in ex]
pose(0.0, True)
zmin = min(p.z for p in points(exo))
run('lsr2_exploded_real.png', ex, 0.0, True, (1.0, -0.45, 0.42), 45, floor_z=zmin - 0.02)

# 4. the four A356 castings next to their PLA patterns, core box and cores, on the floor
cast_pairs = [('az_housing', 'az_housing_pattern'), ('mast_clamp', 'mast_clamp_pattern'),
              ('el_bearing_housing', 'el_bearing_housing_pattern'), ('boom_socket', 'boom_socket_pattern')]
show([n for pair in cast_pairs for n in pair] + ['az_housing_corebox', 'az_housing_cores'])
pose(0.0, False)
cols = [(a, b) for a, b in cast_pairs] + [('az_housing_corebox', 'az_housing_cores')]
bbs = lambda n: points([OBJ[n]])
ext = lambda n: [(min(p[i] for p in bbs(n)), max(p[i] for p in bbs(n))) for i in range(3)]
ydepth = max(e[1][1] - e[1][0] for pair in cols for e in map(ext, pair))
cursor, placed = 0.0, []
for a, b in cols:
    wa, wb = [e[0][1] - e[0][0] for e in map(ext, (a, b))]
    w = max(wa, wb)
    for n, yrow in ((a, 0.0), (b, ydepth + 0.05)):
        e = ext(n)
        dx = cursor + w / 2 - (e[0][0] + e[0][1]) / 2
        dy = yrow - (e[1][0] + e[1][1]) / 2
        OBJ[n].matrix_world = Matrix.Translation((dx, dy, -e[2][0]))
        placed.append(OBJ[n])
    cursor += w + 0.04
FLOOR.hide_render = False
render('lsr2_castings_real.png', [], points(placed), (0.35, -1.0, 0.55), 50, floor_z=0.0)

# 5. EL sweep: the moving group ghosted at -30, 45 and 150 deg about the EL axis
sw_static = [n for n in FULL if n not in EL_GROUP]
show(sw_static)
pose(0.0, False)
ghosts = []
group = [n for n in EL_GROUP if n in OBJ and n not in EXTRA]
for ang, col in ((-30, BLUE), (45, ORANGE), (150, '#2e7d32')):
    gm = pbr(f'ghost{ang}', col, 0.0, 0.35, alpha=0.45)
    for n in group:
        g = bpy.data.objects.new(f'{n}_g{ang}', OBJ[n].data.copy())
        scene.collection.objects.link(g)
        assign(g, gm)
        g.matrix_world = el_matrix(ang)
        ghosts.append(g)
FLOOR.hide_render = False
render('lsr2_el_sweep_real.png', [], points([OBJ[n] for n in sw_static] + ghosts), (0.45, -1.0, 0.2), 38)
for g in ghosts:
    bpy.data.objects.remove(g)

# 6. calibration: index discs, photo-interrupters and sun sight highlighted
cal = HEAD + ['cross_boom'] + EXTRA
show(cal)
pose(20.0, False)
for n in ('az_index_disc', 'el_index_disc'):
    assign(OBJ[n], 'hi_disc')
fr = [OBJ[n] for n in HEAD + [e for e in EXTRA if e.startswith('sunsight')]]
FLOOR.hide_render = False
render('lsr2_calibration.png', cal, points(fr), (0.55, -1.0, 0.75), 50, floor_z=min(p.z for p in points([OBJ[n] for n in HEAD])) - 0.0005)
