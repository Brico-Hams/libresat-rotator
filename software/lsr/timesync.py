"""Field time keeping: the Pi Zero has no RTC. If NTP is not synchronised and the GPS on the
controller (or an OpenGD77 radio with GPS) has a fix, set the system clock from it.
Needs CAP_SYS_TIME (the systemd unit grants it). Accuracy ~0.1-0.5 s: plenty for tracking
(LEO moves ~0.07 deg/s at most) and for the Doppler (< 2 Hz at 435 MHz)."""
from __future__ import annotations

import logging
import subprocess
import time
from datetime import datetime, timezone

log = logging.getLogger('lsr.time')


def ntp_synchronized() -> bool:
    try:
        r = subprocess.run(['timedatectl', 'show', '-p', 'NTPSynchronized', '--value'], capture_output=True, text=True, timeout=3)
        return r.stdout.strip() == 'yes'
    except Exception:
        return False


def parse_utc(s: str) -> datetime | None:
    try:
        if not s or s.startswith('0000') or s.startswith('2000-00'):
            return None
        return datetime.strptime(s.rstrip('Z')[:22], '%Y-%m-%dT%H:%M:%S.%f').replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(s.rstrip('Z')[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def maybe_set_clock(status: dict, threshold_s: float = 2.0) -> str | None:
    """Return a message if the clock was (or should be) set from the controller GPS."""
    g = status.get('gps')
    if not isinstance(g, list) or not g or not g[0]:
        return None
    t = parse_utc(str(status.get('utc', '')))
    if not t or t.year < 2024:
        return None
    off = (t - datetime.now(timezone.utc)).total_seconds()
    if abs(off) < threshold_s or ntp_synchronized():
        return None
    try:
        time.clock_settime(time.CLOCK_REALTIME, t.timestamp())
        log.warning('system clock set from GPS (offset was %.1f s)', off)
        return f'clock set from GPS (offset {off:.1f} s)'
    except PermissionError:
        return f'clock is {off:.1f} s off and cannot be set (needs CAP_SYS_TIME)'
