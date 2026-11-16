"""Configuration: YAML file merged over the defaults below.

Search order: $LSR_CONFIG, /etc/lsr/config.yaml, ~/.config/lsr/config.yaml.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

DEFAULTS = {
    'model': 'lsr1',
    'station': {'name': 'LSR-1', 'lat': 40.4168, 'lon': -3.7038, 'alt': 650.0, 'use_gps': True},
    'rotator': {'port': '/dev/serial0', 'baud': 115200, 'simulate': False, 'timeout': 0.5},
    'limits': {'az_min': 0.0, 'az_max': 450.0, 'el_min': 0.0, 'el_max': 180.0,
               'vmax_az': 20.0, 'vmax_el': 15.0, 'allow_flip': True},
    'tracking': {'lead_s': 0.6, 'update_hz': 2.0, 'min_el': 0.0, 'preposition_s': 120,
                 'park_after_pass': True, 'park': [0.0, 90.0], 'auto_next': False, 'min_pass_el': 10.0},
    'tle': {'groups': ['amateur', 'cubesat', 'stations', 'weather'], 'max_age_days': 3.0,
            'url': 'https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle',
            'cache_dir': '~/.local/share/lsr/tle', 'extra_files': []},
    'rig': {'type': 'none',
            'ftx1': {'port': '/dev/ttyUSB0', 'baud': 38400, 'cat_tone': False, 'sub_tx': True},
            'hamlib': {'host': '127.0.0.1', 'port': 4532, 'vfo_mode': True, 'rx_vfo': 'Main', 'tx_vfo': 'Sub'},
            'opengd77': {'port': '/dev/ttyACM0', 'sync_clock': True, 'read_gps': False}},
    'doppler': {'fm_step_hz': 100, 'ssb_step_hz': 10, 'knob_follow': True, 'knob_threshold_hz': 30},
    'web': {'host': '0.0.0.0', 'port': 8080},
    'rotctld': {'host': '0.0.0.0', 'port': 4533, 'enabled': True},
    'satdb': {'file': ''},
}

# Rotator model profiles: merged over DEFAULTS, then the user's YAML on top. lsr1 = the defaults above.
# lsr2 azimuth is -360..+360; the firmware works on 0..720 (user + AZ_WIRE_OFFSET), see rotator.Rotator.
MODEL_NAMES = {'lsr1': 'LSR-1', 'lsr2': 'LSR-2'}
AZ_WIRE_OFFSET = {'lsr1': 0.0, 'lsr2': 360.0}
PROFILES = {
    'lsr1': {},
    'lsr2': {'station': {'name': 'LSR-2'},
             'limits': {'az_min': -360.0, 'az_max': 360.0, 'el_min': -30.0, 'el_max': 150.0,
                        'vmax_az': 12.0, 'vmax_el': 12.0, 'allow_flip': False, 'anti_windup': False},
             'rotator': {'baud': 9600}},   # EasyComm II 9600 8N1 as SARCTrac Mk5 trackers expect
}


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def with_model(user: dict) -> dict:
    model = str((user or {}).get('model', 'lsr1')).lower()
    if model not in PROFILES:
        raise ValueError(f"unknown rotator model {model!r} (use one of {', '.join(PROFILES)})")
    cfg = _merge(_merge(DEFAULTS, PROFILES[model]), user or {})
    cfg['model'] = model
    return cfg


def config_paths():
    env = os.environ.get('LSR_CONFIG')
    return [Path(env)] if env else [Path('/etc/lsr/config.yaml'), Path('~/.config/lsr/config.yaml').expanduser()]


def load(path: str | None = None) -> dict:
    paths = [Path(path)] if path else config_paths()
    for p in paths:
        if p.exists():
            with open(p) as f:
                cfg = with_model(yaml.safe_load(f) or {})
            cfg['_path'] = str(p)
            return cfg
    cfg = copy.deepcopy(DEFAULTS)
    cfg['_path'] = str(paths[-1])
    return cfg


def save(cfg: dict, path: str | None = None):
    p = Path(path or cfg.get('_path') or config_paths()[-1])
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in cfg.items() if not k.startswith('_')}
    with open(p, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False)
    return str(p)
