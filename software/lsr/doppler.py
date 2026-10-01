"""Doppler control for full-duplex satellite work.

FM      : RX = down * (1 - rr/c), TX = up / (1 - rr/c). Updated in fm_step_hz steps.
Linear  : the operator tunes the RX (downlink) knob. We read the rig back; if the RX moved
          more than knob_threshold_hz from what we last set, the operator tuned: the new
          satellite-frame downlink is RX / (1 - rr/c). Then RX and TX are recomputed so that
          the QSO stays on the same transponder frequency during the whole pass
          ("one true frequency" rule) and the uplink follows (inverting or not).
"""
from __future__ import annotations

from dataclasses import dataclass

from .astro import C_KMS
from .satdb import Transponder


@dataclass
class DopplerState:
    down_sat: float | None = None     # Hz, satellite frame
    last_rx: float | None = None      # Hz, last value written to the rig
    last_tx: float | None = None
    rx: float | None = None           # current computed values (Hz)
    tx: float | None = None
    rr: float = 0.0


class DopplerEngine:
    def __init__(self, tp: Transponder, rig, cfg: dict):
        self.tp, self.rig, self.cfg = tp, rig, cfg
        self.st = DopplerState()
        lin = tp.type == 'linear'
        self.step = cfg['ssb_step_hz'] if lin else cfg['fm_step_hz']
        self.started = False

    @staticmethod
    def rx_from_sat(f_sat: float, rr: float) -> float:
        return f_sat * (1.0 - rr / C_KMS)

    @staticmethod
    def tx_from_sat(f_sat: float, rr: float) -> float:
        return f_sat / (1.0 - rr / C_KMS)

    def start(self):
        tp = self.tp
        self.st.down_sat = tp.center_down()
        if self.rig:
            self.rig.set_modes(tp.down_mode, tp.up_mode if tp.has_uplink else None)
            if tp.ctcss and tp.has_uplink:
                self.rig.set_tone(tp.ctcss)
        self.started = True

    def tick(self, range_rate_kms: float) -> DopplerState:
        """Call 1-4 times per second with the current range rate."""
        if not self.started:
            self.start()
        st, tp, rr = self.st, self.tp, range_rate_kms
        st.rr = rr
        # knob follow (linear only)
        if tp.type == 'linear' and self.cfg.get('knob_follow', True) and self.rig and self.rig.can_read_rx and st.last_rx:
            cur = self.rig.get_rx()
            if cur and abs(cur - st.last_rx) > self.cfg.get('knob_threshold_hz', 30):
                st.down_sat = tp.clamp_down(cur / (1.0 - rr / C_KMS))
        st.rx = self.rx_from_sat(st.down_sat, rr)
        up_sat = tp.up_for_down(st.down_sat)
        st.tx = self.tx_from_sat(up_sat, rr) if up_sat else None
        if self.rig:
            if st.last_rx is None or abs(st.rx - st.last_rx) >= self.step:
                q = round(st.rx / 10.0) * 10 if tp.type == 'linear' else round(st.rx / self.step) * self.step
                self.rig.set_rx(int(q)); st.last_rx = q
            if st.tx and (st.last_tx is None or abs(st.tx - st.last_tx) >= self.step):
                q = round(st.tx / 10.0) * 10 if tp.type == 'linear' else round(st.tx / self.step) * self.step
                self.rig.set_tx(int(q)); st.last_tx = q
        return st
