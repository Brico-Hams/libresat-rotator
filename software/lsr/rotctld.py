"""Hamlib rotctld-compatible TCP server (default port 4533).

Lets Gpredict, Look4Sat, SatNOGS client, SatPC32 (via rotctld) or `rotctl -m 2` drive the
rotator through the Pi. Implements p/P/S/K/_ and their long forms, dump_state (protocol 1),
and the '+' extended response prefix.
"""
from __future__ import annotations

import asyncio
import logging

from .config import MODEL_NAMES

log = logging.getLogger('lsr.rotctld')


class RotctldServer:
    def __init__(self, rot, tracker=None, min_az=0.0, max_az=360.0, min_el=0.0, max_el=180.0):
        self.rot, self.tracker = rot, tracker
        self.lim = (min_az, max_az, min_el, max_el)
        self.clients = 0

    @property
    def model_name(self) -> str:
        return MODEL_NAMES.get(getattr(self.rot, 'model', 'lsr1'), 'LSR-1')
    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.clients += 1
        peer = writer.get_extra_info('peername')
        log.info('rotctld client %s', peer)
        try:
            while not reader.at_eof():
                raw = await reader.readline()
                if not raw:
                    break
                for line in raw.decode(errors='replace').replace(';', '\n').splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    out = await asyncio.to_thread(self.execute, line)
                    if out is None:          # quit
                        writer.close(); return
                    writer.write(out.encode())
                    await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self.clients -= 1
            try:
                writer.close()
            except Exception:
                pass

    def execute(self, line: str) -> str | None:
        ext = line.startswith('+')
        if ext:
            line = line[1:].strip()
        parts = line.split()
        if not parts:
            return ''
        cmd, args = parts[0], parts[1:]
        try:
            if cmd in ('p', '\\get_pos'):
                az, el = self.rot.get_pos()
                if ext:
                    return f'get_pos:\nAzimuth: {az:.6f}\nElevation: {el:.6f}\nRPRT 0\n'
                return f'{az:.6f}\n{el:.6f}\n'
            if cmd in ('P', '\\set_pos'):
                az, el = float(args[0].replace(',', '.')), float(args[1].replace(',', '.'))
                if self.tracker:
                    self.tracker.external()
                self.rot.set_pos(az % 360.0 if az >= 0 else az + 360.0, el)
                return f'set_pos: {az} {el}\nRPRT 0\n' if ext else 'RPRT 0\n'
            if cmd in ('S', '\\stop'):
                self.rot.stop()
                return 'RPRT 0\n'
            if cmd in ('K', '\\park'):
                self.rot.park()
                return 'RPRT 0\n'
            if cmd in ('R', '\\reset'):
                self.rot.home()
                return 'RPRT 0\n'
            if cmd in ('M', '\\move'):
                d = int(args[0])
                self.rot.jog({2: 'up', 4: 'down', 8: 'left', 16: 'right'}.get(d, 'left'))
                return 'RPRT 0\n'
            if cmd in ('_', '\\get_info'):
                return f'LibreSat Rotator {self.model_name} {self.rot.version()}\n'
            if cmd == '\\dump_state':
                a0, a1, e0, e1 = self.lim
                return (f'1\n2\nmin_az={a0:.6f}\nmax_az={a1:.6f}\nmin_el={e0:.6f}\nmax_el={e1:.6f}\n'
                        'south_zero=0\nrot_type=AzEl\ndone\n')
            if cmd in ('q', 'Q', '\\quit'):
                return None
            if cmd in ('\\chk_vfo', '\\dump_caps'):
                return '0\n' if cmd == '\\chk_vfo' else f'Model name: {self.model_name}\nRPRT 0\n'
            return 'RPRT -11\n'                       # not implemented
        except (IndexError, ValueError):
            return 'RPRT -1\n'                        # invalid parameter
        except Exception as e:                       # controller I/O
            log.warning('rotctld %s: %s', line, e)
            return 'RPRT -6\n'

    async def serve(self, host='0.0.0.0', port=4533):
        srv = await asyncio.start_server(self.handle, host, port)
        log.info('rotctld listening on %s:%d', host, port)
        async with srv:
            await srv.serve_forever()
