#!/usr/bin/env python3
"""Check that every STL is a closed (watertight) solid and sits on the bed (z min = 0)."""
import glob, os, sys
import trimesh
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bad = 0
for f in sorted(glob.glob(os.path.join(ROOT, 'stl', '*', '*.stl'))):
    m = trimesh.load(f)
    ok = m.is_watertight and abs(m.bounds[0][2]) < 0.01
    bad += not ok
    print(f"{'OK ' if ok else 'BAD'} {os.path.relpath(f, ROOT):48s} {m.extents[0]:5.0f} x {m.extents[1]:5.0f} x {m.extents[2]:5.0f} mm")
print(f'{bad} problem(s)')
sys.exit(1 if bad else 0)
