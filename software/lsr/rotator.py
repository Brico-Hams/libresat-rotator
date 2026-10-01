"""Client for the LSR-1 controller firmware (Easycomm II + LSR 'X' extensions) and a simulator."""
from __future__ import annotations

import math
import re
import threading
import time


def _num(p: str):
    for f in (int, float):
        try:
            return f(p)
        except ValueError:
            pass
    return p


def parse_xs(line: str) -> dict:
    """Parse the 'XS key=value ...' status line of the firmware."""
    out: dict = {}
    for k, v in re.findall(r'(\w+)=(\S+)', line):
        conv = [_num(p) for p in v.split(',')] if k != 'utc' else [v]
        out[k] = conv[0] if len(conv) == 1 else conv
    return out


ERRORS = {1: 'AZ not referenced (HOME, sun alignment or XCAL AZ=)', 2: 'EL not referenced (check boom IMU)',
          4: 'TMC2209 UART not answering (drivers run on their defaults)', 8: 'magnetic encoder missing / magnet',
          16: 'supply voltage low', 32: 'AZ index magnet not found during HOME'}


def error_text(code: int) -> list[str]:
    return [t for b, t in ERRORS.items() if int(code) & b]


class Rotator:
    """Serial link to the controller. All methods are thread-safe and blocking (short)."""

    def __init__(self, port='/dev/serial0', baud=115200, timeout=0.5, serial_factory=None, **_):
        self.port, self.baud, self.timeout = port, baud, timeout
        self._factory = serial_factory
        self.ser = None
        self.lock = threading.Lock()

    def open(self):
        if self.ser is None:
            if self._factory:
                self.ser = self._factory()
            else:
                import serial
                self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            time.sleep(0.05)
            self.ser.reset_input_buffer()
        return self

    def close(self):
        if self.ser:
            self.ser.close(); self.ser = None

    def _tx(self, line: str, expect: str | None = None, lines: int = 1) -> list[str]:
        with self.lock:
            self.open()
            self.ser.write((line + '\r').encode('ascii'))
            if expect is None:
                return []
            out = []
            t0 = time.time()
            while time.time() - t0 < self.timeout * 2 and len(out) < lines:
                r = self.ser.readline().decode('ascii', 'replace').strip()
                if r.startswith(expect):
                    out.append(r)
            return out

    # ---- Easycomm II
    def get_pos(self) -> tuple[float, float]:
        r = self._tx('AZ EL', 'AZ')
        if not r:
            raise IOError('no answer from the rotator controller')
        m = re.match(r'AZ\s*(-?[\d.]+)\s+EL\s*(-?[\d.]+)', r[0])
        return float(m.group(1)), float(m.group(2))

    def set_pos(self, az: float, el: float):
        self._tx(f'AZ{az:.1f} EL{el:.1f}')

    def set_abs(self, az: float, el: float):
        """Absolute azimuth on the cable-wrap scale (e.g. 0..450): used by the pass planner."""
        self._tx(f'XP {az:.2f} {el:.2f}')

    def stop(self):
        self._tx('SA SE')

    def park(self):
        self._tx('PARK')

    def home(self):
        self._tx('HOME')

    def jog(self, direction: str):
        self._tx({'left': 'ML', 'right': 'MR', 'up': 'MU', 'down': 'MD'}[direction])

    def version(self) -> str:
        r = self._tx('VE', 'VE')
        return r[0][2:] if r else ''

    def status(self) -> dict:
        r = self._tx('XS', 'XS')
        return parse_xs(r[0]) if r else {}

    def cal(self, what: str, value: float | None = None) -> str:
        cmd = f'XCAL {what}' + (f'={value:.3f}' if value is not None else '')
        r = self._tx(cmd, 'XCAL')
        return r[0] if r else ''

    def conf(self, key: str | None = None, value=None) -> list[str]:
        if value is not None:
            return self._tx(f'XC {key}={value}', 'XC')
        return self._tx(f'XC {key or "?"}', 'XC', lines=1 if key else 40)

    def enable(self, on: bool):
        self._tx(f'XE {1 if on else 0}', 'XE')


class SimRotator:
    """Kinematic simulator with the firmware's planner (sqrt profile, limits, wrap): no hardware needed."""

    def __init__(self, vmax_az=20.0, vmax_el=15.0, acc=25.0, az_min=0.0, az_max=450.0, el_min=0.0, el_max=180.0, **_):
        self.pos = [0.0, 90.0]
        self.tgt = [0.0, 90.0]
        self.v = [0.0, 0.0]
        self.vmax = [vmax_az, vmax_el]
        self.acc = acc
        self.lim = [(az_min, az_max), (el_min, el_max)]
        self.t = time.monotonic()
        self.lock = threading.Lock()
        self.errors = 0

    def _update(self):
        now = time.monotonic()
        dt = min(0.5, now - self.t)
        self.t = now
        n = max(1, int(dt / 0.002))
        h = dt / n
        for _ in range(n):
            for a in (0, 1):
                e = self.tgt[a] - self.pos[a]
                vd = 0.0
                if abs(e) > 0.05:
                    vd = math.copysign(min(self.vmax[a], math.sqrt(2 * self.acc * (abs(e) - 0.025))), e)
                dv = max(-self.acc * h, min(self.acc * h, vd - self.v[a]))
                self.v[a] += dv
                if abs(e) <= 0.05 and abs(self.v[a]) < self.acc * h * 2:
                    self.v[a] = 0.0
                self.pos[a] += self.v[a] * h

    def open(self): return self
    def close(self): ...

    def get_pos(self):
        with self.lock:
            self._update()
            return self.pos[0] % 360.0, self.pos[1]

    def set_pos(self, az, el):
        with self.lock:
            self._update()
            cands = [a for a in (az - 360, az, az + 360) if self.lim[0][0] <= a <= self.lim[0][1]]
            self.tgt[0] = min(cands, key=lambda a: abs(a - self.tgt[0])) if cands else self.tgt[0]
            self.tgt[1] = min(max(el, self.lim[1][0]), self.lim[1][1])

    def set_abs(self, az, el):
        with self.lock:
            self._update()
            self.tgt = [min(max(az, self.lim[0][0]), self.lim[0][1]), min(max(el, self.lim[1][0]), self.lim[1][1])]

    def stop(self):
        with self.lock:
            self._update(); self.tgt = list(self.pos)

    def park(self): self.set_abs(0.0, 90.0)
    def home(self): self.set_abs(0.0, self.pos[1])
    def jog(self, d): self.set_abs({'left': self.lim[0][0], 'right': self.lim[0][1]}.get(d, self.pos[0]),
                                   {'up': self.lim[1][1], 'down': self.lim[1][0]}.get(d, self.pos[1]))
    def version(self): return 'SIM 1.0.0'
    def enable(self, on): ...
    def conf(self, key=None, value=None): return []

    def cal(self, what, value=None):
        with self.lock:
            if what == 'AZ' and value is not None:
                self.pos[0] = value; self.tgt[0] = value
            if what == 'EL' and value is not None:
                self.pos[1] = value; self.tgt[1] = value
        return f'XCAL ok az={self.pos[0]:.2f} el={self.pos[1]:.2f}'

    def status(self):
        with self.lock:
            self._update()
            moving = int(any(abs(v) > 0 for v in self.v))
            return dict(az=round(self.pos[0], 2), el=round(self.pos[1], 2), taz=self.tgt[0], tel=self.tgt[1],
                        vaz=round(self.v[0], 2), vel=round(self.v[1], 2), mode=[moving, moving], ref=[1, 1],
                        err=self.errors, vin=13.2, enc=[1, 1], slips=[0, 0], tmc=[1, 1], imu_el=round(self.pos[1], 2),
                        tilt=[0.1, -0.2], gps=[0, 0, 0.0, 0.0, 0.0], utc='', up=0)


def make_rotator(cfg: dict):
    if cfg['rotator'].get('simulate'):
        l = cfg['limits']
        return SimRotator(l['vmax_az'], l['vmax_el'], 25.0, l['az_min'], l['az_max'], l['el_min'], l['el_max'])
    r = cfg['rotator']
    return Rotator(r['port'], r['baud'], r.get('timeout', 0.5))
