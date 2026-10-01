#!/usr/bin/env python3
"""Fabrication outputs for LSR-CTL: Gerbers + drill (zip), pick-and-place, BOM (CSV + Markdown), netlist table.

  python3 hardware/export_fab.py            (after hardware/build_pcb.sh)
Needs kicad-cli (KiCad 7) and, for the PNG previews, gerbv.
"""
import csv, os, subprocess, sys, zipfile, shutil, collections
import pcbnew

HW = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HW, 'pcb', 'lsr_ctl.kicad_pcb')
FAB = os.path.join(HW, 'fab')
G = os.path.join(FAB, 'gerber')
shutil.rmtree(FAB, ignore_errors=True)
os.makedirs(G)

def run(*a):
    subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

run('kicad-cli', 'pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts',
    '--subtract-soldermask', '--use-drill-file-origin', '-o', G + '/', PCB)
run('kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map', '--map-format', 'pdf', '-o', G + '/', PCB)
run('kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '-o', os.path.join(FAB, 'lsr_ctl_pos.csv'), PCB)
run('kicad-cli', 'pcb', 'export', 'pdf', '--layers', 'F.Cu,F.SilkS,F.Fab,Edge.Cuts', '-o', os.path.join(FAB, 'lsr_ctl_assembly_top.pdf'), PCB)
run('kicad-cli', 'pcb', 'export', 'pdf', '--layers', 'B.Cu,B.SilkS,B.Fab,Edge.Cuts', '--mirror', '-o', os.path.join(FAB, 'lsr_ctl_assembly_bottom.pdf'), PCB)
with zipfile.ZipFile(os.path.join(FAB, 'lsr_ctl_gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(G)):
        if not f.endswith('.pdf'):
            z.write(os.path.join(G, f), f)

# ---- BOM from the board (reference, value, footprint, side) + sourcing notes
b = pcbnew.LoadBoard(PCB)
NOTES = {
    'RaspberryPi_Pico_THT': 'Raspberry Pi Pico (or Pico W / Pico 2) + 2x 1x20 headers',
    'Pololu_Breakout-16_15.2x20.3mm': 'TMC2209 StepStick (BTT / FYSETC, UART) + 2x 1x8 female headers + heatsink',
    'PinSocket_2x20_P2.54mm_Vertical': '2x20 female socket, 8.5 mm (mounted on the BOTTOM side)',
    'AMASS_XT30PW-M_1x02_P2.50mm_Horizontal': 'AMASS XT30PW-M (male, PCB right-angle)',
    'BarrelJack_Horizontal': '5.5 x 2.1 mm DC jack',
    'MountingHole_3.2mm_M3': '', 'MountingHole_2.7mm_M2.5': 'Pi Zero standoffs M2.5 x 11 mm',
}
groups = collections.OrderedDict()
for fp in sorted(b.GetFootprints(), key=lambda f: (f.GetReference()[0], int(''.join(c for c in f.GetReference() if c.isdigit()) or 0))):
    key = (fp.GetValue(), fp.GetFPID().GetLibItemName().wx_str())
    groups.setdefault(key, []).append(fp.GetReference())
rows = []
for (val, fpn), refs in groups.items():
    if fpn.startswith('MountingHole'):
        continue
    rows.append(dict(qty=len(refs), refs=' '.join(refs), value=val, footprint=fpn, note=NOTES.get(fpn, '')))
with open(os.path.join(FAB, 'lsr_ctl_bom.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['qty', 'refs', 'value', 'footprint', 'note']); w.writeheader(); w.writerows(rows)
with open(os.path.join(FAB, 'lsr_ctl_bom.md'), 'w') as f:
    f.write('| Qty | Refs | Value | Footprint | Note |\n|---|---|---|---|---|\n')
    for r in rows:
        f.write(f"| {r['qty']} | {r['refs']} | {r['value']} | {r['footprint']} | {r['note']} |\n")

# ---- netlist table (the schematic in table form)
nets = collections.defaultdict(list)
for fp in b.GetFootprints():
    for p in fp.Pads():
        if p.GetNetname():
            nets[p.GetNetname()].append(f'{fp.GetReference()}.{p.GetNumber()}')
with open(os.path.join(FAB, 'lsr_ctl_netlist.md'), 'w') as f:
    f.write('| Net | Pins |\n|---|---|\n')
    for n in sorted(nets):
        f.write(f"| {n} | {' '.join(sorted(nets[n], key=lambda s: (s.split('.')[0], s)))} |\n")

# ---- previews
if shutil.which('gerbv'):
    def render(out, layers, bg):
        args = ['gerbv', '-x', 'png', '-D', '400', '-a', '-b', bg, '-o', out]
        for fn, col in layers:
            args += ['-f', col, os.path.join(G, fn)]
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pre = 'lsr_ctl-'
    render(os.path.join(FAB, 'lsr_ctl_top.png'), [(pre + 'Edge_Cuts.gm1', '#ffffffff'), (pre + 'F_Silkscreen.gto', '#ffffffff'),
           (pre + 'F_Mask.gts', '#c8a24aff'), (pre + 'F_Cu.gtl', '#2f8f4fff')], '#0b3d1e')
    render(os.path.join(FAB, 'lsr_ctl_bottom.png'), [(pre + 'Edge_Cuts.gm1', '#ffffffff'), (pre + 'B_Silkscreen.gbo', '#ffffffff'),
           (pre + 'B_Mask.gbs', '#c8a24aff'), (pre + 'B_Cu.gbl', '#2f8f4fff')], '#0b3d1e')
print('fab outputs in', FAB)
print('\n'.join(sorted(os.listdir(G))))
