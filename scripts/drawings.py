# Dimensioned drawings of the LSR-2 (matplotlib only): one A3 sheet per part, one for the assembly, one exploded with BOM balloons.
# Args: [repo_root] [stl_dir] [out_dir] -> out_dir/<name>.svg and .pdf (STL files written by cad/lsr2/build.py; default out_dir docs/drawings).
# Views are projections of the STL (silhouette, rasterised) with vector dimensions on top; sections cut the mesh with the plane through the AZ axis (y = 0)
# and through the EL axis (z = z_el). Dimensions are read from the geometry (PARAMETRIC); fit and tolerance notes come from cad/lsr2/tolerances.py.
import sys, os, re, struct
import numpy as np
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection, LineCollection
from matplotlib.patches import Circle, Rectangle

here = os.path.dirname(os.path.abspath(__file__))
repo = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(here)
stl_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.environ.get('LSR2_OUT') or repo, 'stl', 'lsr2')
out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(repo, 'docs', 'drawings')
sys.path.insert(0, os.path.join(repo, 'cad', 'lsr2'))
import axes as AX
import parts_table as PT
import tolerances as TL

K = AX.K
ZE = K['z_el']
REV = re.search(r"^REV\s*=\s*'([^']+)'", open(os.path.join(repo, 'cad', 'lsr2', 'params.py'), encoding='utf-8').read(), re.M).group(1)
LOGO = os.path.join(repo, 'branding', 'bricohams_horizontal.png')
BLUE = '#12263f'
AUTHORS = 'Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina'
TOL_NOTE = ('General tolerances ISO 2768-m (machined), ISO 8062-3 CT9-10 (castings).\n'
            'Critical features per docs/LSR2_TOLERANCES.md. Dimensions in mm, PARAMETRIC unless tagged.')
SCALES = (1, 2, 2.5, 5, 10, 20, 25, 50, 100)
SW, SH, PAD = 420.0, 297.0, 14.0   # A3 sheet and per-panel dimension margin, mm
TB_W, TB_H = 180.0, 52.0
NO_DRAW = ('mast', 'yagi_145', 'yagi_435')   # customer items: listed in the legend, not drawn
os.makedirs(out_dir, exist_ok=True)


def read_stl(name):
    cands = (os.path.join(stl_dir, name + '.stl'), os.path.join(stl_dir, 'visual', name + '.stl'))
    path = next((p for p in cands if os.path.exists(p)), None)
    if path is None:
        sys.exit('drawings.py: no STL for %s in %s (run cad/lsr2/build.py with the same LSR2_OUT; bought parts go to stl/lsr2/visual)' % (name, stl_dir))
    data = open(path, 'rb').read()
    n = struct.unpack('<I', data[80:84])[0] if len(data) > 84 else -1
    if n >= 0 and 84 + 50 * n == len(data):
        dt = np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')])
        return np.frombuffer(data, dtype=dt, count=n, offset=84)['v'].astype(float)
    vals = re.findall(rb'vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)', data)
    return np.array(vals).astype(float).reshape(-1, 3, 3)


def cut(tris, axis, c):
    """Segments where the plane coordinate[axis] = c crosses the triangles, as (n, 2, 3)."""
    d = tris[:, :, axis] - c
    pts = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        m = d[:, i] * d[:, j] < 0
        t = d[m, i] / (d[m, i] - d[m, j])
        pts.append((np.nonzero(m)[0], tris[m, i] + (tris[m, j] - tris[m, i]) * t[:, None]))
    seg = {}
    for idx, p in pts:
        for k, q in zip(idx, p):
            seg.setdefault(k, []).append(q)
    return np.array([v[:2] for v in seg.values() if len(v) >= 2]).reshape(-1, 2, 3)


class Sheet:
    def __init__(self, title_part, material, route, note_rows):
        self.fig = plt.figure(figsize=(SW / 25.4, SH / 25.4), facecolor='white')
        self.bg = self.fig.add_axes([0, 0, 1, 1]); self.bg.set_xlim(0, SW); self.bg.set_ylim(0, SH); self.bg.axis('off')
        self.bg.add_patch(Rectangle((10, 10), SW - 20, SH - 20, fill=False, lw=1.0, ec=BLUE))
        self.part, self.material, self.route, self.notes = title_part, material, route, note_rows

    def panel(self, x, y, w, h, tris_by_model, ia, ib, title, scale, cut_plane=None, dims=True, axis_marks=()):
        """x, y: lower-left of the panel on the sheet (mm); w, h: model extents (mm) for ia, ib."""
        allt = np.concatenate([t for t in tris_by_model.values()]) if tris_by_model else np.zeros((0, 3, 3))
        if cut_plane:
            lines = {m: cut(t, *cut_plane) for m, t in tris_by_model.items()}
            allt = np.concatenate([v for v in lines.values() if len(v)] or [np.zeros((0, 2, 3))])
        if len(allt) == 0:
            return False
        lo, hi = allt.reshape(-1, 3).min(0), allt.reshape(-1, 3).max(0)
        pw, ph = (hi[ia] - lo[ia]) / scale + 2 * PAD, (hi[ib] - lo[ib]) / scale + 2 * PAD
        ax = self.fig.add_axes([x / SW, y / SH, pw / SW, ph / SH])
        cx, cy = (lo[ia] + hi[ia]) / 2, (lo[ib] + hi[ib]) / 2
        ax.set_xlim(cx - pw * scale / 2, cx + pw * scale / 2); ax.set_ylim(cy - ph * scale / 2, cy + ph * scale / 2); ax.axis('off')
        for m, t in tris_by_model.items():
            col = PT.COLOURS.get(PT.cat_of(m), '#8a8f98') if m in PT.BY_MODEL else '#8a8f98'
            if cut_plane:
                s = lines[m]
                if len(s):
                    ax.add_collection(LineCollection(s[:, :, [ia, ib]], colors=col, linewidths=0.8))
            else:
                ax.add_collection(PolyCollection(t[:, :, [ia, ib]], facecolors=col, edgecolors=col, linewidths=0.05, alpha=0.55, rasterized=True))
        for k, v, _ in axis_marks:   # (0 horizontal / 1 vertical, value, label): chain lines through the AZ and EL axes
            if k == 1 and lo[ia] <= v <= hi[ia]:
                ax.plot([v, v], [lo[ib] - 4 * scale, hi[ib] + 4 * scale], color='k', lw=0.4, ls=(0, (8, 2, 1, 2)))
            if k == 0 and lo[ib] <= v <= hi[ib]:
                ax.plot([lo[ia] - 4 * scale, hi[ia] + 4 * scale], [v, v], color='k', lw=0.4, ls=(0, (8, 2, 1, 2)))
        if dims:
            self.dim(ax, (lo[ia], lo[ib] - 7 * scale), (hi[ia], lo[ib] - 7 * scale), '%.0f' % (hi[ia] - lo[ia]), scale, lo[ib])
            self.dim(ax, (hi[ia] + 7 * scale, lo[ib]), (hi[ia] + 7 * scale, hi[ib]), '%.0f' % (hi[ib] - lo[ib]), scale, hi[ia], vertical=True)
        ax.text(cx, hi[ib] + 6 * scale, title, ha='center', va='bottom', fontsize=7, color=BLUE, fontweight='bold')
        return ax, lo, hi

    @staticmethod
    def dim(ax, p, q, text, scale, ref, vertical=False):
        ax.annotate('', xy=q, xytext=p, arrowprops=dict(arrowstyle='<->', lw=0.5, color='k', shrinkA=0, shrinkB=0))
        for e in (p, q):
            f = (e[0], ref) if not vertical else (ref, e[1])
            ax.plot([f[0], e[0]], [f[1], e[1]], color='k', lw=0.3)
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        ax.text(m[0], m[1], text, fontsize=6, ha='center', va='bottom' if not vertical else 'center', rotation=90 if vertical else 0,
                bbox=dict(fc='white', ec='none', pad=0.5))

    def title_block(self, scale, sheet_name):
        x0, y0 = SW - 10 - TB_W, 10
        self.bg.add_patch(Rectangle((x0, y0), TB_W, TB_H, fill=True, fc='white', ec=BLUE, lw=0.8, zorder=5))
        if os.path.exists(LOGO):
            im = plt.imread(LOGO)
            lw_ = 50.0
            lh_ = lw_ * im.shape[0] / im.shape[1]
            ax = self.fig.add_axes([(x0 + 3) / SW, (y0 + TB_H - lh_ - 3) / SH, lw_ / SW, lh_ / SH], zorder=6)
            ax.imshow(im); ax.axis('off')
        t = lambda dx, dy, s, **kw: self.bg.text(x0 + dx, y0 + dy, s, fontsize=kw.pop('fs', 6.5), color=BLUE, zorder=7, **kw)
        t(58, TB_H - 7, 'BricoHams · LibreSat LSR-2', fs=10, fontweight='bold')
        t(58, TB_H - 14, self.part, fs=8)
        t(3, 30, 'Material: ' + self.material); t(3, 25, 'Route: ' + self.route)
        t(95, 30, 'REV: ' + REV); t(95, 25, 'Scale: 1:%g (A3)' % scale); t(135, 30, 'Sheet: ' + sheet_name)
        t(3, 19, 'Authors: ' + AUTHORS, fs=5.5)
        self.bg.text(x0 + 3, y0 + 3, TOL_NOTE, fontsize=4.6, color=BLUE, zorder=7, va='bottom')

    def legend(self, x, y):
        for i, c in enumerate(PT.CATEGORIES):
            self.bg.add_patch(Rectangle((x, y - 6 * i), 5, 3.5, fc=PT.COLOURS[c], ec='k', lw=0.3, alpha=0.7))
            self.bg.text(x + 7, y - 6 * i, c, fontsize=6, va='bottom', color=BLUE)

    def note_block(self, x, y, lines, fs=5.6):
        self.bg.text(x, y, '\n'.join(lines), fontsize=fs, va='top', color='k', family='monospace')

    def save(self, name):
        for ext in ('svg', 'pdf'):
            self.fig.savefig(os.path.join(out_dir, name + '.' + ext), dpi=150)
        plt.close(self.fig)
        print('wrote', os.path.join(out_dir, name))


def pick_scale(w, h, d):
    """Smallest standard scale for which front|side|section A (row 1) and top|section B (row 2) fit on the sheet beside the title block."""
    for s in SCALES:
        row1 = (2 * w + d) / s + 6 * PAD
        row2 = (w + d) / s + 4 * PAD
        height = (h + d) / s + 4 * PAD
        if row1 <= SW - 20 and row2 <= SW - 20 - TB_W - 10 and height <= SH - 20:
            return s
    return SCALES[-1]


def tolerance_lines(models):
    names = {re.sub(r'_(neg|pos)$', '', m) for m in models}
    out = []
    for r in TL.ROWS:
        if names & {p.strip() for p in r[2].split(',')}:
            out.append('%s %s %s %s [%s]' % (r[0], r[1], r[4], r[5], r[12]))
    return out


def sheet(name, part, material, route, models, extra_notes=(), marks=True, scale=None, tris=None):
    tris = tris or {m: read_stl(m) for m in models}
    allv = np.concatenate(list(tris.values())).reshape(-1, 3)
    lo, hi = allv.min(0), allv.max(0)
    w, d, h = hi - lo
    s = scale or pick_scale(w, h, d)
    sh = Sheet(part, material, route, [])
    am = [(1, 0.0, 'AZ'), (0, ZE, 'EL')] if marks else []
    am_side = [(0, ZE, 'EL')] if marks else []
    top = SH - 10 - PAD
    x = 10 + PAD
    fr = sh.panel(x, top - (h / s + 2 * PAD) + PAD, w, h, tris, 0, 2, 'FRONT (XZ)', s, axis_marks=am)
    x += w / s + 2 * PAD
    sd = sh.panel(x, top - (h / s + 2 * PAD) + PAD, d, h, tris, 1, 2, 'SIDE (YZ)', s, axis_marks=am_side)
    x += d / s + 2 * PAD
    sh.panel(x, top - (h / s + 2 * PAD) + PAD, w, h, tris, 0, 2, 'SECTION A-A (plane through the AZ axis, y = 0)', s, cut_plane=(1, 0.0), dims=False,
             axis_marks=[(1, 0.0, 'AZ')] if marks else [])
    y2 = 10 + PAD
    sh.panel(10 + PAD, y2, w, d, tris, 0, 1, 'TOP (XY)', s, axis_marks=[(1, 0.0, 'AZ')] if marks else [])
    zc = ZE if lo[2] <= ZE <= hi[2] else (lo[2] + hi[2]) / 2
    sh.panel(10 + 3 * PAD + w / s, y2, w, d, tris, 0, 1, 'SECTION B-B (plane through the EL axis, z = %.0f)' % zc if marks else 'SECTION B-B (mid-height)',
             s, cut_plane=(2, zc), dims=False)
    notes = tolerance_lines(models) + list(extra_notes)
    if notes:
        sh.note_block(SW - 10 - TB_W + 3, 10 + TB_H + 60, ['Features / tolerances:'] + notes[:14], fs=4.6)
    sh.legend(SW - 10 - TB_W + 100, 10 + TB_H + 22)
    sh.title_block(s, name)
    sh.save(name)


def assembly_notes():
    return ['Frame: origin = centre of the body bottom face, AZ = Z, EL axis along Y at z = %.0f (datum A)' % ZE,
            'AZ shaft Ø30 in 2 x 6206 + 51206; EL shaft Ø20 in 2 x 6004 (dedicated bearings, gearboxes transmit torque only)',
            'Mast interface: bracket for tube Ø60.3 x 3.6 (accepts 40-63.5), U-bolts, slip 113 N·m [DATASHEET sizing]',
            'Boom interface: 40 x 40 x 3 tube parallel to the EL axis, saddle %.0f wide, 2 blocks, 8 x M6 [PARAMETRIC]' % K['saddle_h'],
            'Fasteners: lid 10 x M5 (cord gasket 2 x 3), gearbox flange 4 x M6 PCD 65 [MEASURE], mast bracket U-bolts M8',
            'Service clearance: 26 mm air under the shelf for the ball-end key; lid lift 260 mm; drivers on the -y inner wall [PARAMETRIC]',
            'Sweep envelope: EL -30..150 deg, boom radius from the EL axis = boom height; AZ +-360 deg [PARAMETRIC]']


def main():
    head = [m for p in PARTS for m in p['models'] if m not in NO_DRAW]
    for p in PARTS:
        if p['models'][0] in NO_DRAW or p['cat'] == PT.BOUGHT:   # catalogue parts have no fabrication drawing
            continue
        m = p['models']
        sheet('LSR2_part_%02d_%s' % (p['pos'], m[0]), '%02d %s' % (p['pos'], p['label']), p['material'], p['route'], m)
    tris = {m: read_stl(m) for m in head}
    sheet('LSR2_assembly', 'Head assembly (mast and antennas not drawn)', 'see BOM_LSR2', 'A cast / B CNC', head, assembly_notes(), tris=tris)
    exploded(tris)


def exploded(tris):
    """Oblique exploded view: u = y + 0.4 x, v = z + 0.3 x. Balloons = BOM Pos column."""
    T = {}
    for m, t in tris.items():
        t = t.copy()
        t += np.array(PT.EXPLODE.get(m, (0, 0, 0)), float)
        t[:, :, 1] += 0.4 * t[:, :, 0]
        t[:, :, 2] += 0.3 * t[:, :, 0]
        T[m] = t
    allv = np.concatenate(list(T.values())).reshape(-1, 3)
    w, h = allv[:, 1].max() - allv[:, 1].min(), allv[:, 2].max() - allv[:, 2].min()
    s = next((c for c in SCALES if w / c + 2 * 45 + 100 <= SW - 20 and h / c + 2 * PAD + TB_H <= SH - 20), SCALES[-1])
    sh = Sheet('Exploded assembly with BOM balloons', 'see BOM_LSR2', 'A cast / B CNC', [])
    res = sh.panel(10 + 100, 10 + TB_H + 6, w, h, T, 1, 2, 'EXPLODED (oblique view, offsets per cad/lsr2/parts_table.py)', s, dims=False)
    ax, lo, hi = res
    done = set()
    for p in PARTS:
        ms = [m for m in p['models'] if m in T]
        if not ms:
            continue
        v = np.concatenate([T[m].reshape(-1, 3) for m in ms])
        c = np.array([(v[:, 1].min() + v[:, 1].max()) / 2, (v[:, 2].min() + v[:, 2].max()) / 2])
        side = -1 if c[0] < (lo[1] + hi[1]) / 2 else 1
        bx = (hi[1] + 12 * s) if side > 0 else (lo[1] - 12 * s)
        bx += side * (len(done) % 3) * 6 * s
        by = c[1]
        ax.plot([c[0], bx], [c[1], by], color='k', lw=0.3, clip_on=False)
        ax.plot(c[0], c[1], 'k.', ms=1.5)
        ax.add_patch(Circle((bx, by), 3.2 * s, fc='white', ec='k', lw=0.5, zorder=9, clip_on=False))
        ax.text(bx, by, str(p['pos']), fontsize=6, ha='center', va='center', zorder=10, clip_on=False)
        done.add(p['pos'])
    rows = ['%2d  %-30s %-16s %s x%d' % (p['pos'], p['label'], p['cat'], p['ref'] or 'customer', p['qty']) for p in PARTS]
    sh.note_block(10 + 4, SH - 14, ['Pos  Part                           Category         BOM key'] + rows, fs=4.6)
    sh.legend(SW - 10 - TB_W + 100, 10 + TB_H + 22)
    sh.title_block(s, 'LSR2_exploded')
    sh.save('LSR2_exploded')


PARTS = PT.PARTS

if __name__ == '__main__':
    main()
