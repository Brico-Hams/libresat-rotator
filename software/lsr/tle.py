"""TLE download (CelesTrak GP API) with an offline cache — the rotator works in the field without internet."""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from .astro import load_tle_text, Satellite


class TleStore:
    def __init__(self, cfg: dict):
        self.cfg = cfg['tle']
        self.dir = Path(self.cfg['cache_dir']).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.sats: dict[str, Satellite] = {}
        self.load_cache()

    def _file(self, group: str) -> Path:
        return self.dir / f'{group}.tle'

    def age_days(self) -> float:
        files = [self._file(g) for g in self.cfg['groups'] if self._file(g).exists()]
        if not files:
            return float('inf')
        return (time.time() - min(f.stat().st_mtime for f in files)) / 86400.0

    def load_cache(self):
        sats = {}
        for g in self.cfg['groups']:
            f = self._file(g)
            if f.exists():
                sats.update(load_tle_text(f.read_text()))
        for extra in self.cfg.get('extra_files', []):
            p = Path(extra).expanduser()
            if p.exists():
                sats.update(load_tle_text(p.read_text()))
        self.sats = sats
        return len(self.names())

    def update(self, timeout: float = 20.0) -> dict:
        """Download every group; failures keep the cached copy. Returns {group: count|error}."""
        res = {}
        for g in self.cfg['groups']:
            url = self.cfg['url'].format(group=g)
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'LibreSat-Rotator/1.0'})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    text = r.read().decode('ascii', 'replace')
                n = len({s.norad for s in load_tle_text(text).values()})
                if n == 0:
                    raise ValueError('no TLEs in response')
                tmp = self._file(g).with_suffix('.tmp')
                tmp.write_text(text)
                tmp.replace(self._file(g))
                res[g] = n
            except Exception as e:      # keep the old file
                res[g] = f'error: {e}'
        self.load_cache()
        return res

    def add_text(self, text: str, name: str = 'manual') -> int:
        sats = load_tle_text(text)
        if sats:
            (self.dir / f'{name}.tle').write_text(text)
            if name not in self.cfg['groups']:
                self.cfg['groups'].append(name)
            self.sats.update(sats)
        return len({s.norad for s in sats.values()})

    def names(self) -> list[str]:
        return sorted({s.name for s in self.sats.values()})

    def get(self, key) -> Satellite | None:
        return self.sats.get(str(key).upper().strip())
