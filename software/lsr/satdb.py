"""Transponder database (data/satellites.yaml + optional SatNOGS DB import)."""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PKG_DATA = Path(__file__).resolve().parent / 'data'
USER_DIR = Path('~/.local/share/lsr').expanduser()


@dataclass
class Transponder:
    label: str
    type: str                       # fm | linear | rx
    up: float | None = None         # MHz (fm)
    down: float | None = None
    up_low: float | None = None     # MHz (linear)
    up_high: float | None = None
    down_low: float | None = None
    down_high: float | None = None
    invert: bool = False
    ctcss: float | None = None
    up_mode: str = 'FM'
    down_mode: str = 'FM'

    # ---- frequency mapping in the satellite frame (Hz)
    @property
    def has_uplink(self) -> bool:
        return self.type != 'rx' and (self.up is not None or self.up_low is not None)

    def center_down(self) -> float:
        if self.type == 'linear':
            return (self.down_low + self.down_high) / 2 * 1e6
        return self.down * 1e6

    def clamp_down(self, f: float) -> float:
        if self.type != 'linear':
            return self.down * 1e6
        return min(max(f, self.down_low * 1e6), self.down_high * 1e6)

    def up_for_down(self, f_down: float) -> float | None:
        """Uplink (satellite frame) that lands on downlink f_down (satellite frame)."""
        if not self.has_uplink:
            return None
        if self.type == 'fm':
            return self.up * 1e6
        off = f_down - self.down_low * 1e6
        if self.invert:
            return self.up_high * 1e6 - off
        return self.up_low * 1e6 + off

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class SatEntry:
    name: str
    norad: int
    transponders: list[Transponder] = field(default_factory=list)


class SatDB:
    def __init__(self, extra: str | None = None):
        self.entries: dict[int, SatEntry] = {}
        for p in [PKG_DATA / 'satellites.yaml', USER_DIR / 'satellites_satnogs.yaml', USER_DIR / 'satellites.yaml'] + ([Path(extra)] if extra else []):
            if p.exists():
                self.load(p)

    def load(self, path: Path):
        for e in yaml.safe_load(path.read_text()) or []:
            tps = [Transponder(**t) for t in e.get('transponders', [])]
            if e['norad'] in self.entries and path.name == 'satellites_satnogs.yaml':
                continue                      # hand-curated entries win
            self.entries[int(e['norad'])] = SatEntry(e['name'], int(e['norad']), tps)

    def get(self, norad: int) -> SatEntry | None:
        return self.entries.get(int(norad))

    @staticmethod
    def update_from_satnogs(timeout: float = 30.0) -> int:
        """Fetch alive amateur transmitters from SatNOGS DB into ~/.local/share/lsr/satellites_satnogs.yaml."""
        url = 'https://db.satnogs.org/api/transmitters/?format=json&alive=true&status=active'
        req = urllib.request.Request(url, headers={'User-Agent': 'LibreSat-Rotator/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        out: dict[int, dict] = {}
        for t in data:
            nid = t.get('norad_cat_id')
            if not nid or t.get('service') not in (None, 'Amateur') or not t.get('downlink_low'):
                continue
            tp = {'label': t.get('description') or t.get('mode') or 'transmitter', 'down_mode': t.get('mode') or 'FM'}
            dl, dh, ul, uh = (t.get('downlink_low'), t.get('downlink_high'), t.get('uplink_low'), t.get('uplink_high'))
            if t.get('type') == 'Transponder' and dh and ul and uh:
                tp.update(type='linear', invert=bool(t.get('invert')), down_low=min(dl, dh) / 1e6, down_high=max(dl, dh) / 1e6,
                          up_low=min(ul, uh) / 1e6, up_high=max(ul, uh) / 1e6, up_mode='LSB' if t.get('invert') else 'USB', down_mode='USB')
            elif t.get('type') == 'Transceiver' and ul:
                tp.update(type='fm', down=dl / 1e6, up=ul / 1e6, up_mode=t.get('uplink_mode') or 'FM')
            else:
                tp.update(type='rx', down=dl / 1e6)
            e = out.setdefault(nid, {'name': t.get('sat_id', str(nid)), 'norad': nid, 'transponders': []})
            e['transponders'].append(tp)
        USER_DIR.mkdir(parents=True, exist_ok=True)
        (USER_DIR / 'satellites_satnogs.yaml').write_text(yaml.safe_dump(list(out.values()), sort_keys=False))
        return len(out)
