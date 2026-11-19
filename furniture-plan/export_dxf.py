import json, sys, re, ezdxf
import furniture as FU
SCR = sys.argv[1]
P = json.load(open(f'{SCR}/prims.json')); DB = json.load(open(f'{SCR}/db.json'))
doc = ezdxf.new('R2013', setup=True); doc.header['$INSUNITS'] = 4
msp = doc.modelspace()
cols = {'A-FURN': 30, 'A-FURN-BED': 32, 'A-FURN-SOFA': 34, 'A-FURN-WARD': 42, 'A-FURN-KIT': 8, 'A-FURN-RUG': 211,
        'A-FURN-PLANT': 94, 'A-FURN-POOJA': 40, 'A-FURN-SAN': 150, 'A-FURN-TEXT': 7, 'A-ROOM-TEXT': 5, 'A-ANNO': 7}
for n, c in cols.items(): doc.layers.add(n, color=c)
# original drawing (flattened), builder furniture layer dropped
for k, L, v in P:
    if 'FIX FURNITURE' in L: continue
    if L not in doc.layers: doc.layers.add(L, color=8 if not ('WALL' in L.upper()) else 7)
    msp.add_lwpolyline(v, dxfattribs={'layer': L})
for e in DB['entities']:
    if e['type'] in ('MTEXT', 'TEXT') and 'SECLINE' not in e.get('layer', ''):
        p = e.get('insertionPoint') or e.get('startPoint')
        if abs(p['x']) > 200000: continue
        t = re.sub(r'\\[A-Za-z][^;]*;', '', e.get('text', '')).replace('{', '').replace('}', '').replace('\\P', ' ')
        L = e.get('layer', '0')
        if L not in doc.layers: doc.layers.add(L)
        msp.add_text(t, height=min(e.get('textHeight', 150) or 150, 200), dxfattribs={'layer': L}).set_placement((p['x'], p['y']))
# furniture: Unit A + mirrored Unit B (lower axis x=15624, upper axis x=54480)
def mir(x, y):
    ax = 15624 if x < 30000 else 54480
    return (2 * ax - x, y)
for unit in ('A', 'B'):
    T = (lambda x, y: (x, y)) if unit == 'A' else mir
    for e in FU.F:
        if e['kind'] == 'poly':
            pts = [T(*p) for p in e['pts']]
            msp.add_lwpolyline(pts, close=e['closed'], dxfattribs={'layer': e['layer'], 'linetype': 'DASHED' if e['ls'] == '--' else 'CONTINUOUS'})
        elif e['kind'] == 'circle' and e['r'] > 1:
            msp.add_circle(T(*e['c']), e['r'], dxfattribs={'layer': e['layer']})
        elif e['kind'] == 'text' and e['s']:
            for i, line in enumerate(e['s'].split('\n')):
                x, y = T(*e['p'])
                msp.add_text(line, height=e['h'] * 0.8, dxfattribs={'layer': e['layer']}).set_placement((x, y - i * e['h'] * 1.1), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
doc.saveas('Furniture_Layout_4BHK_Duplex.dxf'); print('dxf ok')
