"""Client for the LSR controller firmware (LSR-1 and LSR-2; Easycomm II + LSR 'X' extensions) and a simulator."""
from __future__ import annotations

import logging
import math
import re
import threading
import time

from . import control
from .config import AZ_WIRE_OFFSET
from .pointing import Pointing, wrap180

log = logging.getLogger('lsr.rotator')


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

    def __init__(self, port='/dev/serial0', baud=115200, timeout=0.5, serial_factory=None, model='lsr1', **_):
        self.port, self.baud, self.timeout = port, baud, timeout
        self.model = model
        self.az_off = AZ_WIRE_OFFSET.get(model, 0.0)       # wire azimuth = user azimuth + az_off
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
        return float(m.group(1)) - self.az_off, float(m.group(2))

    def set_pos(self, az: float, el: float):
        if self.az_off:
            az %= 360.0          # the firmware picks the wrap closest to the current azimuth
        self._tx(f'AZ{az:.1f} EL{el:.1f}')

    def set_abs(self, az: float, el: float):
        """Absolute azimuth on the cable-wrap scale (LSR-1 0..450, LSR-2 -360..360): used by the pass planner."""
        self._tx(f'XP {az + self.az_off:.2f} {el:.2f}')

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
        st = parse_xs(r[0]) if r else {}
        if self.az_off:
            for k in ('az', 'taz'):
                if isinstance(st.get(k), (int, float)):
                    st[k] = round(st[k] - self.az_off, 2)
        return st

    def cal(self, what: str, value: float | None = None) -> str:
        cmd = f'XCAL {what}' + (f'={value:.3f}' if value is not None else '')
        r = self._tx(cmd, 'XCAL')
        return r[0] if r else ''

    def raw(self) -> dict:
        """Raw sensor readings (firmware 'XR'): base/boom accelerometer in g, magnetometer (None: not fitted), output
        encoder and step-count angles, index levels, backlash. Azimuths are in the user frame."""
        r = self._tx('XR', 'XR')
        if not r:
            return {}
        d = parse_xs(r[0])
        out = dict(acc_base=d.get('accb'), acc_boom=d.get('accl'),
                   mag=d.get('mag') if isinstance(d.get('mag'), list) else None,
                   enc=list(d.get('enc', [])), step=list(d.get('step', [])), idx=d.get('idx'), backlash=d.get('bl'))
        for k in ('enc', 'step'):
            if len(out[k]) == 2 and self.az_off and math.isfinite(out[k][0]):
                out[k][0] -= self.az_off
        return out

    def conf(self, key: str | None = None, value=None) -> list[str]:
        if value is not None:
            return self._tx(f'XC {key}={value}', 'XC')
        return self._tx(f'XC {key or "?"}', 'XC', lines=1 if key else 40)

    def enable(self, on: bool):
        self._tx(f'XE {1 if on else 0}', 'XE')


class SimRotator:
    """Kinematic simulator with the firmware's planner (sqrt profile, limits, wrap): no hardware needed."""

    def __init__(self, vmax_az=20.0, vmax_el=15.0, acc=25.0, az_min=0.0, az_max=450.0, el_min=0.0, el_max=180.0,
                 model='lsr1', clock=None, backlash=(0.0, 0.0), mount_tilt=(0.0, 0.0), **_):
        self.model = model
        clock = clock or (lambda: time.monotonic())     # late-bound so patching time.monotonic drives the sim
        self.clock = clock
        self.pos = [0.0, 90.0]
        self.tgt = [0.0, 90.0]
        self.v = [0.0, 0.0]
        self.vmax = [vmax_az, vmax_el]
        self.acc = acc
        self.lim = [(az_min, az_max), (el_min, el_max)]
        self.t = clock()
        self.lock = threading.Lock()
        self.errors = 0
        # output-encoder simulation: enc = pos + enc_off - dir * backlash / 2 (enc_off < 0: lost steps / stall)
        self.backlash = list(backlash)
        self.enc_off = [0.0, 0.0]
        self.dir = [1, 1]
        self.stalled = [False, False]
        self.mount_tilt = mount_tilt            # (tilt_n, tilt_e) deg of the simulated base, seen by the base accelerometer

    def _update(self):
        now = self.clock()
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
                if self.v[a]:
                    self.dir[a] = 1 if self.v[a] > 0 else -1
                    if self.stalled[a]:
                        self.enc_off[a] -= self.v[a] * h

    def inject_step_loss(self, axis: int, deg: float):
        """The output lags the step count by `deg` (as after lost steps)."""
        with self.lock:
            self.enc_off[axis] -= deg

    def stall(self, axis: int, on: bool = True):
        with self.lock:
            self.stalled[axis] = on

    def raw(self):
        with self.lock:
            self._update()
            enc = [self.pos[a] + self.enc_off[a] - self.dir[a] * self.backlash[a] / 2 for a in (0, 1)]
            tn, te = (math.radians(x) for x in self.mount_tilt)
            el = math.radians(self.pos[1])
            return dict(acc_base=[-math.sin(tn), -math.cos(tn) * math.sin(te), math.cos(tn) * math.cos(te)],
                        acc_boom=[0.0, math.sin(el), math.cos(el)], mag=None, enc=enc, step=list(self.pos),
                        idx=[0, 0], backlash=list(self.backlash))

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
                self.pos[0] = value; self.tgt[0] = value; self.enc_off[0] = 0.0
            if what == 'EL' and value is not None:
                self.pos[1] = value; self.tgt[1] = value; self.enc_off[1] = 0.0
        return f'XCAL ok az={self.pos[0]:.2f} el={self.pos[1]:.2f}'

    def status(self):
        with self.lock:
            self._update()
            moving = int(any(abs(v) > 0 for v in self.v))
            return dict(az=round(self.pos[0], 2), el=round(self.pos[1], 2), taz=self.tgt[0], tel=self.tgt[1],
                        vaz=round(self.v[0], 2), vel=round(self.v[1], 2), mode=[moving, moving], ref=[1, 1],
                        err=self.errors, vin=13.2, enc=[1, 1], slips=[0, 0], tmc=[1, 1], imu_el=round(self.pos[1], 2),
                        tilt=[0.1, -0.2], gps=[0, 0, 0.0, 0.0, 0.0], utc='', up=0)


class CorrectedRotator:
    """Transparent wrapper around Rotator / SimRotator: pointing correction (commanded: sky -> mount, reported: mount ->
    sky), soft limits, deadband, optional velocity feed-forward for set_pos callers (rotctld/Gpredict send the CURRENT
    position; lsr's own tracker already leads by tracking.lead_s through set_abs), closed-loop trim and the supervisor
    (step loss, stall, sensor faults -> stop). With pointing and control both disabled make_rotator does not wrap at all."""

    def __init__(self, base, cfg: dict, clock=time.monotonic):
        self.base, self.cfg, self.clock = base, cfg, clock
        self.pt = Pointing(cfg) if cfg.get('pointing', {}).get('enabled') else None
        self.cc = {**control.DEFAULTS, **cfg.get('control', {})}
        self.sup = control.Supervisor(self.cc)
        lsr2 = cfg.get('model') == 'lsr2'
        self.acc = self.cc.get('acc') or (10.0 if lsr2 else 25.0)
        self._last_sent = self._ant = self._ff = None
        self._trimmed = True
        self._stopped = False
        self.limit_hit = False

    def __getattr__(self, name):                          # model, version, enable, conf, cal, jog, ...
        return getattr(self.__dict__['base'], name)

    # ---- commands
    def _clamp(self, az, el, absolute):
        l, m = self.cfg['limits'], self.cc['soft_margin']
        el2 = min(max(el, l['el_min'] + m), l['el_max'] - m)
        az2 = min(max(az, l['az_min'] + m), l['az_max'] - m) if absolute else az
        self.limit_hit = (el2 != el) or (az2 != az)
        return az2, el2

    def _lead(self, az, el):
        now, h = self.clock(), self._ff
        self._ff = [now, az, el, 0.0, 0.0]
        dt = now - h[0] if h else 0.0
        if not 0.05 <= dt <= 10.0:
            return az, el
        l, out = self.cfg['limits'], []
        for i, (x, px, pr, vmax) in enumerate(((az, h[1], h[3], l['vmax_az']), (el, h[2], h[4], l['vmax_el']))):
            r = (wrap180(x - px) if i == 0 else x - px) / dt
            r = 0.0 if abs(r) > self.cc.get('ff_max_dps', 5.0) else max(pr - self.acc * dt, min(pr + self.acc * dt, r))
            r = max(-vmax, min(vmax, r))
            self._ff[3 + i] = r
            out.append(x + r * self.cfg['tracking']['lead_s'])
        return out[0], out[1]

    def _send(self, fn, az, el, absolute):
        if self.sup.faults:
            log.warning('command ignored: rotator in fault state (%s)', ', '.join(self.sup.faults))
            return
        az, el = self._clamp(az, el, absolute)
        ant = (az, el)
        if self.pt:
            az, el = self.pt.command(az, el)
            ant = self.pt.last_ant
        ls = self._last_sent
        if self.cc['enabled'] and ls and abs(wrap180(az - ls[0])) < self.cc['deadband'] and abs(el - ls[1]) < self.cc['deadband']:
            return
        fn(az, el)
        self._last_sent, self._ant, self._trimmed = (az, el), ant, False

    def set_pos(self, az, el):
        if self.cc['enabled'] and self.cc['feedforward']:
            az, el = self._lead(az, el)
        self._send(self.base.set_pos, az, el, False)

    def set_abs(self, az, el):
        self._send(self.base.set_abs, az, el, True)

    def raw_move(self, az, el):
        """Command the raw mount (no correction, no deadband): used by the calibration scans."""
        self._last_sent = self._ant = None
        self.base.set_pos(az, el)

    def stop(self):
        self._last_sent = self._ff = None
        self.base.stop()

    def park(self):
        self._last_sent = self._ff = None
        self.base.park()

    def home(self):
        self._last_sent = self._ff = None
        self.base.home()

    def clear_faults(self):
        self.sup.clear(); self._stopped = False

    # ---- readings
    def get_pos(self):
        az, el = self.base.get_pos()
        return self.pt.report(az, el) if self.pt else (az, el)

    def _raw(self):
        if not self.cc['enabled'] or not hasattr(self.base, 'raw'):
            return None
        try:
            return self.base.raw() or None
        except (OSError, ValueError, KeyError):
            return None

    def _trim(self, st, raw):
        if not (self.cc['trim'] and not self._trimmed and self._ant and self._last_sent and raw) or self.sup.faults:
            return
        enc = raw.get('enc') or []
        if list(st.get('mode', [1, 1])) != [0, 0] or len(enc) != 2 or not all(math.isfinite(v) for v in enc):
            return
        err = (wrap180(self._ant[0] - enc[0]), self._ant[1] - enc[1])
        self._trimmed = True
        worst = max(abs(err[0]), abs(err[1]))
        if worst <= self.cc['deadband']:
            return
        if worst > self.cc['max_trim_deg']:
            self.sup.log(self.clock(), 'trim', f'error {worst:.2f} deg too large to trim')
            return
        new = (self._last_sent[0] + err[0], self._last_sent[1] + err[1])
        self.base.set_pos(*new)
        self._last_sent = new
        self.sup.log(self.clock(), 'trim', f'closed-loop correction {err[0]:+.2f}/{err[1]:+.2f} deg')

    def _act(self, actions):
        for a in actions:
            if a[0] == 'resync':
                self.base.cal('AZ' if a[1] == 0 else 'EL', a[2] + (getattr(self.base, 'az_off', 0.0) if a[1] == 0 else 0.0))
            elif a[0] == 'stop' and not self._stopped:
                self._stopped = True
                self.base.stop()
                if self.cc['on_fault'] == 'park' and not any(k.startswith('stall') for k in self.sup.faults):
                    self.base.park()

    def status(self) -> dict:
        st = self.base.status()
        if not st:
            return st
        if self.cc['enabled']:
            raw = self._raw()
            self._act(self.sup.update(self.clock(), st, raw))
            self._trim(st, raw)
        if self.pt:
            st['raw_az'], st['raw_el'] = st.get('az'), st.get('el')
            if isinstance(st.get('az'), (int, float)) and isinstance(st.get('el'), (int, float)):
                st['az'], st['el'] = self.pt.report(st['az'], st['el'])
            if isinstance(st.get('taz'), (int, float)) and isinstance(st.get('tel'), (int, float)):
                st['taz'], st['tel'] = self.pt.model.to_sky(st['taz'], st['tel'])
        st['control'] = self.control_status()
        return st

    def control_status(self) -> dict:
        p = self.cfg.get('pointing', {})
        return dict(self.sup.snapshot(), enabled=bool(self.cc['enabled']), limit_hit=self.limit_hit,
                    pointing=dict(enabled=bool(self.pt), rms=p.get('rms'), n=p.get('n', 0)))


def make_rotator(cfg: dict):
    model = cfg.get('model', 'lsr1')
    if cfg['rotator'].get('simulate'):
        l = cfg['limits']
        rot = SimRotator(l['vmax_az'], l['vmax_el'], 10.0 if model == 'lsr2' else 25.0,
                         l['az_min'], l['az_max'], l['el_min'], l['el_max'], model=model)
    else:
        r = cfg['rotator']
        rot = Rotator(r['port'], r['baud'], r.get('timeout', 0.5), model=model)
    if cfg.get('pointing', {}).get('enabled') or cfg.get('control', {}).get('enabled'):
        return CorrectedRotator(rot, cfg)
    return rot
