"""Radio (CAT) back-ends for Doppler control."""
from __future__ import annotations


class Rig:
    """Minimal interface used by the Doppler engine. Frequencies in Hz."""
    name = 'none'
    can_read_rx = False

    def open(self): ...
    def close(self): ...
    def set_rx(self, hz: int): ...
    def set_tx(self, hz: int): ...
    def get_rx(self) -> int | None: return None
    def set_modes(self, rx_mode: str | None, tx_mode: str | None): ...
    def set_tone(self, hz: float | None): ...
    def info(self) -> dict: return {'type': self.name}


class DummyRig(Rig):
    """Records what would be sent (simulation and tests). get_rx() returns the knob position."""
    name = 'dummy'
    can_read_rx = True

    def __init__(self):
        self.rx = self.tx = None
        self.knob = None
        self.modes = (None, None)
        self.tone = None
        self.log: list[tuple] = []

    def set_rx(self, hz):
        self.rx = hz; self.knob = hz; self.log.append(('rx', hz))

    def set_tx(self, hz):
        self.tx = hz; self.log.append(('tx', hz))

    def get_rx(self):
        return self.knob

    def set_modes(self, rx_mode, tx_mode):
        self.modes = (rx_mode, tx_mode); self.log.append(('modes', rx_mode, tx_mode))

    def set_tone(self, hz):
        self.tone = hz; self.log.append(('tone', hz))

    def info(self):
        return {'type': 'dummy', 'rx': self.rx, 'tx': self.tx, 'modes': self.modes, 'tone': self.tone}


def make_rig(cfg: dict) -> Rig | None:
    t = (cfg['rig'].get('type') or 'none').lower()
    if t == 'ftx1':
        from .ftx1 import FTX1
        return FTX1(**cfg['rig']['ftx1'])
    if t == 'hamlib':
        from .hamlib_net import HamlibRig
        return HamlibRig(**cfg['rig']['hamlib'])
    if t == 'dummy':
        return DummyRig()
    return None                      # 'none' and 'opengd77' (the GD77 does its own Doppler)
