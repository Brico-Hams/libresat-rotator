# Quick matplotlib views of the LSR-2 phase 11 head (body, lid, yoke, saddle, boom, lift arms, counterweights, shafts).
# Args: repo_root stl_dir out_dir -> out_dir/lsr2_assembly.png, lsr2_exploded.png, lsr2_el_sweep.png (STL files written by cad/lsr2/build.py)
import sys, os, math, re, struct
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

repo, stl_dir, out_dir = sys.argv[1:4]
sys.path.insert(0, os.path.join(repo, 'cad', 'lsr2'))
import axes as AX

K = AX.K
BLUE, ORANGE, PLATE, STEEL = '#12263f', '#e8871e', '#9aa7b4', '#d0d6dc'
TITLE = 'BricoHams · LibreSat LSR-2'
STATIC = {'body': PLATE, 'lid': PLATE, 'mast_bracket': PLATE, 'az_shaft': STEEL}
MOVING = {'yoke_arm': PLATE, 'yoke_arm_neg': PLATE, 'saddle': PLATE, 'boom_clamp': PLATE, 'boom_clamp_neg': PLATE, 'boom': STEEL,
          'lift_arm_pos': PLATE, 'lift_arm_neg': PLATE, 'counterweight_pos': STEEL, 'counterweight_neg': STEEL, 'el_shaft': STEEL, 'el_sleeve': STEEL}
EXPLODE = {'lid': (0, 0, 120), 'mast_bracket': (0, 0, -120), 'az_shaft': (0, 0, -80), 'yoke_arm': (0, 60, 0), 'yoke_arm_neg': (0, -60, 0),
           'el_shaft': (0, 0, 80), 'el_sleeve': (0, 0, 80), 'saddle': (0, 0, 60), 'boom': (0, 0, 120), 'boom_clamp': (0, 60, 150),
           'boom_clamp_neg': (0, -60, 150)}
ZE = K['z_el']

def read_stl(name):
    data = open(os.path.join(stl_dir, name + '.stl'), 'rb').read()
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
parts = {**STATIC, **MOVING}
fig = plt.figure(figsize=(14, 8), facecolor='#fcfcfb')
for k, (el, az, title) in enumerate([(25, -60, 'Isometric'), (0, -90, 'Front (XZ)')]):
    ax = fig.add_subplot(1, 2, k + 1, projection='3d')
    for name, col in parts.items():
        add(ax, read_stl(name), col, 0.9)
    frame(ax, title, el, az, HEAD)
save(fig, 'lsr2_assembly.png', 'head assembly (body, yoke, saddle, boom, lift arms, counterweights)')

fig = plt.figure(figsize=(11, 11), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
for name, col in parts.items():
    add(ax, moved(read_stl(name), EXPLODE.get(name, (0, 0, 0))), col, 0.9)
frame(ax, '', 22, -55, ((-400, 400), (-800, 800), (-200, 700)))
save(fig, 'lsr2_exploded.png', 'exploded view (each group moved along its own axis)')

fig = plt.figure(figsize=(10, 10), facecolor='#fcfcfb')
ax = fig.add_subplot(1, 1, 1, projection='3d')
for name, col in STATIC.items():
    add(ax, read_stl(name), col, 0.5)
group = [read_stl(n) for n in MOVING]
for ang, col in ((-30, BLUE), (45, ORANGE), (150, '#2e7d32')):
    for tris in group:
        add(ax, rot_y(tris, ang), col, 0.55)
    ax.text(600 * math.cos(math.radians(ang)), 0, ZE - 600 * math.sin(math.radians(ang)), f'{ang} deg', color=col, fontsize=9)
frame(ax, '', 0, -90, ((-700, 700), (-800, 800), (-300, 800)))
save(fig, 'lsr2_el_sweep.png', 'EL sweep, moving group at -30, 45 and 150 deg (view along the EL axis)')
