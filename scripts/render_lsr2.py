# Render the whole LSR-2 (plates, cast parts, shafts, bought-part envelopes) and the cast parts next to their patterns.
# Args: repo_root stl_dir out_dir -> out_dir/lsr2_assembly.png, lsr2_exploded.png, lsr2_patterns.png (ASCII STL from build.py)
import sys, os
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

repo, stl_dir, out_dir = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, 'cad', 'lsr2'))
import plates as PL

BLUE, ORANGE, PLATE, MOTOR, STEEL, PAT = '#12263f', '#e8871e', '#9aa7b4', '#5b6b7b', '#d0d6dc', '#f4d2a6'
TITLE = 'BricoHams · LibreSat LSR-2'
CAST = ('az_housing', 'mast_clamp', 'el_hub_a', 'el_hub_b')
SHAFTS = ('az_shaft', 'el_shaft')

def read_stl(name):
    tris, cur = [], []
    for line in open(os.path.join(stl_dir, name + '.stl')):
        w = line.split()
        if w and w[0] == 'vertex':
            cur.append(tuple(map(float, w[1:4])))
            if len(cur) == 3:
                tris.append(cur); cur = []
    return tris

def box_faces(b):
    x0, x1, y0, y1, z0, z1 = b
    v = [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)]
    f = [(0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,3,7,4)]
    return [[v[i] for i in q] for q in f]

def shifted(tris, dx):
    return [[(x + dx, y, z) for x, y, z in t] for t in tris]

def extent(tris):
    pts = [p for t in tris for p in t]
    return [(min(p[i] for p in pts), max(p[i] for p in pts)) for i in range(3)]

def add(ax, tris, color, alpha, edge='none'):
    ax.add_collection3d(Poly3DCollection(tris, facecolor=color, edgecolor=edge, linewidth=0.15, alpha=alpha))

fig = plt.figure(figsize=(12, 8), facecolor='#fcfcfb')
for k, (el, az, title) in enumerate([(25, -60, 'Isometric'), (0, -90, 'Front (XZ)')]):
    ax = fig.add_subplot(1, 2, k + 1, projection='3d')
    for name in PL.PLATES:
        add(ax, read_stl(name), PLATE, 0.25 if name == 'side_a' else 0.9)
    for name in CAST:
        add(ax, read_stl(name), ORANGE, 0.85)
    for name in SHAFTS:
        add(ax, read_stl(name), STEEL, 1.0)
    for name, b in PL.ENVELOPES.items():
        col = MOTOR if 'motor' in name else BLUE
        ax.add_collection3d(Poly3DCollection(box_faces(b), facecolor=col, edgecolor='k', linewidth=0.3, alpha=0.55))
    ax.set_xlim(-190, 190); ax.set_ylim(-190, 190); ax.set_zlim(-250, 200)
    ax.view_init(el, az); ax.set_title(title, color=BLUE); ax.set_box_aspect((380, 380, 450))
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
fig.suptitle(TITLE + ' (plates grey, cast orange, gearboxes blue, NEMA23 grey, shafts steel)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_assembly.png')
fig.savefig(out, dpi=110)
print('wrote', out)

def moved(tris, d):
    return [[(x + d[0], y + d[1], z + d[2]) for x, y, z in t] for t in tris]

# Exploded isometric: every group moves along its own axis (dx, dy, dz in mm)
SHIFT = {'top': (0, 0, 110), 'side_a': (0, 60, 0), 'side_b': (0, -60, 0), 'el_hub_a': (0, 120, 0), 'el_hub_b': (0, -120, 0),
         'az_housing': (0, 0, -50), 'az_shaft': (0, 0, -100), 'el_shaft': (0, 0, -180), 'mast_clamp': (0, 0, -200)}
fig = plt.figure(figsize=(11, 11), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
parts = [(n, read_stl(n), PLATE) for n in PL.PLATES] + [(n, read_stl(n), ORANGE) for n in CAST] + \
        [(n, read_stl(n), STEEL) for n in SHAFTS] + \
        [(n, [t for f in box_faces(b) for t in ([f[:3], [f[0], f[2], f[3]]])], MOTOR if 'motor' in n else BLUE)
         for n, b in PL.ENVELOPES.items()]
for name, tris, col in parts:
    tris = moved(tris, SHIFT.get(name, (0, 0, 0)))
    add(ax, tris, col, 0.5 if name.endswith(('gearbox', 'motor')) else 0.9, edge='none')
    e = extent(tris)
    ax.text((e[0][0] + e[0][1]) / 2, (e[1][0] + e[1][1]) / 2, e[2][1] + 6, name, color=BLUE, fontsize=6, ha='center')
ax.plot([0, 0], [0, 0], [-450, 320], color=ORANGE, linestyle=':', linewidth=0.8)   # AZ axis
ax.set_xlim(-200, 200); ax.set_ylim(-260, 260); ax.set_zlim(-450, 320)
ax.view_init(22, -55); ax.set_box_aspect((400, 520, 770))
ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
fig.suptitle(TITLE + ': exploded view (each group moved along its own axis)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_exploded.png')
fig.savefig(out, dpi=110)
print('wrote', out)

fig = plt.figure(figsize=(14, 5), facecolor='#fcfcfb')
for k, (part, pat) in enumerate([('az_housing', 'az_housing_pattern'), ('mast_clamp', 'mast_clamp_pattern'),
                                 ('el_hub_a', 'el_hub_pattern')]):
    ax = fig.add_subplot(1, 3, k + 1, projection='3d')
    a, b = read_stl(part), read_stl(pat)
    ea, eb = extent(a), extent(b)
    dx = ea[0][1] - eb[0][0] + 30.0                 # pattern placed beside the part along X
    b = shifted(b, dx)
    add(ax, a, ORANGE, 0.85)
    add(ax, b, PAT, 0.9, edge=BLUE)
    lo = [min(ea[i][0], eb[i][0] + (dx if i == 0 else 0)) for i in range(3)]
    hi = [max(ea[i][1], eb[i][1] + (dx if i == 0 else 0)) for i in range(3)]
    for i, setter in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
        setter(lo[i], hi[i])
    ax.set_box_aspect([h - l for l, h in zip(lo, hi)]); ax.view_init(20, -60)
    ax.set_title(f'{part}  |  {pat}', color=BLUE, fontsize=9)
fig.suptitle(TITLE + ': cast parts (orange) and PLA patterns (shrink, machining allowance, core prints)', color=BLUE)
fig.tight_layout()
out = os.path.join(out_dir, 'lsr2_patterns.png')
fig.savefig(out, dpi=110)
print('wrote', out)
