# Quick matplotlib views of the LSR-2 phase 11 head (all parts of the parts table, bought parts from stl/lsr2/visual).
# Args: repo_root stl_dir out_dir -> out_dir/lsr2_assembly.png, lsr2_exploded.png, lsr2_el_sweep.png, lsr2_castings.png, lsr2_blanks.png
# (STL files and build/lsr2_render_scene.json are written by cad/lsr2/build.py)
import sys, os, math, re, struct, json
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

repo, stl_dir, out_dir = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, 'cad', 'lsr2'))
import axes as AX
import parts_table as PT

K = AX.K
BLUE = '#12263f'
TITLE = 'BricoHams · LibreSat LSR-2'
MOVING = ['yoke_arm', 'yoke_arm_neg', 'saddle', 'boom_clamp', 'boom_clamp_neg', 'boom', 'lift_arm_pos', 'lift_arm_neg',
          'counterweight_pos', 'counterweight_neg', 'el_shaft', 'el_sleeve']
OUTSIDE = ('mast', 'yagi_145', 'yagi_435')   # too long for the head views
HEAD_MODELS = [m for m in PT.BY_MODEL if m not in OUTSIDE]
EXPLODE = PT.EXPLODE
ZE = K['z_el']
SCENE = next((p for p in (os.path.join(os.environ.get('LSR2_OUT') or repo, 'build', 'lsr2_render_scene.json'),
                          os.path.join(repo, 'build', 'lsr2_render_scene.json')) if os.path.exists(p)), None)
SC = json.load(open(SCENE)) if SCENE else {}

def colour(name):
    return PT.COLOURS[PT.cat_of(name)] if name in PT.BY_MODEL or name.endswith('_pattern') else '#9aa7b4'

def read_stl(name, path=None):
    path = path or next(p for p in (os.path.join(stl_dir, name + '.stl'), os.path.join(stl_dir, 'visual', name + '.stl')) if os.path.exists(p))
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0] if len(data) > 84 else -1
    if n >= 0 and 84 + 50 * n == len(data):
        vals = [struct.unpack_from('<3f', data, 84 + 50 * i + 12 + 12 * j) for i in range(n) for j in range(3)]
    else:
        vals = [tuple(map(float, m)) for m in re.findall(r'vertex\s+(\S+)\s+(\S+)\s+(\S+)', data.decode('ascii', 'ignore'))]
    return [vals[i:i + 3] for i in range(0, len(vals) - 2, 3)]

def moved(tris, d):
    return [[(x + d[0], y + d[1], z + d[2]) for x, y, z in t] for t in tris]

def rot_y(tris, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[(x * c + (z - ZE) * s, y, -x * s + (z - ZE) * c + ZE) for x, y, z in t] for t in tris]

def add(ax, tris, color, alpha):
    ax.add_collection3d(Poly3DCollection(tris, facecolor=color, edgecolor='none', linewidth=0.15, alpha=alpha))

def frame(ax, title, el, az, lim):
    ax.set_xlim(*lim[0]); ax.set_ylim(*lim[1]); ax.set_zlim(*lim[2])
    ax.set_box_aspect([h - l for l, h in lim]); ax.view_init(el, az); ax.set_title(title, color=BLUE)
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')

def save(fig, name, suptitle):
    fig.suptitle(TITLE + ': ' + suptitle, color=BLUE)
    fig.tight_layout()
    out = os.path.join(out_dir, name)
    fig.savefig(out, dpi=110)
    print('wrote', out)

HEAD = ((-400, 400), (-750, 750), (-60, 560))
fig = plt.figure(figsize=(14, 8), facecolor='#fcfcfb')
for k, (el, az, title) in enumerate([(25, -60, 'Isometric'), (0, -90, 'Front (XZ)')]):
    ax = fig.add_subplot(1, 2, k + 1, projection='3d')
    for name in HEAD_MODELS:
        add(ax, read_stl(name), colour(name), 0.9)
    frame(ax, title, el, az, HEAD)
save(fig, 'lsr2_assembly.png', 'head assembly, colour = bought / machined / cast / printed pattern')

fig = plt.figure(figsize=(11, 11), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
for name in HEAD_MODELS + ['mast']:
    add(ax, moved(read_stl(name), EXPLODE.get(name, (0, 0, 0))), colour(name), 0.9)
frame(ax, '', 22, -55, ((-400, 400), (-800, 800), (-700, 700)))
save(fig, 'lsr2_exploded.png', 'exploded view (each group moved along its own axis)')

fig = plt.figure(figsize=(10, 10), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
for name in HEAD_MODELS:
    if name not in MOVING:
        add(ax, read_stl(name), '#9aa7b4', 0.5)
group = [read_stl(n) for n in MOVING]
for ang, col in ((-30, BLUE), (45, '#2e7d32'), (150, '#8a3b8a')):
    for tris in group:
        add(ax, rot_y(tris, ang), col, 0.55)
    ax.text(600 * math.cos(math.radians(ang)), 0, ZE - 600 * math.sin(math.radians(ang)), f'{ang} deg', color=col, fontsize=9)
frame(ax, '', 0, -90, ((-700, 700), (-800, 800), (-300, 800)))
save(fig, 'lsr2_el_sweep.png', 'EL sweep, moving group at -30, 45 and 150 deg (view along the EL axis)')

def route_figure(parts, folder, suffix, name, what):
    fig = plt.figure(figsize=(14, 8), facecolor='#fcfcfb')
    ax = fig.add_subplot(1, 1, 1, projection='3d')
    x = 0.0
    for p in parts:
        f = os.path.join(folder, p + suffix + '.stl')
        if not os.path.exists(f):
            continue
        t = read_stl(p, f)
        xs = [v[0] for tri in t for v in tri]; ys = [v[1] for tri in t for v in tri]; zs = [v[2] for tri in t for v in tri]
        t = moved(t, (x - min(xs), -(min(ys) + max(ys)) / 2, -min(zs)))
        add(ax, t, colour(p + suffix if suffix == '_pattern' else p), 0.9)
        x += max(xs) - min(xs) + 40
    frame(ax, '', 20, -60, ((0, max(x, 100)), (-250, 250), (0, 400)))
    save(fig, name, what)

if SC.get('cast_parts'):
    route_figure(SC['cast_parts'], SC['cast_dir'], '_pattern', 'lsr2_castings.png', 'route A, printed patterns for the castings')
if SC.get('cnc_parts'):
    route_figure(SC['cnc_parts'], SC['cnc_dir'], '_blank', 'lsr2_blanks.png', 'route B, CNC blanks')

