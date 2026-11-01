"""OpenGD77 integration (GD-77, DM-1801, RD-5R, MD-UV380/390, DM-1701, MD-9600, DM-32 ... running OpenGD77).

OpenGD77 has no CAT frequency control, but it has a built-in satellite mode that computes
Doppler itself from Keplerian elements (keps) stored in the radio, and it needs a correct
UTC clock. This module talks the OpenGD77 CPS USB-serial protocol (as used by the official
CPS and OpenGD77 WebCPS, js/webusb.js) to:

  * sync_clock()   - command 'C' 6/7 with Unix time: sets the radio clock to UTC (from GPS/NTP)
  * radio_info()   - 'R' mode 9: model, firmware build
  * upload_keps()  - EXPERIMENTAL: writes up to 25 satellites (TLE + FM channel) into the
                     custom-data area (block type 3), exactly like the CPS "Satellite" tab.
                     A backup of the custom-data area is saved first.
  * read_nmea()    - radios with GPS stream NMEA on the same USB port outside CPS mode:
                     the Pi can take its position/time from the radio.

The rotator then tracks the same satellite the operator selects on the radio. Frequencies:
the radio applies its own Doppler, so nothing is sent during the pass.
"""
from __future__ import annotations

import struct
import time
from datetime import datetime, timezone
from pathlib import Path

LUT = '0123456789. +-*'
RADIO_TYPES = {0: 'GD-77', 1: 'GD-77S', 2: 'DM-1801', 3: 'RD-5R', 4: 'DM-1801A', 5: 'MD-9600', 6: 'MD-UV380',
               7: 'MD-380', 8: 'DM-1701', 9: 'MD-2017', 10: 'DM-1701 RGB', 11: 'DM-32', 12: 'UV008'}
CUSTOM_DATA_SIZE = 0x11A0
CUSTOM_HEADER = 12
SAT_TYPE = 3
SAT_BLOCK = 2520
RECORD = 100
MAX_SATS = 25
STM32_FLASH_OFFSET = 0x20000
SECTOR = 4096


# ------------------------------------------------------------------ keps packing (pure, unit tested)
def compress_tle_text(text: str) -> bytes:
    out = bytearray((len(text) + 1) // 2)
    for i in range(0, len(text), 2):
        hi = max(0, LUT.find(text[i])) if i < len(text) else 0
        lo = max(0, LUT.find(text[i + 1] if i + 1 < len(text) else ' '))
        out[i >> 1] = ((hi << 4) | lo) & 0xFF
    return bytes(out)


def decompress_tle_text(data: bytes) -> str:
    return ''.join(LUT[(b >> 4) & 0x0F] + LUT[b & 0x0F] for b in data)


def build_satellite_records(sats: list[dict]) -> bytes:
    """sats: dicts with name, line1, line2, rx1, tx1 (MHz), tx_ctcss, arm_ctcss (Hz), rx2, tx2, rx3, tx3, extra.
    Byte-for-byte the layout of buildSatelliteRecords() in OpenGD77 WebCPS."""
    buf = bytearray(SAT_BLOCK)
    for i, s in enumerate(sorted(sats, key=lambda s: str(s.get('name', '')))[:MAX_SATS]):
        r = i * RECORD
        name = str(s.get('name', ''))[:8].encode('ascii', 'replace')
        buf[r:r + len(name)] = name
        l1 = str(s.get('line1', '')).ljust(70)
        t1 = l1[18:20] + l1[20:32] + l1[33:43]
        buf[r + 8:r + 20] = compress_tle_text(t1)[:12]
        l2 = str(s.get('line2', '')).ljust(70)
        t2 = l2[8:16] + l2[17:25] + l2[26:33] + l2[34:42] + l2[43:51] + l2[52:63] + l2[63:68] + ' '
        buf[r + 20:r + 48] = compress_tle_text(t2)[:28]
        u32 = lambda o, mhz: struct.pack_into('<I', buf, r + o, int(round((mhz or 0) * 1e6)) & 0xFFFFFFFF)
        u16 = lambda o, hz: struct.pack_into('<H', buf, r + o, int(round((hz or 0) * 10)) & 0xFFFF)
        u32(48, s.get('rx1')); u32(52, s.get('tx1')); u16(56, s.get('tx_ctcss')); u16(58, s.get('arm_ctcss'))
        u32(60, s.get('rx2')); u32(64, s.get('tx2')); u32(68, s.get('rx3')); u32(72, s.get('tx3'))
        extra = str(s.get('extra', ''))[:24].encode('ascii', 'replace')
        buf[r + 76:r + 76 + len(extra)] = extra
    return bytes(buf)


def patch_custom_data(region: bytes, records: bytes) -> bytes:
    """Insert/replace the satellite block (type 3) keeping other blocks (boot image, melody, theme)."""
    w = bytearray(region)
    if bytes(w[0:8]) != b'OpenGD77':
        w[0:8] = b'OpenGD77'; w[8:12] = b'\0\0\0\0'
    off, target, uninit = CUSTOM_HEADER, -1, -1
    while off < len(w) - 8:
        btype = w[off]
        bsize = struct.unpack_from('<I', w, off + 4)[0]
        if btype == SAT_TYPE:
            target = off; break
        if btype == 0xFF and uninit == -1 and off + 8 + SAT_BLOCK <= len(w):
            uninit = off
        if btype in (0xFF, 0) or bsize == 0 or bsize > 0x10000:
            break
        off += 8 + bsize
    if target < 0:
        if uninit < 0:
            raise RuntimeError('no space for satellite data in the custom data area')
        target = uninit
    struct.pack_into('<II', w, target, SAT_TYPE, SAT_BLOCK)
    w[target + 8:target + 8 + SAT_BLOCK] = records
    return bytes(w)


def sats_from_tracker(tle_store, satdb, names: list[str]) -> list[dict]:
    """Build radio records from TLEs + the FM transponder of each satellite (if any)."""
    out = []
    for n in names:
        s = tle_store.get(n)
        if not s:
            continue
        e = satdb.get(s.norad)
        tp = next((t for t in (e.transponders if e else []) if t.type == 'fm'), None)
        out.append(dict(name=(e.name if e else s.name)[:8], line1=s.line1, line2=s.line2,
                        rx1=tp.down if tp else 0, tx1=tp.up if tp else 0, tx_ctcss=(tp.ctcss or 0) if tp else 0))
    return out


# ------------------------------------------------------------------ USB serial protocol
class OpenGD77:
    def __init__(self, port='/dev/ttyACM0', serial_factory=None, **_):
        self.port = port
        self._factory = serial_factory
        self.ser = None
        self.platform = None          # 'MK22' | 'STM32' | 'DM32'
        self.bufsize = 32
        self.info = None

    def open(self):
        if self.ser is None:
            if self._factory:
                self.ser = self._factory()
            else:
                import serial
                self.ser = serial.Serial(self.port, 115200, timeout=1.0)
        return self

    def close(self):
        if self.ser:
            self.ser.close(); self.ser = None

    def _read(self, n, timeout=2.0):
        buf = b''
        t0 = time.time()
        while len(buf) < n and time.time() - t0 < timeout:
            buf += self.ser.read(n - len(buf))
        return buf

    def command(self, num: int, option: int | None = None, payload: bytes = b'') -> bool:
        pkt = bytes([0x43, num]) + (bytes([option]) if option is not None else b'') + payload
        self.ser.reset_input_buffer()
        self.ser.write(pkt)
        r = self._read(1)
        return r == b'-'

    def enter_cps(self):
        for _ in range(3):
            if self.command(0):
                return True
            time.sleep(0.5)
        raise IOError('OpenGD77 did not acknowledge CPS mode (command 0)')

    def exit_cps(self):
        self.command(5); self.command(7)

    def sync_clock(self, when: datetime | None = None) -> bool:
        ts = int((when or datetime.now(timezone.utc)).timestamp()) & 0xFFFFFFFF
        self.open(); self.enter_cps()
        try:
            return self.command(6, 7, struct.pack('<I', ts))
        finally:
            self.exit_cps()

    def read(self, mode: int, addr: int, length: int) -> bytes:
        out = b''
        while len(out) < length:
            n = min(self.bufsize, length - len(out))
            a = addr + len(out)
            self.ser.reset_input_buffer()
            self.ser.write(bytes([0x52, mode]) + struct.pack('>IH', a, n))
            r = self._read(n + 3)
            if len(r) < 3 or r[0] != 0x52:
                raise IOError(f'read error at 0x{a:x}')
            got = min((r[1] << 8) | r[2], n, len(r) - 3)
            if got <= 0:
                raise IOError(f'empty read at 0x{a:x}')
            out += r[3:3 + got]
        return out

    def radio_info(self) -> dict:
        self.open(); self.enter_cps()
        try:
            b = self.read(9, 0, 46)
        finally:
            self.exit_cps()
        ver, rtype = struct.unpack_from('<II', b, 0)
        build = b[24:40].split(b'\0')[0].decode('ascii', 'replace')
        self.platform = 'DM32' if rtype >= 11 else ('STM32' if rtype >= 5 else 'MK22')
        try:
            self.bufsize = 1024 if int(build[:8]) > 20211002 else 32
        except ValueError:
            self.bufsize = 32
        self.info = dict(struct_version=ver, radio_type=rtype, model=RADIO_TYPES.get(rtype, f'unknown {rtype}'),
                         git=b[8:24].split(b'\0')[0].decode('ascii', 'replace'), build=build, platform=self.platform)
        return self.info

    # flash write: prepare sector / send data / write sector ('W' on MK22, 'X' on STM32/DM32)
    def _wcmd(self, pkt: bytes, sub: int) -> bool:
        ch = pkt[0]
        for _ in range(6):
            self.ser.reset_input_buffer(); self.ser.write(pkt)
            r = self._read(2, 1.0).lstrip(b'-')
            if len(r) >= 2 and r[0] == ch and r[1] == sub:
                return True
            time.sleep(0.03)
        return False

    def write_flash(self, addr: int, data: bytes):
        ch = 0x58 if self.platform in ('STM32', 'DM32') else 0x57
        pos, sector = 0, -1
        while pos < len(data):
            a = addr + pos
            if sector == -1:
                sector = a // SECTOR
                if not self._wcmd(bytes([ch, 1]) + sector.to_bytes(3, 'big'), 1):
                    raise IOError('prepare sector failed')
            n = min(self.bufsize, len(data) - pos, (sector + 1) * SECTOR - a)
            if not self._wcmd(bytes([ch, 2]) + struct.pack('>IH', a, n) + data[pos:pos + n], 2):
                raise IOError(f'send data failed at 0x{a:x}')
            pos += n
            if (addr + pos) // SECTOR != sector or pos >= len(data):
                if not self._wcmd(bytes([ch, 3]), 3):
                    raise IOError('write sector failed')
                sector = -1

    def upload_keps(self, sats: list[dict], backup_dir: str = '~/.local/share/lsr/gd77') -> dict:
        """EXPERIMENTAL. Read-modify-write of the custom data area, then clock sync + reboot."""
        self.open()
        info = self.radio_info()
        base = STM32_FLASH_OFFSET if self.platform in ('STM32', 'DM32') else 0
        self.enter_cps()
        try:
            self.command(1); self.command(6, 3)
            region = self.read(1, base, CUSTOM_DATA_SIZE)
            bdir = Path(backup_dir).expanduser(); bdir.mkdir(parents=True, exist_ok=True)
            bfile = bdir / f'customdata_{info["model"].replace(" ", "_")}_{int(time.time())}.bin'
            bfile.write_bytes(region)
            new = patch_custom_data(region, build_satellite_records(sats))
            self.command(6, 4)
            self.write_flash(base, new)
            self.command(6, 3)
            self.command(6, 7, struct.pack('<I', int(time.time()) & 0xFFFFFFFF))
            self.command(6, 1)                         # reboot
        except Exception:
            self.exit_cps()
            raise
        return dict(model=info['model'], satellites=min(len(sats), MAX_SATS), backup=str(bfile))

    def read_nmea(self, seconds: float = 3.0) -> list[str]:
        """Collect NMEA sentences streamed by GPS-equipped radios (outside CPS mode)."""
        self.open()
        out, buf, t0 = [], b'', time.time()
        while time.time() - t0 < seconds:
            buf += self.ser.read(256)
            while b'\n' in buf:
                line, buf = buf.split(b'\n', 1)
                s = line.decode('ascii', 'ignore').strip()
                if s.startswith('$'):
                    out.append(s)
        return out
