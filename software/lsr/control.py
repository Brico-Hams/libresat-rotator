"""Closed-loop supervision of the rotator on the OUTPUT encoders: step-loss and stall detection, fault latching, status.

Pure logic with an injected clock (no I/O): rotator.CorrectedRotator feeds it the controller status and the raw
encoder/step angles and executes the returned actions. Faults are latched until clear() (SARCNET-style safe state:
stop, keep the reason visible in the status). The firmware already re-syncs its step counter on large slips (XS slips=);
this layer is the independent second line and the place where the operator-visible faults are raised.
"""
from __future__ import annotations

import logging
import math
from collections import deque

from .pointing import wrap180

log = logging.getLogger('lsr.control')

E_ENC, E_LOWV = 8, 16
DEFAULTS = {'enabled': False, 'deadband': 0.1, 'step_loss_deg': 0.5, 'step_loss_s': 1.0, 'stall_s': 0.8,
            'stall_min_dps': 0.5, 'stall_min_frac': 0.25, 'feedforward': False, 'on_fault': 'stop',
            'require_encoders': False, 'require_gps': False, 'require_imu': False, 'trim': True, 'max_trim_deg': 1.0,
            'soft_margin': 0.0}


class Supervisor:
    def __init__(self, c: dict | None = None):
        self.c = {**DEFAULTS, **(c or {})}
        self.faults: dict[str, str] = {}
        self.events: deque = deque(maxlen=20)
        self._dis = [None, None]
        self._stall = [None, None]            # [t0, enc0, integral of |v|, t_last]
        self._slips = None
        self._t_loss = -1e9
        self.warnings: list[str] = []

    def log(self, now: float, kind: str, msg: str):
        self.events.append(dict(t=round(now, 2), kind=kind, msg=msg))
        log.warning('%s: %s', kind, msg)

    def fault(self, now: float, name: str, msg: str):
        if name not in self.faults:
            self.faults[name] = msg
            self.log(now, 'fault', f'{name}: {msg}')

    def clear(self):
        self.faults.clear(); self._dis = [None, None]; self._stall = [None, None]

    def update(self, now: float, st: dict, raw: dict | None) -> list[tuple]:
        """Returns actions: ('resync', axis, deg) or ('stop',)."""
        c, actions = self.c, []
        self.warnings = []
        enc = (raw or {}).get('enc') or []
        step = (raw or {}).get('step') or [st.get('az'), st.get('el')]
        enc_ok = len(enc) == 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in enc)
        flags = st.get('enc') or [1, 1]
        if c['require_encoders'] and (not enc_ok or 0 in flags or int(st.get('err', 0)) & E_ENC):
            self.fault(now, 'encoder', 'output encoder missing or invalid')
        elif int(st.get('err', 0)) & E_ENC:
            self.warnings.append('encoder: magnet or sensor problem')
        if c['require_imu'] and not (isinstance(st.get('imu_el'), (int, float)) and math.isfinite(st['imu_el'])):
            self.fault(now, 'imu', 'boom IMU not answering')
        g = st.get('gps')
        if c['require_gps'] and not (isinstance(g, list) and g and g[0]):
            self.fault(now, 'gps', 'no GPS fix')
        if int(st.get('err', 0)) & E_LOWV:
            self.warnings.append('supply voltage low')
        slips = st.get('slips')
        if isinstance(slips, list):
            if self._slips is not None and slips != self._slips:
                self.log(now, 'step_loss', f'firmware re-synced on the encoder (slips {slips})')
                self._t_loss = now
            self._slips = list(slips)
        if enc_ok:
            for a in (0, 1):
                d = step[a] - enc[a]
                d = wrap180(d) if a == 0 else d
                if abs(d) > c['step_loss_deg']:
                    if self._dis[a] is None:
                        self._dis[a] = now
                    elif now - self._dis[a] > c['step_loss_s']:
                        self.log(now, 'step_loss', f'{"AZ" if a == 0 else "EL"} step count {step[a]:.2f} vs encoder {enc[a]:.2f}: re-sync')
                        self._t_loss = now
                        actions.append(('resync', a, enc[a]))
                        self._dis[a] = None
                else:
                    self._dis[a] = None
                v = abs(float(st.get('vaz' if a == 0 else 'vel', 0.0) or 0.0))
                s = self._stall[a]
                if v < c['stall_min_dps']:
                    self._stall[a] = None
                elif s is None:
                    self._stall[a] = [now, enc[a], 0.0, now]
                else:
                    s[2] += v * (now - s[3]); s[3] = now
                    if now - s[0] >= c['stall_s']:
                        if abs(enc[a] - s[1]) < c['stall_min_frac'] * s[2]:
                            self.fault(now, f'stall_{"az" if a == 0 else "el"}',
                                       f'{"AZ" if a == 0 else "EL"} commanded but the encoder did not move')
                        self._stall[a] = None
        if self.faults:
            actions.append(('stop',))
        if now - self._t_loss < 60.0:
            self.warnings.append('step loss in the last minute')
        return actions

    def snapshot(self) -> dict:
        state = 'fault' if self.faults else ('warn' if self.warnings else 'ok')
        return dict(state=state, faults=dict(self.faults), warnings=list(self.warnings), events=list(self.events)[-5:],
                    deadband=self.c['deadband'])
