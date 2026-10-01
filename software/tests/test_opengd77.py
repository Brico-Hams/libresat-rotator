import json
import struct
from pathlib import Path

from lsr.rigs.opengd77 import (OpenGD77, build_satellite_records, compress_tle_text, decompress_tle_text,
                               patch_custom_data, CUSTOM_DATA_SIZE, SAT_BLOCK)

DATA = Path(__file__).parent / 'data'


def test_records_match_webcps_byte_for_byte():
    """Golden file produced by running buildSatelliteRecords() of OpenGD77 WebCPS (js/webusb.js) in Node."""
    sats = json.loads((DATA / 'gd77_sats.json').read_text())
    conv = [dict(name=s['name'], line1=s['tle']['line1'], line2=s['tle']['line2'], rx1=s['rx1'], tx1=s['tx1'],
                 tx_ctcss=s.get('txCtcss'), arm_ctcss=s.get('armCtcss'), extra=s.get('aprsConfig', '')) for s in sats]
    assert build_satellite_records(conv).hex() == (DATA / 'gd77_records_webcps.hex').read_text().strip()


def test_compress_roundtrip():
    t = '26273.50000000 .00012000'
    assert decompress_tle_text(compress_tle_text(t)) == t


def test_patch_custom_data_preserves_blocks():
    region = bytearray(b'\xff' * CUSTOM_DATA_SIZE)
    region[0:12] = b'OpenGD77\0\0\0\0'
    struct.pack_into('<II', region, 12, 1, 16)                # an existing 16-byte block (e.g. melody)
    region[20:36] = bytes(range(16))
    rec = bytes([7]) * SAT_BLOCK
    out = patch_custom_data(bytes(region), rec)
    assert out[20:36] == bytes(range(16))
    assert struct.unpack_from('<II', out, 36) == (3, SAT_BLOCK) and out[44:44 + SAT_BLOCK] == rec
    out2 = patch_custom_data(out, bytes(SAT_BLOCK))           # replace in place
    assert struct.unpack_from('<II', out2, 36) == (3, SAT_BLOCK) and out2[44] == 0


def test_sync_clock_protocol(fake_serial):
    ser = fake_serial(lambda b: b'-' if b[:1] == b'C' else b'')
    dev = OpenGD77(serial_factory=lambda: ser)
    from datetime import datetime, timezone
    assert dev.sync_clock(datetime(2026, 10, 1, tzinfo=timezone.utc))
    ts = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
    assert ser.written == b'C\x00' + b'C\x06\x07' + struct.pack('<I', ts) + b'C\x05' + b'C\x07'
