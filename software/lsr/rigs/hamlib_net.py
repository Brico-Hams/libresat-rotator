"""Any Hamlib-supported radio through rigctld (TCP).

Example for the FTX-1 (Hamlib >= 4.7 / master, model 1051) with VFO mode:
    rigctld -m 1051 -r /dev/serial/by-id/...-if00-port0 -s 38400 --vfo -t 4532
VFO mode lets us address Main (RX) and Sub (TX) explicitly without toggling split.
Without --vfo set vfo_mode: false and the driver uses F (RX) and I (split TX).
"""
from __future__ import annotations

import socket
import threading

from . import Rig


class HamlibRig(Rig):
    name = 'hamlib'
    can_read_rx = True

    def __init__(self, host='127.0.0.1', port=4532, vfo_mode=True, rx_vfo='Main', tx_vfo='Sub'):
        self.addr = (host, int(port))
        self.vfo_mode, self.rx_vfo, self.tx_vfo = vfo_mode, rx_vfo, tx_vfo
        self.sock = None
        self.f = None
        self.lock = threading.RLock()

    def open(self):
        if self.sock is None:
            self.sock = socket.create_connection(self.addr, timeout=2.0)
            self.f = self.sock.makefile('rwb', buffering=0)
            if not self.vfo_mode:
                self.cmd('S 1 ' + self.tx_vfo)

    def close(self):
        if self.sock:
            self.sock.close(); self.sock = None

    def cmd(self, line: str, nlines: int = 1) -> list[str]:
        """Set commands (upper case) answer 'RPRT n'; get commands answer `nlines` value lines."""
        with self.lock:
            for attempt in (0, 1):
                try:
                    self.open()
                    self.f.write((line + '\n').encode())
                    out = []
                    while True:
                        r = self.f.readline().decode(errors='replace').strip()
                        if r == '' and not out:
                            raise ConnectionError('rigctld closed the connection')
                        out.append(r)
                        if r.startswith('RPRT') or (not line[0].isupper() and len(out) >= nlines) or r == '':
                            return out
                except OSError:
                    self.close()          # reconnect on the next open(); retry once
                    if attempt:
                        raise

    def _v(self, vfo):
        return f' {vfo}' if self.vfo_mode else ''

    def set_rx(self, hz):
        self.cmd(f'F{self._v(self.rx_vfo)} {int(hz)}')

    def set_tx(self, hz):
        if self.vfo_mode:
            self.cmd(f'F {self.tx_vfo} {int(hz)}')
        else:
            self.cmd(f'I {int(hz)}')

    def get_rx(self):
        r = self.cmd(f'f{self._v(self.rx_vfo)}')
        try:
            return int(float(r[0]))
        except (IndexError, ValueError):
            return None

    def set_modes(self, rx_mode, tx_mode):
        if rx_mode:
            self.cmd(f'M{self._v(self.rx_vfo)} {rx_mode.upper()} 0')
        if tx_mode:
            if self.vfo_mode:
                self.cmd(f'M {self.tx_vfo} {tx_mode.upper()} 0')
            else:
                self.cmd(f'X {tx_mode.upper()} 0')

    def set_tone(self, hz):
        tenths = int(round((hz or 0) * 10))
        v = self.tx_vfo if self.vfo_mode else ''
        self.cmd(f'C {v} {tenths}'.replace('  ', ' '))

    def info(self):
        return {'type': 'hamlib', 'rigctld': f'{self.addr[0]}:{self.addr[1]}', 'vfo_mode': self.vfo_mode}
