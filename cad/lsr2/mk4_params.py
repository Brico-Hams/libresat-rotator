"""LSR-2 = replica of the SARCTrac Mk4 (SARCNET, MIT licence, third_party/sarctrac-mk4). Plain Python, no FreeCAD import.

Driving dimensions are read from third_party/sarctrac-mk4/mk4_dump.json at import time (bbox of every part file, placements of the assembly links).
PARTS = every part of the Mk4 with material, density, process and render colour category; classify() maps an assembly instance to a PARTS row.
Run: python mk4_params.py (self-test).
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
MK4_DIR = os.path.join(ROOT, 'third_party', 'sarctrac-mk4')
FC_DIR = os.path.join(MK4_DIR, 'FreeCAD')
ASSEMBLY = 'Rotator.FCStd'
with open(os.path.join(MK4_DIR, 'mk4_dump.json'), encoding='utf-8') as _fh:
    DUMP = json.load(_fh)

GEAR_RATIO = 50          # 2 x NMRV30-G50-D11
EL_SIGN = -1             # elevation up = rotation about -y, as in the other LSR-2 scenes
DENSITY = {'alu_5083': 2.66, 'alu_6082': 2.70, 'steel_A2': 7.93, 'neoprene': 1.25, 'bought': 0.0}   # g/cm3 (bought: mass not computed)
COLOURS = {'alu_sheet': '#b8c7d6', 'alu_plate': '#8a9aa8', 'steel': '#5f6670', 'motor_black': '#26282b', 'gearbox_grey': '#7d8590',
           'rubber': '#111111', 'electronics': '#2f9e57', 'antenna': '#e0b341'}
COLOUR_LABEL = {'alu_sheet': 'aluminium sheet', 'alu_plate': 'aluminium plate', 'steel': 'steel', 'motor_black': 'black motors',
                'gearbox_grey': 'gearbox grey', 'rubber': 'rubber', 'electronics': 'electronics green', 'antenna': 'antenna'}


def snake(s):
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s)
    return re.sub(r'[^A-Za-z0-9]+', '_', s).strip('_').lower() or 'part'


def _finite(b):
    return bool(b) and all(abs(v) < 1e6 for v in b)


def _union(bs):
    return [min(b[i] for b in bs) for i in range(3)] + [max(b[i + 3] for b in bs) for i in range(3)]


def dims(b):
    return [b[i + 3] - b[i] for i in range(3)]


def bbox(stem):
    """Overall bbox [xmin, ymin, zmin, xmax, ymax, zmax] of a part file: the object labelled like the file, else the union of all solid objects."""
    objs = [o for o in DUMP[stem]['objects'] if _finite(o.get('bbox')) and o.get('vol', 0) > 0]
    objs = objs or [o for o in DUMP[stem]['objects'] if _finite(o.get('bbox'))]   # imported bodies (e.g. CableGland) report no volume
    top = [o for o in objs if o['label'] == stem]
    use = top or objs
    return _union([o['bbox'] for o in use]) if use else None


def assembly_objects(pattern, typ='App::Link'):
    return [o for o in DUMP['Rotator']['objects'] if o.get('type') == typ and re.search(pattern, o['label']) and _finite(o.get('bbox'))]


def assembly_box(pattern):
    """Size [dx, dy, dz] of the union of the Rotator links whose label matches pattern."""
    return dims(_union([o['bbox'] for o in assembly_objects(pattern)]))


def _link(label):
    return assembly_objects('^' + re.escape(label) + '$')[0]


# --- driving dimensions (mm), all from the dump ----------------------------------------------------------------------------------
SIZE = {stem: dims(bbox(stem)) for stem in DUMP if DUMP[stem]['objects'] and bbox(stem)}
PLATE_T = min(SIZE['Plate'])
COVER_T = min(SIZE['CoverTop'])
COVER_BOX = assembly_box(r'^Cover(Back|Front|Left|Right|Top|Bottom)$')
ENCLOSURE_BOX = assembly_box(r'^Enclosure(Front|Top|Bottom)$')
SADDLE_T = min(SIZE['SaddlePlateFront'])
BRACKET = sorted(SIZE['Bracket'])
LIFT_ARM_LEN = max(SIZE['LiftArm'])
ANTENNA_LEN = max(SIZE['Antenna'])
HUB = SIZE['Hub']
PLATFORM = SIZE['Platform']
THRUST_BEARING = SIZE['ThrustBearing']
_hr, _ha = _link('HubRight'), _link('HubAz')
EL_AXIS = dict(point=[_hr['pos'][0], 0.0, _hr['pos'][2]], dir=[0.0, 1.0, 0.0])      # hub axis along y
AZ_AXIS = dict(point=[_ha['pos'][0], _ha['pos'][1], 0.0], dir=[0.0, 0.0, 1.0])      # azimuth hub axis along z
EL_RE = r'^(HubRight|HubLeft|Bar|Platform|SaddlePlate|PipeClamp|Antenna|LiftArm|AngleBracket|Saddle|EndStop|CounterWeight)'   # instances turning with the elevation axis
STATIC_RE = r'^(HubAz|ThrustBearing|Bracket)'                                        # mast side, never turns; everything else turns with the azimuth
LEAF_MATERIAL = {'CounterWeight': 'steel_A2', 'Seal': 'neoprene'}                   # leaves of a part file whose material differs from the part's


def _p(name, source, material, process, colour, match=None):
    return dict(name=name, source=source, source_stem=os.path.splitext(source)[0], material=material, density=DENSITY[material],
                process=process, colour=colour, match=match)


# (name, source file, material, process, colour category, regex on the instance label for parts without an own FreeCAD file)
PARTS = [
    _p('Plate', 'Plate.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('Bracket', 'Bracket.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('SaddlePlateFront', 'SaddlePlateFront.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('SaddlePlateLeft', 'SaddlePlateLeft.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('SaddlePlateRight', 'SaddlePlateRight.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('Bar', 'Bar.FCStd', 'alu_6082', 'sawn_bar', 'alu_plate'),
    _p('Angle', 'Angle.FCStd', 'alu_6082', 'sawn_bar', 'alu_plate'),
    _p('LiftArm', 'LiftArm.FCStd', 'alu_6082', 'shs_25', 'alu_plate'),
    _p('Hub', 'Hub.FCStd', 'steel_A2', 'turned', 'steel'),
    _p('Platform', 'Platform.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('PipeClamp', 'PipeClamp.FCStd', 'steel_A2', 'sawn_bar', 'steel'),
    _p('EndStop', 'EndStop.FCStd', 'alu_6082', 'cnc_plate_10mm', 'alu_plate'),
    _p('MotorGasket', 'MotorGasket.FCStd', 'neoprene', 'cut_gasket', 'rubber'),
    _p('DustCap', 'DustCap.FCStd', 'neoprene', 'moulded', 'rubber'),
    _p('CoverCornerBlock', 'CoverCornerBlock.FCStd', 'alu_6082', 'cnc_block_16mm', 'alu_plate'),
    _p('CoverBack', 'CoverBack.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('CoverBottom', 'CoverBottom.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('CoverFront', 'CoverFront.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('CoverLeft', 'CoverLeft.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('CoverRight', 'CoverRight.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('CoverTop', 'CoverTop.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('EnclosureBottom', 'EnclosureBottom.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('EnclosureFront', 'EnclosureFront.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('EnclosureTop', 'EnclosureTop.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('Panel', 'Panel.FCStd', 'alu_5083', 'laser_2mm', 'alu_sheet'),
    _p('MicroSwitchActuatorPin', 'MicroSwitchActuatorPin.FCStd', 'steel_A2', 'turned', 'steel'),
    _p('ThrustBearing', 'ThrustBearing.FCStd', 'bought', 'bought', 'steel'),
    _p('CableGland', 'CableGland.FCStd', 'bought', 'bought', 'steel'),
    _p('Antenna', 'Antenna.FCstd', 'bought', 'bought', 'antenna'),
    _p('WemosD1MiniPro', 'WemosD1MiniPro.FCStd', 'bought', 'bought', 'electronics'),
    _p('XL7015Converter', 'XL7015DC-DC-Converter.FCStd', 'bought', 'bought', 'electronics'),
    # bought STEP models, found in the assembly by instance label
    _p('Converter', 'Converter.step', 'bought', 'bought', 'electronics', r'Converter|XL7015'),
    _p('EE_SX1103', 'EE_SX1103.step', 'bought', 'bought', 'electronics', r'SX1103'),
    _p('MicroSwitch', 'MicroSwitch.step', 'bought', 'bought', 'electronics', r'Micro ?Switch'),
    _p('SMA', 'SMA.step', 'bought', 'bought', 'antenna', r'^SMA|Connector'),
    _p('ToggleSwitch', 'ToggleSwitch.step', 'bought', 'bought', 'electronics', r'Toggle|^Switches'),
    _p('Wemos', 'Wemos.step', 'bought', 'bought', 'electronics', r'Wemos'),
    # parts modelled directly in Rotator.FCStd
    _p('Gearbox_NMRV30', ASSEMBLY, 'bought', 'bought', 'gearbox_grey', r'NMRV|RV30|Gearbox'),
    _p('Motor_NEMA23', ASSEMBLY, 'bought', 'bought', 'motor_black', r'23HS32|Motor'),
    _p('Driver_DM542T', ASSEMBLY, 'bought', 'bought', 'electronics', r'DM542'),
    _p('Controller_Deltron', ASSEMBLY, 'bought', 'bought', 'gearbox_grey', r'Controller'),
    _p('HallSwitch_NJK5002C', ASSEMBLY, 'bought', 'bought', 'electronics', r'HallSwitch'),
    _p('Antenna_2G4', ASSEMBLY, 'bought', 'bought', 'antenna', r'2\.4'),
    _p('Hardware', ASSEMBLY, 'steel_A2', 'bought', 'steel', r'HexScrew|CapScrew|U-Bolt|Washer|Nut'),
    _p('MountingPlate', ASSEMBLY, 'alu_6082', 'cnc_plate_10mm', 'alu_plate', r'MountingPlate'),
]
UNKNOWN = _p('Unclassified', ASSEMBLY, 'bought', 'bought', 'alu_plate')
BY_NAME = {p['name']: p for p in PARTS}


def is_made(p):
    return p['process'] != 'bought'


def classify(source_stem, label):
    """PARTS row of an assembly instance: its own part file first, then the regex on the instance label; None if unknown."""
    for p in PARTS:
        if p['match'] is None and p['source_stem'] == source_stem and source_stem != 'Rotator':
            return p
    return next((p for p in PARTS if p['match'] and re.search(p['match'], label)), None)


def group_of(label):
    """'el' (turns with the elevation axis), 'static' (mast side) or 'az' (turns with the azimuth)."""
    if re.search(EL_RE, label):
        return 'el'
    return 'static' if re.search(STATIC_RE, label) else 'az'


def self_test():
    assert len({p['name'] for p in PARTS}) == len(PARTS) and len({snake(p['name']) for p in PARTS}) == len(PARTS)
    files = {f.lower() for f in os.listdir(FC_DIR)}
    for p in PARTS:
        assert p['source'].lower() in files, 'missing source file ' + p['source']
        assert p['colour'] in COLOURS and p['material'] in DENSITY
        if p['source'].lower().endswith('.fcstd') and p['source_stem'] != 'Rotator' and p['match'] is None:
            assert p['source_stem'] in DUMP and bbox(p['source_stem']) is not None, 'no bbox in mk4_dump.json for ' + p['source']
    assert classify('Plate', 'Plate') is BY_NAME['Plate'] and classify('Rotator', 'HexScrewWasherNut013') is BY_NAME['Hardware']
    assert group_of('HubLeft') == 'el' and group_of('HubAz') == 'static' and group_of('CoverTop') == 'az'
    assert PLATE_T > 0 and COVER_T > 0 and LIFT_ARM_LEN > 0 and ANTENNA_LEN > 0
    print('mk4_params self-test OK (%d parts, plate %.1f, cover %.1f, cover box %s, lift arm %.0f, antenna %.0f)'
          % (len(PARTS), PLATE_T, COVER_T, [round(v) for v in COVER_BOX], LIFT_ARM_LEN, ANTENNA_LEN))


if __name__ == '__main__':
    self_test()
