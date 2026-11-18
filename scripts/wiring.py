#!/usr/bin/env python3
"""LSR-2 wiring diagram (SVG, pure Python): blocks, pins and wires from firmware/src/config.h and docs/ELECTRONICS.md.
Usage: python scripts/wiring.py [repo_root] [out_dir]   -> out_dir/LSR2_wiring.svg (default docs/drawings)
"""
import os, sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'docs', 'drawings')
W, H = 1240, 800

# block: (x, y, w, title, [pin labels]); wires reference (block, pin index) on its left (L) or right (R) side
BLOCKS = {
    'psu': (30, 70, 190, 'S-400-48 48 V supply + fuse', ['L / N mains', '+48 V', '0 V', 'PE']),
    'cap': (30, 250, 190, '2200 uF 63 V + PWRFAIL opto', ['+48 V', '0 V', 'PC817 + 47k to GP22']),
    'buck': (30, 400, 190, '2 x XL7015 buck 48 V to 12 V / 5 V', ['VIN 48 V', 'GND', 'OUT 5 V']),
    'ctl': (400, 70, 270, 'LSR-CTL (Pico) per config.h (controller: O35)', [
        'GP10 STEP AZ', 'GP11 DIR AZ', 'GP2 EN AZ', 'GP12 STEP EL', 'GP13 DIR EL', 'GP3 EN EL', 'GP22 PWRFAIL',
        'GP20 J9 AZ index (3V3, SIG, GND)', 'GP21 J10 EL index (3V3, SIG, GND)', 'GP0/GP1 UART0 TX/RX (Pi / PC link, 9600 8N1)',
        'GP16/17 J5 AS5600 AZ (SDA/SCL)', 'GP18/19 J7 AS5600 EL (SDA/SCL)', 'VSYS 5 V']),
    'lvl': (400, 460, 270, '3.3 V to 5 V level stage (opto drive)', ['6 inputs from the Pico', '6 outputs to DM542T -', '5 V']),
    'drvaz': (800, 70, 230, 'DM542T AZ', ['PUL+/DIR+/ENA+ to 5 V', 'PUL- / DIR- / ENA-', 'VCC +48 V / GND', 'A+ A- B+ B-']),
    'drvel': (800, 260, 230, 'DM542T EL', ['PUL+/DIR+/ENA+ to 5 V', 'PUL- / DIR- / ENA-', 'VCC +48 V / GND', 'A+ A- B+ B-']),
    'maz': (800, 470, 230, 'Motor AZ 23HS32-4004S', ['coil 1: A+ A-', 'coil 2: B+ B-', 'shield at the driver only']),
    'mel': (800, 600, 230, 'Motor EL 23HS32-4004S', ['coil 1: A+ A-', 'coil 2: B+ B-', 'shield at the driver only']),
    'gl': (1060, 70, 160, 'Deltron 483-0100 glands', ['harness: 48 V + data', 'coax']),
}
WIRES = [  # (src block, pin, dst block, pin, label, colour)
    ('psu', 1, 'cap', 0, '+48 V', '#c00'), ('psu', 2, 'cap', 1, '0 V', '#222'),
    ('cap', 0, 'buck', 0, '+48 V', '#c00'), ('cap', 1, 'buck', 1, '0 V', '#222'),
    ('buck', 2, 'lvl', 2, '5 V', '#080'), ('buck', 2, 'ctl', 12, '5 V (VSYS via D2)', '#080'),
    ('cap', 2, 'ctl', 6, 'PWRFAIL (low = 48 V present)', '#555'),
    ('ctl', 0, 'lvl', 0, 'STEP/DIR/EN x 2', '#06c'), ('lvl', 1, 'drvaz', 1, 'AZ', '#06c'), ('lvl', 1, 'drvel', 1, 'EL', '#06c'),
    ('buck', 2, 'drvaz', 0, '5 V opto +', '#080'), ('cap', 0, 'drvaz', 2, '+48 V', '#c00'), ('cap', 0, 'drvel', 2, '+48 V', '#c00'),
    ('drvaz', 3, 'maz', 0, 'motor cable', '#222'), ('drvel', 3, 'mel', 0, 'motor cable', '#222'),
    ('psu', 0, 'gl', 0, 'supply cable through the harness gland', '#888'),
]
ROW = 22


def box(key):
    x, y, w, t, pins = BLOCKS[key]
    h = 34 + ROW * len(pins)
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fff" stroke="#222" stroke-width="1.5"/>',
         f'<text x="{x + 8}" y="{y + 20}" font-size="13" font-weight="bold" fill="#222">{t}</text>']
    for i, p in enumerate(pins):
        s.append(f'<text x="{x + 8}" y="{y + 44 + ROW * i}" font-size="11" fill="#222">{p}</text>')
    return '\n'.join(s)


def anchor(key, i, right):
    x, y, w, _, _ = BLOCKS[key]
    return (x + (w if right else 0), y + 40 + ROW * i)


def svg():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, sans-serif">',
         f'<rect width="{W}" height="{H}" fill="#fff"/>']
    for a, i, b, j, lab, col in WIRES:
        ax, ay = anchor(a, i, BLOCKS[a][0] < BLOCKS[b][0])
        bx, by = anchor(b, j, BLOCKS[a][0] > BLOCKS[b][0])
        mx = (ax + bx) / 2
        o.append(f'<polyline points="{ax},{ay} {mx},{ay} {mx},{by} {bx},{by}" fill="none" stroke="{col}" stroke-width="1.4"/>')
        o.append(f'<text x="{mx + 3}" y="{(ay + by) / 2 - 3}" font-size="9" fill="{col}">{lab}</text>')
    o += [box(k) for k in BLOCKS]
    o += [f'<rect x="10" y="{H - 62}" width="{W - 20}" height="52" fill="none" stroke="#222"/>',
          f'<text x="20" y="{H - 38}" font-size="14" font-weight="bold">BricoHams · LibreSat LSR-2 · Wiring diagram</text>',
          f'<text x="20" y="{H - 20}" font-size="10">Pins from firmware/src/config.h and docs/ELECTRONICS.md (LSR-2 Mk4 replica, external drivers; the Mk4 Wemos controller is open item O35). Authors: Anatol EA5KAO, Diego EA5JEF, Pedro Roca Molina. '
          'Colours: red 48 V, green 5 V, blue signal, black 0 V. DM542T pin names VERIFY against the driver label.</text>', '</svg>']
    return '\n'.join(o)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'LSR2_wiring.svg'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg())
    print('wiring: wrote', os.path.join(OUT, 'LSR2_wiring.svg'))
