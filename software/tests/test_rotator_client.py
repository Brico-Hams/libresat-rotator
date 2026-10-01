from lsr.rotator import Rotator, parse_xs, error_text


def firmware(b):
    s = b.decode().strip()
    if s == 'AZ EL':
        return b'AZ123.4 EL45.0\r\n'
    if s == 'XS':
        return b'XS az=483.40 el=45.00 taz=483.40 tel=45.00 vaz=0.00 vel=0.00 mode=0,0 ref=1,0 err=2 vin=12.90 gps=1,8,40.4,-3.7,650.0 utc=2026-10-01T10:00:00.00Z up=5\r\n'
    if s == 'VE':
        return b'VELSR-1 1.0.0\r\n'
    return b''


def test_client(fake_serial):
    ser = fake_serial(firmware)
    r = Rotator(serial_factory=lambda: ser, timeout=0.05)
    assert r.get_pos() == (123.4, 45.0)
    r.set_abs(395.5, 12.25)
    assert ser.written.endswith(b'XP 395.50 12.25\r')
    st = r.status()
    assert st['az'] == 483.4 and st['ref'] == [1, 0] and st['gps'][1] == 8
    assert error_text(st['err']) == ['EL not referenced (check boom IMU)']
    assert r.version() == 'LSR-1 1.0.0'
