import struct

import pytest

from lsr.rigs.ftx1 import FTX1, fa, fb, md, tone_cmds


def test_ftx1_strings():
    assert fa(145_900_000) == 'FA145900000;'
    assert fb(435_800_123) == 'FB435800123;'
    assert md(0, 'usb') == 'MD02;' and md(1, 'LSB') == 'MD11;' and md(1, 'FM') == 'MD14;'
    assert tone_cmds(67.0) == ['CN00000;', 'CT02;'] and tone_cmds(None) == ['CT00;']
    with pytest.raises(ValueError):
        fa(1_500_000_000)


def test_ftx1_io(fake_serial):
    def resp(b):
        return b'FA436795100;' if b == b'FA;' else b''
    ser = fake_serial(resp)
    r = FTX1(serial_factory=lambda: ser)
    r.set_rx(436_795_100); r.set_tx(145_850_000); r.set_modes('FM', 'FM')
    assert ser.written == b'FA436795100;FB145850000;MD04;MD14;'
    assert r.get_rx() == 436_795_100
    r.set_tone(67.0)                       # cat_tone disabled by default -> nothing sent
    assert ser.written.endswith(b'MD14;FA;')


def test_hamlib_vfo_mode_commands():
    from lsr.rigs.hamlib_net import HamlibRig
    sent = []
    r = HamlibRig(vfo_mode=True, rx_vfo='Main', tx_vfo='Sub')
    r.cmd = lambda line, nlines=1: sent.append(line) or ['436000000']
    r.set_rx(436000000); r.set_tx(145900000); r.set_modes('USB', 'LSB'); r.set_tone(67.0)
    assert sent == ['F Main 436000000', 'F Sub 145900000', 'M Main USB 0', 'M Sub LSB 0', 'C Sub 670']
    assert r.get_rx() == 436000000
