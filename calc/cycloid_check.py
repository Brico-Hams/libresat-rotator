#!/usr/bin/env python3
"""Kinematic check of the printed cycloidal reducer used in the LSR-1 actuator.

Rotates the input (eccentric) through one full disc revolution and verifies that
the disc profile never intersects the ring pins and that the running clearance
stays within the intended band. Also checks output-pin holes and envelope vs bore.
Parameters mirror cad/lsr_params.scad.
"""
import math, sys

N_PINS, R, PIN_D, E, CLR = 26, 36.0, 4.0, 1.0, 0.15
OUT_R, OUT_PIN_D, N_OUT = 22.0, 4.0, 6
BORE_R = R + 0.4


def profile(n=25 * 64):
    Rr = PIN_D / 2 + CLR
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        psi = math.atan2(math.sin((1 - N_PINS) * t), R / (E * N_PINS) - math.cos((1 - N_PINS) * t))
        pts.append((R * math.cos(t) - Rr * math.cos(t + psi) - E * math.cos(N_PINS * t),
                    -R * math.sin(t) + Rr * math.sin(t + psi) + E * math.sin(N_PINS * t)))
    return pts


def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def main():
    prof = profile()
    lobes = N_PINS - 1
    worst_min, worst_max, env = 1e9, 0, 0
    pins = [(R * math.cos(2 * math.pi * k / N_PINS), R * math.sin(2 * math.pi * k / N_PINS)) for k in range(N_PINS)]
    steps = 720
    for s in range(steps):
        th = 2 * math.pi * s / steps          # input angle
        rot = -th / lobes                      # disc rotation (reduction, reversed)
        cx, cy = E * math.cos(th), E * math.sin(th)
        c, si = math.cos(rot), math.sin(rot)
        # The disc profile is generated with the eccentric at angle 0 -> offset so that
        # at th=0 the disc centre is at (E,0): profile is defined about its own centre.
        P = [(cx + x * c - y * si, cy + x * si + y * c) for x, y in prof]
        env = max(env, max(math.hypot(*p) for p in P))
        dmin = 1e9
        for pc in pins:
            # distance from pin centre to polygon
            for i in range(0, len(P)):
                d = seg_dist(pc, P[i - 1], P[i])
                if d < dmin:
                    dmin = d
        gap = dmin - PIN_D / 2
        worst_min = min(worst_min, gap)
        worst_max = max(worst_max, gap)
    hole_d = OUT_PIN_D + 2 * E + 0.3
    web_bore = OUT_R - hole_d / 2 - 13.0
    print(f'lobes={lobes} ratio={lobes}:1 (output reversed)')
    print(f'min pin clearance over a cycle: {worst_min:.3f} mm (target ~{CLR})')
    print(f'disc envelope radius: {env:.2f} mm, bore radius {BORE_R:.2f} -> margin {BORE_R - env:.2f} mm')
    print(f'output hole d={hole_d:.2f} mm, web to cam bearing bore {web_bore:.2f} mm')
    ok = 0.05 < worst_min < 0.3 and BORE_R - env > 0.3 and web_bore > 4
    print('PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
