#!/usr/bin/env python3
"""LSR-CTL v1.0 — LibreSat Rotator controller board (KiCad 7, scripted).

  python3 hardware/gen_pcb.py place  <out_dir>   -> placed, unrouted board + Specctra DSN
  python3 hardware/gen_pcb.py finish <out_dir>   -> imports the routed SES, pours GND, DRC

Board: 100 x 80 mm, 2 layers, 1.6 mm, 1 oz. Everything hand-solderable (0805 / SOD-123 /
SOIC-8 / TSOT-23-6) plus plug-in modules: Raspberry Pi Pico, 2 x TMC2209 StepStick.
A Raspberry Pi Zero 2 W sits UNDER the board on the 2x20 socket (HAT-style, standard
pre-soldered Pi Zero 2 WH header) and is powered from the on-board 5 V / 2 A buck.

The netlist below IS the schematic (docs/HARDWARE.md renders it as tables).
"""
import sys, os, json, math, pcbnew
from pcbnew import FromMM as MM, VECTOR2I

STAGE, OUT = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KLIB = os.environ.get('KICAD7_FOOTPRINT_DIR', '/usr/share/kicad/footprints').rstrip('/') + '/'
MYLIB = os.path.join(ROOT, 'hardware', 'lib', 'LSR.pretty')
os.makedirs(OUT, exist_ok=True); os.makedirs(MYLIB, exist_ok=True)
NAME = 'lsr_ctl'
PCB = os.path.join(OUT, NAME + '.kicad_pcb')
BW, BH = 100.0, 80.0
ORG = (100.0, 50.0)
def P(x, y): return VECTOR2I(MM(ORG[0] + x), MM(ORG[1] + y))

# ===================================================================== custom footprints
def mk_fp(fname, pads, outline=None, descr=''):
    """pads: (num, kind, x, y, sx, sy, drill, shape)"""
    b = pcbnew.BOARD(); fp = pcbnew.FOOTPRINT(b)
    for num, kind, x, y, sx, sy, drill, shape in pads:
        p = pcbnew.PAD(fp); p.SetNumber(num)
        if kind == 'tht':
            p.SetAttribute(pcbnew.PAD_ATTRIB_PTH); p.SetLayerSet(pcbnew.PAD.PTHMask())
            p.SetDrillSize(VECTOR2I(MM(drill), MM(drill)))
        else:
            p.SetAttribute(pcbnew.PAD_ATTRIB_SMD); p.SetLayerSet(pcbnew.PAD.SMDMask())
        p.SetShape({'rect': pcbnew.PAD_SHAPE_RECT, 'oval': pcbnew.PAD_SHAPE_OVAL, 'circle': pcbnew.PAD_SHAPE_CIRCLE}[shape])
        p.SetSize(VECTOR2I(MM(sx), MM(sy)))
        v = VECTOR2I(MM(x), MM(y)); p.SetPos0(v); p.SetPosition(v); fp.Add(p)
    if outline:
        x0, y0, x1, y1 = outline
        for layer, g, w in ((pcbnew.F_SilkS, 0, 0.15), (pcbnew.F_CrtYd, 0.25, 0.05), (pcbnew.F_Fab, 0, 0.1)):
            s = pcbnew.FP_SHAPE(fp); s.SetShape(pcbnew.SHAPE_T_RECT)
            s.SetStart0(VECTOR2I(MM(x0 - g), MM(y0 - g))); s.SetEnd0(VECTOR2I(MM(x1 + g), MM(y1 + g)))
            s.SetLayer(layer); s.SetWidth(MM(w)); s.SetDrawCoord(); fp.Add(s)
    fp.SetFPID(pcbnew.LIB_ID('LSR', fname)); fp.SetDescription(descr)
    fp.Reference().SetLayer(pcbnew.F_SilkS); fp.Value().SetLayer(pcbnew.F_Fab)
    pcbnew.FootprintSave(MYLIB, fp)

# Raspberry Pi Pico / Pico W / Pico 2 (through-hole on 2.54 mm headers or soldered flat)
pico = []
for i in range(20):
    pico.append((str(i + 1), 'tht', -8.89, -24.13 + 2.54 * i, 1.7, 1.7, 1.0, 'rect' if i == 0 else 'oval'))
    pico.append((str(40 - i), 'tht', 8.89, -24.13 + 2.54 * i, 1.7, 1.7, 1.0, 'oval'))
mk_fp('RaspberryPi_Pico_THT', pico, (-10.5, -25.5, 10.5, 25.5), 'Raspberry Pi Pico family, 2x20 THT, USB at pin 1/40 end')

# ===================================================================== netlist (the schematic)
PICO = {  # Pico pin -> net
    1: 'PI_RX', 2: 'PI_TX', 3: 'GND', 6: 'GPS_RX', 7: 'GPS_TX', 8: 'GND', 9: 'GPS_PPS', 10: 'BTN',
    11: 'TMC_TX', 12: 'TMC_UART', 13: 'GND', 14: 'STEP_AZ', 15: 'DIR_AZ', 16: 'STEP_EL', 17: 'DIR_EL',
    18: 'GND', 19: 'NEN', 20: 'LED', 21: 'SDA0', 22: 'SCL0', 23: 'GND', 24: 'SDA1', 25: 'SCL1',
    26: 'HALL_AZ', 27: 'HALL_EL', 28: 'GND', 30: 'RUN', 31: 'VSENSE', 33: 'GND', 36: '+3V3', 38: 'GND', 39: 'VSYS'}
# Pi Zero 2 W header (socket on the board underside)
PIHDR = {2: '+5V', 4: '+5V', 6: 'GND', 8: 'PI_TX', 10: 'PI_RX', 9: 'GND', 14: 'GND', 16: 'PI_RESET',
         18: 'PI_SWDIO', 20: 'GND', 22: 'PI_SWCLK', 25: 'GND', 30: 'GND', 34: 'GND', 39: 'GND'}

def driver(addr_ms1, step, dirn, motor):
    return {'1': 'NEN', '2': addr_ms1, '3': 'GND', '4': 'TMC_UART', '5': f'PDN2_{motor}', '7': step, '8': dirn,
            '9': 'GND', '10': '+3V3', '11': f'{motor}_1B', '12': f'{motor}_1A', '13': f'{motor}_2A', '14': f'{motor}_2B',
            '15': 'GND', '16': 'VM'}

JST = 'Connector_JST', 'JST_XH_B{n}B-XH-A_1x0{n}_P2.50mm_Vertical'
def jst(n): return (JST[0], JST[1].format(n=n))
R0805 = ('Resistor_SMD', 'R_0805_2012Metric')
C0805 = ('Capacitor_SMD', 'C_0805_2012Metric')
C1206 = ('Capacitor_SMD', 'C_1206_3216Metric')
LED0805 = ('LED_SMD', 'LED_0805_2012Metric')

# ref: (lib, fp, value, x, y, rot, {pad: net}, side)
PARTS = {
    # ---------------- power input + protection
    'J1': ('Connector_AMASS', 'AMASS_XT30PW-M_1x02_P2.50mm_Horizontal', 'XT30 9-24V', 86.5, 18.0, 270, {'1': 'VIN_RAW', '2': 'GND'}, 'F'),
    'J2': ('Connector_BarrelJack', 'BarrelJack_Horizontal', '5.5x2.1 9-24V', 86.0, 31.5, 180, {'1': 'VIN_RAW', '2': 'GND', '3': 'GND'}, 'F'),
    'F1': ('Fuse', 'Fuse_1812_4532Metric', 'PTC 2.5A hold (1812L250)', 73.0, 13.0, 0, {'1': 'VIN_RAW', '2': 'VIN_F'}, 'F'),
    'D1': ('Diode_SMD', 'D_SMB', 'SMBJ24A', 73.0, 19.0, 0, {'1': 'VIN_F', '2': 'GND'}, 'F'),
    'Q1': ('Package_SO', 'SOIC-8_3.9x4.9mm_P1.27mm', 'AO4407A P-MOSFET', 68.0, 26.0, 0,
           {'1': 'VM', '2': 'VM', '3': 'VM', '4': 'QGATE', '5': 'VIN_F', '6': 'VIN_F', '7': 'VIN_F', '8': 'VIN_F'}, 'F'),
    'D3': ('Diode_SMD', 'D_SOD-123', 'BZT52C12 (12V)', 62.0, 22.0, 90, {'1': 'VM', '2': 'QGATE'}, 'F'),
    'R1': R0805 + ('10k', 62.0, 29.0, 90, {'1': 'QGATE', '2': 'GND'}, 'F'),
    'C1': ('Capacitor_THT', 'CP_Radial_D10.0mm_P5.00mm', '470uF 35V', 64.0, 36.0, 0, {'1': 'VM', '2': 'GND'}, 'F'),
    # ---------------- 5 V / 2 A buck for the Pi + Pico (AP63205WU)
    'U2': ('Package_TO_SOT_SMD', 'TSOT-23-6', 'AP63205WU', 50.0, 15.0, 0,
           {'1': '+5V', '2': 'BUCK_EN', '3': 'VM', '4': 'GND', '5': 'BUCK_SW', '6': 'BUCK_BST'}, 'F'),
    'C2': C1206 + ('10uF 50V', 46.8, 12.0, 90, {'1': 'VM', '2': 'GND'}, 'F'),
    'C3': C1206 + ('10uF 50V', 52.8, 20.0, 0, {'1': 'VM', '2': 'GND'}, 'F'),
    'C4': C0805 + ('100nF', 51.5, 11.5, 0, {'1': 'BUCK_BST', '2': 'BUCK_SW'}, 'F'),
    'R2': R0805 + ('100k', 46.6, 16.2, 90, {'1': 'VM', '2': 'BUCK_EN'}, 'F'),
    'L1': ('Inductor_SMD', 'L_Bourns_SRN6045TA', '6.8uH 3A (SRN6045TA-6R8M)', 57.0, 15.0, 0, {'1': 'BUCK_SW', '2': '+5V'}, 'F'),
    'C5': C1206 + ('22uF 10V', 62.5, 13.0, 90, {'1': '+5V', '2': 'GND'}, 'F'),
    'C6': C1206 + ('22uF 10V', 65.5, 13.0, 90, {'1': '+5V', '2': 'GND'}, 'F'),
    'D2': ('Diode_SMD', 'D_SOD-123', 'B5819W (5V->VSYS)', 30.0, 44.0, 0, {'1': 'VSYS', '2': '+5V'}, 'F'),
    'D4': LED0805 + ('green PWR', 36.0, 35.5, 0, {'1': 'GND', '2': 'LED_PWR_A'}, 'F'),
    'R3': R0805 + ('2k2', 36.0, 38.5, 0, {'1': 'LED_PWR_A', '2': '+5V'}, 'F'),
    # ---------------- MCU
    'U1': ('LSR', 'RaspberryPi_Pico_THT', 'Raspberry Pi Pico', 30.5, 60.0, 90, {str(k): v for k, v in PICO.items()}, 'F'),
    'D5': LED0805 + ('blue STATUS', 37.0, 76.0, 0, {'1': 'GND', '2': 'LED_A'}, 'F'),
    'R4': R0805 + ('1k', 32.0, 76.0, 0, {'1': 'LED', '2': 'LED_A'}, 'F'),
    'R5': R0805 + ('100k', 52.0, 41.0, 90, {'1': 'VM', '2': 'VSENSE'}, 'F'),
    'R6': R0805 + ('10k', 54.5, 41.0, 90, {'1': 'VSENSE', '2': 'GND'}, 'F'),
    'C7': C0805 + ('100nF', 57.0, 41.0, 90, {'1': 'VSENSE', '2': 'GND'}, 'F'),
    'C8': C0805 + ('10uF', 25.0, 44.0, 0, {'1': '+3V3', '2': 'GND'}, 'F'),
    'R7': R0805 + ('4k7', 6.0, 31.0, 90, {'1': '+3V3', '2': 'SDA0'}, 'F'),
    'R8': R0805 + ('4k7', 8.5, 31.0, 90, {'1': '+3V3', '2': 'SCL0'}, 'F'),
    'R9': R0805 + ('4k7', 11.0, 31.0, 90, {'1': '+3V3', '2': 'SDA1'}, 'F'),
    'R10': R0805 + ('4k7', 13.5, 31.0, 90, {'1': '+3V3', '2': 'SCL1'}, 'F'),
    'R11': R0805 + ('1k', 46.0, 44.0, 0, {'1': 'TMC_TX', '2': 'TMC_UART'}, 'F'),
    'R12': R0805 + ('1k', 20.0, 36.0, 0, {'1': 'PI_RESET', '2': 'RUN'}, 'F'),
    'R13': R0805 + ('10k', 41.0, 44.0, 0, {'1': '+3V3', '2': 'NEN'}, 'F'),
    # ---------------- stepper drivers (TMC2209 StepStick, UART addr 0 = AZ, 1 = EL)
    'A1': ('Module', 'Pololu_Breakout-16_15.2x20.3mm', 'TMC2209 AZ (addr 0)', 60.0, 50.0, 0, driver('GND', 'STEP_AZ', 'DIR_AZ', 'MAZ'), 'F'),
    'A2': ('Module', 'Pololu_Breakout-16_15.2x20.3mm', 'TMC2209 EL (addr 1)', 80.0, 50.0, 0, driver('+3V3', 'STEP_EL', 'DIR_EL', 'MEL'), 'F'),
    'JP1': ('Jumper', 'SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm', 'PDN pin5 AZ', 66.3, 47.0, 0, {'1': 'PDN2_MAZ', '2': 'TMC_UART'}, 'F'),
    'JP2': ('Jumper', 'SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm', 'PDN pin5 EL', 86.3, 47.0, 0, {'1': 'PDN2_MEL', '2': 'TMC_UART'}, 'F'),
    'C9': ('Capacitor_THT', 'CP_Radial_D8.0mm_P3.50mm', '100uF 35V', 75.0, 41.5, 0, {'1': 'VM', '2': 'GND'}, 'F'),
    'C10': ('Capacitor_THT', 'CP_Radial_D8.0mm_P3.50mm', '100uF 35V', 90.0, 41.5, 0, {'1': 'VM', '2': 'GND'}, 'F'),
    'C11': C0805 + ('100nF', 76.3, 52.0, 90, {'1': 'VM', '2': 'GND'}, 'F'),
    'C12': C0805 + ('100nF', 96.5, 52.0, 90, {'1': 'VM', '2': 'GND'}, 'F'),
    'J3': jst(4) + ('MOTOR AZ', 62.5, 75.0, 0, {'1': 'MAZ_1A', '2': 'MAZ_1B', '3': 'MAZ_2A', '4': 'MAZ_2B'}, 'F'),
    'J4': jst(4) + ('MOTOR EL', 82.5, 75.0, 0, {'1': 'MEL_1A', '2': 'MEL_1B', '3': 'MEL_2A', '4': 'MEL_2B'}, 'F'),
    # ---------------- sensors (I2C0 = AZ side, I2C1 = EL side), GPS, index, button
    'J5': jst(4) + ('ENC AZ (AS5600)', 3.5, 12.0, 0, {'1': '+3V3', '2': 'SDA0', '3': 'SCL0', '4': 'GND'}, 'F'),
    'J6': jst(4) + ('IMU BASE', 17.5, 12.0, 0, {'1': '+3V3', '2': 'SDA0', '3': 'SCL0', '4': 'GND'}, 'F'),
    'J7': jst(4) + ('ENC EL (AS5600)', 3.5, 21.0, 0, {'1': '+3V3', '2': 'SDA1', '3': 'SCL1', '4': 'GND'}, 'F'),
    'J8': jst(4) + ('IMU EL (boom)', 17.5, 21.0, 0, {'1': '+3V3', '2': 'SDA1', '3': 'SCL1', '4': 'GND'}, 'F'),
    'J9': jst(3) + ('HALL AZ', 31.5, 21.0, 0, {'1': '+3V3', '2': 'HALL_AZ', '3': 'GND'}, 'F'),
    'J10': jst(3) + ('HALL/LIM EL', 42.5, 21.0, 0, {'1': '+3V3', '2': 'HALL_EL', '3': 'GND'}, 'F'),
    'J12': jst(5) + ('GPS', 31.5, 12.0, 0, {'1': '+3V3', '2': 'GND', '3': 'GPS_RX', '4': 'GPS_TX', '5': 'GPS_PPS'}, 'F'),
    'J13': jst(2) + ('PARK/STOP', 11.0, 76.0, 0, {'1': 'BTN', '2': 'GND'}, 'F'),
    'J14': ('Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical', 'SWD from Pi', 14.0, 5.5, 270,
            {'1': 'PI_SWCLK', '2': 'GND', '3': 'PI_SWDIO'}, 'F'),
    # ---------------- Raspberry Pi Zero 2 W socket (board underside)
    'J11': ('Connector_PinSocket_2.54mm', 'PinSocket_2x20_P2.54mm_Vertical', 'Pi Zero 2 W', 17.0, 76.5, 90, {str(k): v for k, v in PIHDR.items()}, 'B'),
    # ---------------- mounting
    'H1': ('MountingHole', 'MountingHole_3.2mm_M3', 'M3', 3.5, 3.5, 0, {}, 'F'),
    'H2': ('MountingHole', 'MountingHole_3.2mm_M3', 'M3', 96.5, 3.5, 0, {}, 'F'),
    'H3': ('MountingHole', 'MountingHole_3.2mm_M3', 'M3', 3.5, 76.5, 0, {}, 'F'),
    'H4': ('MountingHole', 'MountingHole_3.2mm_M3', 'M3', 96.5, 76.5, 0, {}, 'F'),
}
# Pi Zero (65 x 30) under the board: origin (PX, PY); pin 1 at (8.37, 4.77), pin 2 at (8.37, 2.23)
PX, PY = 17.5, 2.0
PI_HOLES = [(PX + 3.5, PY + 3.5), (PX + 61.5, PY + 3.5), (PX + 3.5, PY + 26.5), (PX + 61.5, PY + 26.5)]

FAB_REFS = {'R5', 'R6', 'C7', 'R7', 'R8', 'R9', 'R10', 'C11', 'C12', 'C5', 'C6', 'R2', 'U2', 'R3', 'C10'}
POWER = {'VIN_RAW': 1.5, 'VIN_F': 1.5, 'VM': 1.2, '+5V': 1.0, 'VSYS': 0.6, 'GND': 0.8}
BUCK = {'BUCK_SW'}
MOTOR = 0.6


def net_class_of(n):
    if n in POWER: return 'Power'
    if n in BUCK: return 'Buck'
    if n.startswith('MAZ_') or n.startswith('MEL_'): return 'Motor'
    return None


def build():
    board = pcbnew.NewBoard(PCB)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(2); ds.SetBoardThickness(MM(1.6))
    ns = ds.m_NetSettings
    dc = ns.m_DefaultNetClass
    dc.SetClearance(MM(0.2)); dc.SetTrackWidth(MM(0.3)); dc.SetViaDiameter(MM(0.7)); dc.SetViaDrill(MM(0.35))
    for cname, w in (('Power', 1.0), ('Motor', MOTOR), ('Buck', 0.6)):
        nc = pcbnew.NETCLASS(cname)
        nc.SetClearance(MM(0.25)); nc.SetTrackWidth(MM(w)); nc.SetViaDiameter(MM(1.0)); nc.SetViaDrill(MM(0.5))
        ns.m_NetClasses[cname] = nc
    ds.m_MinClearance = MM(0.2); ds.m_TrackMinWidth = MM(0.2); ds.m_ViasMinSize = MM(0.6); ds.m_MinThroughDrill = MM(0.3)
    ds.m_CopperEdgeClearance = MM(0.4)

    nets = {}
    def net(n):
        if n not in nets:
            ni = pcbnew.NETINFO_ITEM(board, n); board.Add(ni); nets[n] = ni
            c = net_class_of(n)
            if c: ns.SetNetclassPatternAssignment(n, c) if hasattr(ns, 'SetNetclassPatternAssignment') else None
        return nets[n]

    # board outline (rounded corners r=2)
    def edge(a, b):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(P(*a)); s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
    def arc(c, s0, ang):
        s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetCenter(P(*c)); s.SetStart(P(*s0))
        s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T)); s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
    r = 2.0
    edge((r, 0), (BW - r, 0)); edge((BW, r), (BW, BH - r)); edge((BW - r, BH), (r, BH)); edge((0, BH - r), (0, r))
    arc((r, r), (0, r), 90); arc((BW - r, r), (BW - r, 0), 90); arc((BW - r, BH - r), (BW, BH - r), 90); arc((r, BH - r), (r, BH), 90)

    fps = {}
    for ref, (lib, fpn, val, x, y, rot, padnets, side) in PARTS.items():
        libdir = MYLIB if lib == 'LSR' else KLIB + lib + '.pretty'
        fp = pcbnew.FootprintLoad(libdir, fpn)
        if fp is None: raise SystemExit(f'footprint not found: {lib}:{fpn}')
        fp.SetFPID(pcbnew.LIB_ID(lib, fpn))
        fp.SetReference(ref); fp.SetValue(val)
        board.Add(fp)
        if side == 'B': fp.Flip(fp.GetPosition(), False)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
        for p in fp.Pads():
            n = padnets.get(p.GetNumber())
            if n: p.SetNet(net(n))
        t = fp.Reference(); t.SetTextSize(VECTOR2I(MM(0.9), MM(0.9))); t.SetTextThickness(MM(0.14))
        if ref in FAB_REFS: t.SetLayer(pcbnew.F_Fab)
        if ref in ('A1', 'A2'): t.SetPosition(P(x + 6.35, y + 6.0)); t.SetTextSize(VECTOR2I(MM(1.5), MM(1.5)))
        fps[ref] = fp

    # --- Pi socket: rows along x, pin 1 at (PX+8.37, PY+4.77), pin 2 at (PX+8.37, PY+2.23)
    s = fps['J11']
    def padpos(fp, num):
        for p in fp.Pads():
            if p.GetNumber() == num:
                v = p.GetPosition(); return (pcbnew.ToMM(v.x) - ORG[0], pcbnew.ToMM(v.y) - ORG[1])
    want1, want2, want3 = (PX + 8.37, PY + 4.77), (PX + 8.37, PY + 2.23), (PX + 8.37 + 2.54, PY + 4.77)
    for rot in (0, 90, 180, 270):
        s.SetOrientationDegrees(rot); s.SetPosition(P(0, 0))
        p1, p2, p3 = padpos(s, '1'), padpos(s, '2'), padpos(s, '3')
        d2 = (p2[0] - p1[0], p2[1] - p1[1]); d3 = (p3[0] - p1[0], p3[1] - p1[1])
        if abs(d2[0]) < 0.01 and d2[1] < 0 and d3[0] > 0:
            s.SetPosition(P(want1[0] - p1[0], want1[1] - p1[1])); break
    else:
        raise SystemExit('could not orient Pi socket')
    assert math.dist(padpos(s, '2'), want2) < 0.01 and math.dist(padpos(s, '39'), (PX + 8.37 + 19 * 2.54, PY + 4.77)) < 0.01

    # Pi Zero mounting holes (M2.5 standoffs 11 mm between Pi and board)
    for i, (hx, hy) in enumerate(PI_HOLES):
        fp = pcbnew.FootprintLoad(KLIB + 'MountingHole.pretty', 'MountingHole_2.7mm_M2.5')
        fp.SetFPID(pcbnew.LIB_ID('MountingHole', 'MountingHole_2.7mm_M2.5'))
        fp.SetReference(f'H{5 + i}'); fp.SetValue('M2.5 Pi'); fp.SetPosition(P(hx, hy)); board.Add(fp)
        fp.Reference().SetVisible(False)

    # Pi Zero outline on the bottom silk/fab + keep-out note
    for layer in (pcbnew.B_SilkS, pcbnew.B_Fab):
        sh = pcbnew.PCB_SHAPE(board); sh.SetShape(pcbnew.SHAPE_T_RECT); sh.SetStart(P(PX, PY)); sh.SetEnd(P(PX + 65, PY + 30))
        sh.SetLayer(layer); sh.SetWidth(MM(0.12)); board.Add(sh)

    # texts
    def text(t, x, y, size=1.2, layer=pcbnew.F_SilkS, rot=0):
        o = pcbnew.PCB_TEXT(board); o.SetText(t); o.SetPosition(P(x, y)); o.SetLayer(layer)
        o.SetTextSize(VECTOR2I(MM(size), MM(size))); o.SetTextThickness(MM(size * 0.15)); o.SetTextAngleDegrees(rot)
        if layer == pcbnew.B_SilkS: o.SetMirrored(True)
        board.Add(o)
    text('LSR-CTL v1.0', 41.5, 28.5, 1.3)
    text('LibreSat Rotator', 41.5, 30.7, 0.9)
    text('9-24V', 97.0, 45.0, 1.0, rot=90)
    text('PI ZERO 2 W HERE (UNDERSIDE)', PX + 32.5, PY + 22, 1.2, pcbnew.B_SilkS)
    text('HEADER PINS UP INTO J11', PX + 32.5, PY + 25, 1.0, pcbnew.B_SilkS)
    text('CERN-OHL-S v2', 40, 74, 1.0, pcbnew.B_SilkS)
    text('AZ addr0', 66.35, 61.0, 0.9, rot=90); text('EL addr1', 86.35, 61.0, 0.9, rot=90)

    # net classes: KiCad 7 python sets assignments via pattern map
    try:
        for n in nets:
            c = net_class_of(n)
            if c: ns.m_NetClassPatternAssignments.append(pcbnew.NETCLASS_PATTERN(n, c)) if hasattr(pcbnew, 'NETCLASS_PATTERN') else None
    except Exception:
        pass
    board.BuildConnectivity()
    return board, fps, nets


def write_dsn_classes(dsn_path, nets):
    """KiCad 7's Python API cannot attach net classes, so move the nets inside the Specctra file
    (KiCad already exports the empty Power/Motor classes with their widths and via padstacks)."""
    import re
    s = open(dsn_path).read()
    def q(n): return f'"{n}"' if any(c in n for c in ' +-()') else n
    groups = {'Power': [n for n in nets if net_class_of(n) == 'Power' and n != 'GND'],
              'Motor': [n for n in nets if net_class_of(n) == 'Motor'],
              'Buck': [n for n in nets if net_class_of(n) == 'Buck']}
    moved = {m for g in groups.values() for m in g}
    m = re.search(r'\(class kicad_default (.*?)\n      \(circuit', s, re.S)
    members = m.group(1).split()
    keep = [t for t in members if t.strip('"') not in moved]
    s = s[:m.start(1)] + ' '.join(keep) + s[m.end(1):]
    for g, mem in groups.items():
        s = s.replace(f'(class {g}\n', f'(class {g} {" ".join(q(x) for x in mem)}\n', 1)
    open(dsn_path, 'w').write(s)



def sexpr(text):
    """Minimal S-expression reader for Specctra files."""
    import re
    toks = re.findall(r'"[^"]*"|\(|\)|[^\s()]+', text)
    stack = [[]]
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t.strip('"'))
    return stack[0][0]


def import_ses(board, path):
    """KiCad 7 can only import SES from the GUI, so add the routed tracks/vias ourselves."""
    tree = sexpr(open(path).read())
    def find(node, key):
        return [c for c in node if isinstance(c, list) and c and c[0] == key]
    routes = find(tree, 'routes')[0]
    res = find(routes, 'resolution')[0]
    scale = {'um': 1e-3, 'mm': 1.0, 'mil': 0.0254}[res[1]] / float(res[2])     # file units -> mm
    layers = {'F.Cu': pcbnew.F_Cu, 'B.Cu': pcbnew.B_Cu}
    n_tr = n_via = 0
    for netnode in find(find(routes, 'network_out')[0], 'net'):
        net = board.FindNet(netnode[1])
        for w in find(netnode, 'wire'):
            pth = find(w, 'path')[0]
            layer, width = layers[pth[1]], float(pth[2]) * scale
            pts = [(float(pth[i]) * scale, -float(pth[i + 1]) * scale) for i in range(3, len(pth) - 1, 2)]
            for a, b in zip(pts, pts[1:]):
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(VECTOR2I(MM(a[0]), MM(a[1]))); t.SetEnd(VECTOR2I(MM(b[0]), MM(b[1])))
                t.SetWidth(MM(width)); t.SetLayer(layer); t.SetNet(net); board.Add(t); n_tr += 1
        for v in find(netnode, 'via'):
            import re
            m = re.search(r'_(\d+):(\d+)_um', v[1])
            dia, drill = (int(m.group(1)) / 1000, int(m.group(2)) / 1000) if m else (0.7, 0.35)
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(VECTOR2I(MM(float(v[2]) * scale), MM(-float(v[3]) * scale)))
            via.SetWidth(MM(dia)); via.SetDrill(MM(drill)); via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            via.SetNet(net); board.Add(via); n_via += 1
    return n_tr, n_via


if STAGE == 'place':
    board, fps, nets = build()
    board.Save(PCB)
    dsn = os.path.join(OUT, NAME + '.dsn')
    pcbnew.ExportSpecctraDSN(board, dsn)
    write_dsn_classes(dsn, list(nets))
    json.dump({'nets': sorted(nets)}, open(os.path.join(OUT, 'nets.json'), 'w'), indent=1)
    print('placed', PCB, len(nets), 'nets')

elif STAGE == 'finish':
    board = pcbnew.LoadBoard(PCB)
    ses = os.path.join(OUT, NAME + '.ses')
    n_tr, n_via = import_ses(board, ses)
    print(f'imported {n_tr} track segments, {n_via} vias from {os.path.basename(ses)}')
    # GND pours on both layers
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNetCode(board.FindNet('GND').GetNetCode())
        o = z.Outline(); o.NewOutline()
        for x, y in ((0.3, 0.3), (BW - 0.3, 0.3), (BW - 0.3, BH - 0.3), (0.3, BH - 0.3)):
            o.Append(MM(ORG[0] + x), MM(ORG[1] + y))
        z.SetLocalClearance(MM(0.3)); z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.5))
        board.Add(z)
    # stitching vias on a grid where free (both pours connected)
    gnd = board.FindNet('GND')
    filler = pcbnew.ZONE_FILLER(board); filler.Fill(board.Zones())
    rpt = os.path.join(OUT, NAME + '_drc.rpt')
    board.Save(PCB)
    pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    # pads whose thermal relief is starved by tracks get a solid connection instead
    import re
    txt = open(rpt).read(); fixed = 0
    for blk in txt.split('[starved_thermal]')[1:]:
        m = re.search(r'PTH pad (\S+) \[GND\] of (\S+)', blk.split('\n[')[0])
        if m:
            fp = board.FindFootprintByReference(m.group(2))
            for p in fp.Pads():
                if p.GetNumber() == m.group(1): p.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL); fixed += 1
    if fixed:
        filler.Fill(board.Zones()); board.Save(PCB)
        pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    print('solid-connected starved pads:', fixed)
    print('finished', PCB)
