"""Shared fixtures: synthetic but valid TLEs (no network needed), fake serial ports."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EPOCH = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)


def _cks(line):
    return line + str(sum(int(c) if c.isdigit() else (1 if c == '-' else 0) for c in line) % 10)


def make_tle(name, norad, incl, raan, ecc, argp, ma, mm, epoch=EPOCH, bstar='21000-3'):
    doy = (epoch - datetime(epoch.year, 1, 1, tzinfo=timezone.utc)).total_seconds() / 86400 + 1
    l1 = _cks(f'1 {norad:05d}U 98067A   {epoch.year % 100:02d}{doy:012.8f}  .00010000  00000-0  {bstar} 0  999')
    l2 = _cks(f'2 {norad:05d} {incl:8.4f} {raan:8.4f} {int(round(ecc * 1e7)):07d} {argp:8.4f} {ma:8.4f} {mm:11.8f}{12345:5d}')
    assert len(l1) == 69 and len(l2) == 69, (l1, l2)
    return f'{name}\n{l1}\n{l2}\n'


TLES = (make_tle('ISS (ZARYA)', 25544, 51.64, 120.0, 0.0005, 90.0, 270.0, 15.50)
        + make_tle('SO-50', 27607, 64.55, 105.0, 0.0042, 123.0, 237.0, 14.80)
        + make_tle('RS-44', 44909, 82.52, 30.0, 0.0215, 50.0, 310.0, 12.80)
        + make_tle('AO-91', 43017, 97.60, 40.0, 0.0230, 300.0, 58.0, 14.80))


@pytest.fixture
def tle_text():
    return TLES


@pytest.fixture
def cfg(tmp_path):
    from lsr import config
    c = config.load(str(tmp_path / 'none.yaml'))
    c['tle']['cache_dir'] = str(tmp_path / 'tle')
    c['tle']['groups'] = ['test']
    (tmp_path / 'tle').mkdir()
    (tmp_path / 'tle' / 'test.tle').write_text(TLES)
    c['station'].update(lat=40.4168, lon=-3.7038, alt=650.0, use_gps=False)
    c['rotator']['simulate'] = True
    c['_path'] = str(tmp_path / 'config.yaml')
    return c


class FakeSerial:
    """Scriptable serial port: `responder(bytes_written) -> bytes_to_return`."""

    def __init__(self, responder=None):
        self.written = b''
        self.inbuf = b''
        self.responder = responder or (lambda b: b'')

    def write(self, b):
        self.written += b
        self.inbuf += self.responder(b) or b''
        return len(b)

    def read(self, n=1):
        out, self.inbuf = self.inbuf[:n], self.inbuf[n:]
        return out

    def readline(self):
        i = self.inbuf.find(b'\n')
        if i < 0:
            out, self.inbuf = self.inbuf, b''
        else:
            out, self.inbuf = self.inbuf[:i + 1], self.inbuf[i + 1:]
        return out

    def flush(self): ...
    def reset_input_buffer(self): self.inbuf = b''
    def close(self): ...


@pytest.fixture
def fake_serial():
    return FakeSerial
