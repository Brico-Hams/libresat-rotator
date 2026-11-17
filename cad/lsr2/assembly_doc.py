"""LSR-2 phase 11e: editable FreeCAD assembly document, whole-assembly STEP and the scene description for the Blender renders. Called by build.py.

LSR2_assembly.FCStd: one Part::Feature per part (label "NN name", properties Balloon / Category / Material / Route), grouped Bought / Machined / Cast /
Printed pattern, plus the Spreadsheet 'Params' with the key numbers of params.py / axes.py / inputs.py (value, unit, tag D / M / P). The shapes are baked in the
head frame (identity placement) and the pattern group is laid out in a row beside the head: the sheet documents the numbers, regenerate the shapes with build.py.
"""
import json
import os
import Part
import FreeCAD as App
import params as P
import axes as AX
import inputs as IN
import parts_table as PT

EL_MOVING = ('yoke_arm', 'yoke_arm_neg', 'saddle', 'boom', 'boom_clamp', 'boom_clamp_neg', 'lift_arm_pos', 'lift_arm_neg', 'counterweight_pos',
             'counterweight_neg', 'clamp_bolts', 'yagi_145', 'yagi_435')


def sheet_rows():
    """(key, value, unit, tag): PARAMETRIC axes.K and params.TOL, DATASHEET NEMA23 / NMRV030 geometry (VERIFY), every scalar inputs row with its own tag."""
    rows = [(f'K_{k}', v, 'mm', 'PARAMETRIC') for k, v in AX.K.items() if isinstance(v, (int, float))]
    rows += [(f'tol_{k}', v, 'mm', 'PARAMETRIC') for k, v in P.TOL.items()]
    rows += [(f'nmrv030_{k}', v, 'mm', 'DATASHEET (catalogue, VERIFY)') for k, v in P.NMRV030_GEO.items() if isinstance(v, (int, float))]
    rows += [(f'nema23_{k}', v, 'mm', 'DATASHEET (NEMA ICS 16 / maker, VERIFY)') for k, v in P.NEMA23.items() if isinstance(v, (int, float))]
    rows += [(f'in_{k}', v, unit, tag) for _, k, v, unit, tag, _ in IN.ROWS if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return rows


def build(out, models, pattern_dir, scene_extra):
    """models: {name: Part.Shape} of the whole head (fabricated + bought). Writes FCStd + STEP under out/cad/lsr2 and returns the scene dict."""
    doc = App.newDocument('LSR2_assembly')
    sheet = doc.addObject('Spreadsheet::Sheet', 'Params')
    sheet.set('A1', 'key')
    sheet.set('B1', 'value')
    sheet.set('C1', 'unit')
    sheet.set('D1', 'tag')
    for i, (k, v, unit, tag) in enumerate(sheet_rows(), start=2):
        sheet.set(f'A{i}', k)
        sheet.set(f'B{i}', repr(float(v)))
        sheet.set(f'C{i}', unit)
        sheet.set(f'D{i}', tag)
        sheet.setAlias(f'B{i}', k)
    groups = {c: doc.addObject('App::DocumentObjectGroup', c.replace(' ', '_')) for c in PT.CATEGORIES}
    for c, g in groups.items():
        g.Label = c

    def add(name, shape, cat, label, part, place=None):
        o = doc.addObject('Part::Feature', name)
        o.Shape = shape
        o.Label = label
        for prop, val in (('Balloon', str(part['pos'])), ('Category', cat), ('Material', part['material']), ('Route', part['route'])):
            o.addProperty('App::PropertyString', prop, 'LSR2')
            setattr(o, prop, val)
        if place is not None:
            o.Placement = place
        groups[cat].addObject(o)

    for name, shape in models.items():
        p = PT.BY_MODEL[name]
        add(name, shape, p['cat'], '%02d %s%s' % (p['pos'], p['label'], ' (%s)' % name.split('_')[-1] if name.endswith(('_pos', '_neg')) else ''), p)
    for i, n in enumerate(q['models'][0] for q in PT.PARTS if q['cat'] == PT.CAST):
        pat = os.path.join(pattern_dir, n + '_pattern.step')
        if os.path.exists(pat):
            add(n + '_pattern', Part.read(pat), PT.PRINTED, '%02d %s (PLA pattern)' % (PT.BY_MODEL[n]['pos'], PT.BY_MODEL[n]['label']), PT.BY_MODEL[n],
                App.Placement(App.Vector(0, -1500.0 - 450.0 * i, 0), App.Rotation()))
    doc.recompute()
    cad = os.path.join(out, 'cad', 'lsr2')
    doc.saveAs(os.path.join(cad, 'LSR2_assembly.FCStd'))
    Part.makeCompound(list(models.values())).exportStep(os.path.join(cad, 'LSR2_assembly.step'))
    App.closeDocument(doc.Name)
    scene = dict(rev=P.REV, el_axis=dict(point=[0, 0, AX.K['z_el']], dir=[0, 1, 0]), el_sign=-1, el_range=list(P.EL_RANGE), el_group=[n for n in EL_MOVING if n in models],
                 category={n: PT.BY_MODEL[n]['cat'] for n in models}, explode=PT.EXPLODE, **scene_extra)
    return scene


def save_scene(out, scene):
    with open(os.path.join(out, 'build', 'lsr2_render_scene.json'), 'w', encoding='utf-8') as fh:
        json.dump(scene, fh, indent=1)
