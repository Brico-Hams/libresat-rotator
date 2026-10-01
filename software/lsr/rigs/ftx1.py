"""Yaesu FTX-1 direct CAT driver (no Hamlib needed).

Wiring: one USB cable from the FTX-1 to the Pi. The radio enumerates as a dual CP210x;
use the *Enhanced* port (CAT-1), e.g. /dev/serial/by-id/usb-Silicon_Labs_..._if00-port0.
Set the radio's CAT rate to 38400 (menu: CAT-1 RATE).

Commands used (Yaesu "new CAT" family, as on the FT-991/FT-710/FTX-1):
  FA%09d;  main VFO frequency (RX = satellite downlink)
  FB%09d;  sub VFO frequency  (TX = satellite uplink)        <- verify on your firmware
  MD0x;    main mode, MD1x; sub mode  (1 LSB, 2 USB, 3 CW-U, 4 FM, 5 AM, C DATA-U)
  FA;      read main frequency back (knob follow on linear transponders)
Hardware split (ST/SPLIT) is NOT used: Hamlib issue #1972 showed the FTX-1 split state
desynchronising; we drive MAIN (RX) and SUB (TX) independently ("logical split").
Select SUB as the TX band on the radio (or press the TX band key) before the pass.
CTCSS via CAT (CN/CT, FT-991 syntax) is off by default: enable `cat_tone` only after checking it.
"""
from __future__ import annotations

import threading
import time

from . import Rig

MODES = {'LSB': '1', 'USB': '2', 'CW': '3', 'CW-U': '3', 'FM': '4', 'AM': '5', 'DATA-U': 'C', 'DATA': 'C'}
CTCSS = [67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8, 97.4, 100.0, 103.5, 107.2, 110.9,
         114.8, 118.8, 123.0, 127.3, 131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 159.8, 162.2, 165.5, 167.9,
         171.3, 173.8, 177.3, 179.9, 183.5, 186.2, 189.9, 192.8, 196.6, 199.5, 203.5, 206.5, 210.7, 218.1,
         225.7, 229.1, 233.6, 241.8, 250.3, 254.1]


def fa(hz: int) -> str:
    if not 30_000 <= hz <= 999_999_999:
        raise ValueError(f'frequency out of range: {hz}')
    return f'FA{int(hz):09d};'


def fb(hz: int) -> str:
    if not 30_000 <= hz <= 999_999_999:
        raise ValueError(f'frequency out of range: {hz}')
    return f'FB{int(hz):09d};'


def md(vfo: int, mode: str) -> str:
    return f'MD{vfo}{MODES[mode.upper()]};'


def tone_cmds(hz: float | None) -> list[str]:
    if not hz:
        return ['CT00;']
    idx = min(range(len(CTCSS)), key=lambda i: abs(CTCSS[i] - hz))
    return [f'CN00{idx:03d};', 'CT02;']


class FTX1(Rig):
    name = 'ftx1'
    can_read_rx = True

    def __init__(self, port='/dev/ttyUSB0', baud=38400, cat_tone=False, sub_tx=True, serial_factory=None):
        self.port, self.baud, self.cat_tone, self.sub_tx = port, baud, cat_tone, sub_tx
        self._factory = serial_factory
        self.ser = None
        self.lock = threading.Lock()
        self.last = {}

    def open(self):
        if self.ser:
            return
        if self._factory:
            self.ser = self._factory()
        else:
            import serial
            self.ser = serial.Serial(self.port, self.baud, timeout=0.3, write_timeout=0.5, rtscts=False)
            self.ser.dtr = False; self.ser.rts = False

    def close(self):
        if self.ser:
            self.ser.close(); self.ser = None

    def _send(self, cmd: str):
        self.open()
        with self.lock:
            self.ser.write(cmd.encode('ascii'))
            self.ser.flush()
            time.sleep(0.02)

    def _query(self, cmd: str) -> str | None:
        self.open()
        with self.lock:
            self.ser.reset_input_buffer()
            self.ser.write(cmd.encode('ascii'))
            buf = b''
            t0 = time.time()
            while time.time() - t0 < 0.5:
                c = self.ser.read(1)
                if not c:
                    continue
                buf += c
                if c == b';':
                    break
            s = buf.decode('ascii', 'replace')
            return s if s.endswith(';') else None

    def set_rx(self, hz: int):
        self._send(fa(hz))

    def set_tx(self, hz: int):
        self._send(fb(hz) if self.sub_tx else fa(hz))

    def get_rx(self):
        r = self._query('FA;')
        if r and r.startswith('FA') and r[2:-1].isdigit():
            return int(r[2:-1])
        return None

    def set_modes(self, rx_mode, tx_mode):
        if rx_mode and rx_mode.upper() in MODES:
            self._send(md(0, rx_mode))
        if tx_mode and tx_mode.upper() in MODES:
            self._send(md(1, tx_mode))

    def set_tone(self, hz):
        if self.cat_tone:
            for c in tone_cmds(hz):
                self._send(c)

    def info(self):
        return {'type': 'ftx1', 'port': self.port, 'baud': self.baud}
