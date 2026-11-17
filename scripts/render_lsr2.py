# Render the whole LSR-2 (plates, cast parts, shafts, bought-part envelopes) and the cast parts next to their patterns.
# Args: repo_root stl_dir out_dir -> out_dir/lsr2_assembly.png, lsr2_exploded.png, lsr2_patterns.png, lsr2_gearbox.png, lsr2_el_sweep.png (ASCII STL from build.py)
import sys, os, math, struct
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

repo, stl_dir, out_dir = sys.argv[1:4]
cast_dir = os.path.normpath(os.path.join(stl_dir, '..', '..', 'cast', 'lsr2'))   # route A patterns live next to the STL dir

BLUE, ORANGE, PLATE, STEEL, PAT = '#12263f', '#e8871e', '#9aa7b4', '#d0d6dc', '#f4d2a6'
TITLE = 'BricoHams · LibreSat LSR-2'
STATIC = ('body', 'lid', 'mast_bracket')
EL_GROUP = ('yoke_arm', 'yoke_arm_neg', 'saddle', 'boom_clamp', 'boom_clamp_neg', 'boom', 'lift_arm_pos', 'lift_arm_neg',
            'counterweight_pos', 'counterweight_neg', 'el_shaft', 'el_sleeve')
COLOR = {n: PLATE for n in STATIC}
COLOR.update({n: ORANGE for n in ('yoke_arm', 'yoke_arm_neg', 'saddle', 'boom_clamp', 'boom_clamp_neg', 'lift_arm_pos', 'lift_arm_neg',
                                  'counterweight_pos', 'counterweight_neg')})
COLOR.update({n: STEEL for n in ('boom', 'az_shaft', 'el_shaft', 'el_sleeve')})

def read_stl(path):
    data = open(path, 'rb').read()
    if data[:5] == b'solid' and b'facet' in data[:300]:
        tris, cur = [], []
        for line in data.decode('ascii', 'ignore').splitlines():
            w = line.split()
            if w and w[0] == 'vertex':
                cur.append(tuple(map(float, w[1:4])))
                if len(cur) == 3:
                    tris.append(cur); cur = []
        return tris
    n = struct.unpack('<I', data[80:84])[0]
    return [[struct.unpack('<3f', data[96 + 50 * i + 12 * k:108 + 50 * i + 12 * k]) for k in range(3)] for i in range(n)]

load = lambda name: read_stl(os.path.join(stl_dir, name + '.stl'))
moved = lambda tris, d: [[(x + d[0], y + d[1], z + d[2]) for x, y, z in t] for t in tris]

def extent(tris):
    pts = [p for t in tris for p in t]
    return [(min(p[i] for p in pts), max(p[i] for p in pts)) for i in range(3)]

def add(ax, tris, color, alpha, edge='none'):
    ax.add_collection3d(Poly3DCollection(tris, facecolor=color, edgecolor=edge, linewidth=0.15, alpha=alpha))

def frame(ax, tris, view, title):
    e = extent(tris)
    for i, setter in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
        setter(*e[i])
    ax.set_box_aspect([max(b - a, 1.0) for a, b in e]); ax.view_init(*view)
    ax.set_title(title, color=BLUE, fontsize=9)
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')

ALL = {n: load(n) for n in COLOR}
everything = [t for tris in ALL.values() for t in tris]
Z_EL = sum(extent(ALL['el_shaft'])[2]) / 2          # the EL shaft is centred on the EL axis

fig = plt.figure(figsize=(12, 8), facecolor='#fcfcfb')
for k, (view, title) in enumerate([((25, -60), 'Isometric'), ((0, -90), 'Front (XZ)')]):
    ax = fig.add_subplot(1, 2, k + 1, projection='3d')
    for n, tris in ALL.items():
        add(ax, tris, COLOR[n], 0.9)
    frame(ax, everything, view, title)
fig.suptitle(TITLE + ' (body, lid and mast bracket grey, cast arms orange, tubes and shafts steel)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_assembly.png')
fig.savefig(out, dpi=110)
print('wrote', out)

# Exploded isometric: every group moves along its own axis (dx, dy, dz in mm)
SHIFT = {'lid': (0, 0, 120), 'mast_bracket': (0, 0, -120), 'az_shaft': (0, 0, -80), 'yoke_arm': (0, 90, 0), 'yoke_arm_neg': (0, -90, 0),
         'boom_clamp': (0, 90, 60), 'boom_clamp_neg': (0, -90, 60), 'saddle': (0, 0, 60), 'boom': (0, 0, 120),
         'lift_arm_pos': (0, 120, 120), 'lift_arm_neg': (0, -120, 120), 'counterweight_pos': (0, 160, 120), 'counterweight_neg': (0, -160, 120)}
fig = plt.figure(figsize=(11, 11), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
placed = []
for n, tris in ALL.items():
    t2 = moved(tris, SHIFT.get(n, (0, 0, 0)))
    placed += t2
    add(ax, t2, COLOR[n], 0.9)
    e = extent(t2)
    ax.text((e[0][0] + e[0][1]) / 2, (e[1][0] + e[1][1]) / 2, e[2][1] + 6, n, color=BLUE, fontsize=6, ha='center')
frame(ax, placed, (22, -55), TITLE + ': exploded view (each group moved along its own axis)')
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_exploded.png')
fig.savefig(out, dpi=110)
print('wrote', out)

fig = plt.figure(figsize=(18, 10), facecolor='#fcfcfb')
for k, part in enumerate(('body', 'lid', 'mast_bracket', 'yoke_arm', 'saddle', 'boom_clamp')):
    ax = fig.add_subplot(2, 3, k + 1, projection='3d')
    a = read_stl(os.path.join(cast_dir, part + '_finished.stl'))
    b = read_stl(os.path.join(cast_dir, part + '_pattern.stl'))
    ea, eb = extent(a), extent(b)
    b = moved(b, (ea[0][1] - eb[0][0] + 30.0, 0, 0))     # pattern placed beside the part along X
    add(ax, a, ORANGE, 0.85)
    add(ax, b, PAT, 0.9, edge=BLUE)
    frame(ax, a + b, (20, -60), f'{part}  |  {part}_pattern')
fig.suptitle(TITLE + ': cast parts (orange) and PLA patterns (shrink, machining allowance, core prints)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_patterns.png')
fig.savefig(out, dpi=110)
print('wrote', out)

# LSR-WG30 gearbox (phase 7): the two cast halves apart with wheel, worm and bearings in the lower half; skipped without the STLs
GB = ('half_low', 'half_up', 'wheel', 'worm', 'bearings')
if all(os.path.exists(os.path.join(stl_dir, f'gearbox_{k}.stl')) for k in GB):
    g = {k: load(f'gearbox_{k}') for k in GB}
    g['half_up'] = moved(g['half_up'], (0, 0, 60))
    col = {'half_low': PLATE, 'half_up': PLATE, 'wheel': '#b08d57', 'worm': STEEL, 'bearings': BLUE}
    fig = plt.figure(figsize=(12, 7), facecolor='#fcfcfb')
    for k, (view, title) in enumerate([((25, -60), 'Isometric'), ((0, -90), 'Side (XZ)')]):
        ax = fig.add_subplot(1, 2, k + 1, projection='3d')
        for n in GB:
            add(ax, g[n], col[n], 0.35 if n == 'half_up' else 0.9)
        frame(ax, [t for v in g.values() for t in v], view, title)
    fig.suptitle(TITLE + ': LSR-WG30 gearbox, upper half lifted (local frame, output axis Z, worm along X)', color=BLUE)
    fig.tight_layout()
    out = os.path.join(out_dir, 'lsr2_gearbox.png')
    fig.savefig(out, dpi=110)
    print('wrote', out)
# EL sweep: the moving group (boom socket, cross boom, Yagi envelopes) at -30, 45 and 150 deg, seen along the EL axis (+Y)
def rot_y(tris, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[(x * c - (z - Z_EL) * s, y, x * s + (z - Z_EL) * c + Z_EL) for x, y, z in t] for t in tris]

fig = plt.figure(figsize=(10, 10), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
for n in STATIC + ('az_shaft',):
    add(ax, ALL[n], PLATE, 0.5)
swept = []
for ang, col in ((-30, BLUE), (45, ORANGE), (150, '#2e7d32')):
    for n in EL_GROUP:
        t2 = rot_y(ALL[n], ang)
        swept += t2
        add(ax, t2, col, 0.55)
frame(ax, everything + swept, (0, -90), TITLE + ': EL sweep, moving group at -30, 45 and 150 deg (view along the EL axis)')
fig.suptitle(TITLE + ': EL sweep (range -30..150)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_el_sweep.png')
fig.savefig(out, dpi=110)
print('wrote', out)
