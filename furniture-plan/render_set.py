"""Builds the drawing set: one A1 sheet per possible North direction (both units, both levels,
Vastu-resolved), plus a furniture-schedule / standards sheet, and one DXF per orientation.
usage: python3 render_set.py <dir containing prims.json and db.json>"""
import json, sys, math, re
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle, FancyArrow
from matplotlib.backends.backend_pdf import PdfPages
import layout as Lo

SCR = sys.argv[1]
P = json.load(open(f'{SCR}/prims.json'))
DB = json.load(open(f'{SCR}/db.json'))
SKIP = ('FIX FURNITURE', 'DIM', 'SECLINE', 'NOTES')
AX = {'lower': 15624, 'upper': 54480}          # party-wall mirror axes
EXT = {'lower': (2900, 28350, 2550, 18100), 'upper': (41800, 67150, 2550, 18100)}
SIDE_WORD = {'T': 'TOP', 'B': 'BOTTOM', 'L': 'LEFT', 'R': 'RIGHT'}

ROOMS = {
    'lower': [((6894, 9541, 15509, 14416), '#fbf7f0'), ((3919, 11850, 6779, 16361), '#f4f1ec'), ((6894, 14531, 9899, 16361), '#e8f2f8'),
              ((10014, 14531, 15509, 16361), '#eef5ea'), ((3919, 3416, 7884, 7686), '#f8f3ea'), ((4644, 7801, 6779, 9426), '#e8f2f8'),
              ((6894, 7801, 7884, 9541), '#fbf7f0'), ((3919, 9541, 6779, 11850), '#f1f1f1')],
    'upper': [((42776, 3636, 46741, 7906), '#f8f3ea'), ((45750, 8021, 46740, 9646), '#f8f3ea'), ((43500, 8021, 45635, 9646), '#e8f2f8'),
              ((42776, 12126, 46625, 16581), '#eef3f8'), ((46740, 12126, 48570, 16581), '#e8f2f8'), ((48685, 12126, 50515, 16581), '#e8f2f8'),
              ((45525, 9761, 48570, 12011), '#fbf7f0'), ((42776, 9761, 45525, 12011), '#f1f1f1'), ((48685, 9761, 50630, 12011), '#f6efe6'),
              ((50630, 9761, 54365, 14636), '#f6efe6'), ((50630, 14751, 53081, 16176), '#eef5ea')]}


def floor_of(x):
    return 'lower' if x < 30000 else 'upper'


def mir(p):
    a = AX[floor_of(p[0])]
    return (2 * a - p[0], p[1])


def style(L):
    U = L.upper()
    if ('WALL' in U and 'LOW' not in U) or 'COLUMN' in U: return '#111', 1.0, 5
    if 'WINDOW' in U: return '#1f5fbf', 0.45, 5
    if 'DOOR' in U: return '#8b1a1a', 0.45, 5
    if 'SANITORY' in U: return '#4d6f8c', 0.35, 4
    if 'STAIR' in U or U == 'STAIR': return '#777', 0.3, 4
    if 'RAILING' in U or 'LOW HT' in U: return '#444', 0.45, 4
    if U.startswith('B-'): return '#d6d6d6', 0.2, 1
    return '#c4c4c4', 0.22, 1


def edge(layer):
    return '#2a6fa8' if ('SAN' in layer or 'AC' in layer or 'CURTAIN' in layer) else '#6b4a2b'


def layout_pair(north):
    c = Lo.compass_for(north)
    A = Lo.build(c, 'A')
    B = Lo.build(Lo.mirror_compass(c), 'B')
    assert not Lo.check(A) and not Lo.check(B)
    return c, A, B


def prims_of(L, mirrored):
    T = mir if mirrored else (lambda p: p)
    out = []
    for e in L.F:
        e2 = dict(e)
        if e['kind'] == 'poly': e2['pts'] = [T(p) for p in e['pts']]
        else: e2['c' if e['kind'] == 'circle' else 'p'] = T(e['c'] if e['kind'] == 'circle' else e['p'])
        out.append(e2)
    return out


def draw_plan(ax, floor, items, title):
    x0, x1, y0, y1 = EXT[floor]
    for mirrored in (False, True):
        for (a, b, c2, d), col in ROOMS[floor]:
            if mirrored:
                a, c2 = 2 * AX[floor] - c2, 2 * AX[floor] - a
            ax.add_patch(Rectangle((a, b), c2 - a, d - b, fc=col, ec='none', zorder=0))
    for k, L, v in P:
        if any(s in L for s in SKIP): continue
        if not any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in v): continue
        col, lw, z = style(L)
        ax.plot([p[0] for p in v], [p[1] for p in v], color=col, lw=lw, zorder=z, solid_capstyle='butt')
    for e in items:
        if e['kind'] == 'poly':
            pts = e['pts']
            if not any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts): continue
            if e['closed']:
                ax.add_patch(Polygon(pts, closed=True, fc=e['fill'] or 'none', ec=edge(e['layer']), lw=e['lw'], ls=e['ls'], zorder=3))
            else:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color=edge(e['layer']), lw=e['lw'], ls=e['ls'], zorder=3)
        elif e['kind'] == 'circle':
            c = e['c']
            if x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and e['r'] > 1:
                ax.add_patch(Circle(c, e['r'], fc=e['fill'] or 'none', ec='#6b4a2b', lw=e['lw'], zorder=3.5))
        elif e['kind'] == 'text':
            p = e['p']
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1 and e['s']:
                ax.text(p[0], p[1], e['s'], fontsize=e['h'] / 19.5, ha='center', va='center', color=e['color'],
                        fontweight='bold' if e['bold'] else 'normal', zorder=6, linespacing=1.05)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.axis('off')
    ax.text(x0 + 100, y1 - 150, title, fontsize=15, fontweight='bold', color='#1d2b4f', va='top')
    for lab, xa in (('UNIT A', AX[floor] - 5600), ('UNIT B', AX[floor] + 5600)):
        ax.text(xa, y0 + 250, lab, fontsize=13, fontweight='bold', color='#5b3a7a', ha='center')
    # scale bar
    sx = x0 + 200
    for i in range(3):
        ax.add_patch(Rectangle((sx + i * 1000, y0 + 120), 1000, 90, fc='k' if i % 2 == 0 else 'w', ec='k', lw=0.6))
    ax.text(sx, y0 + 330, '0', fontsize=7, ha='center'); ax.text(sx + 3000, y0 + 330, '3 m', fontsize=7, ha='center')


def compass(ax, north, cx, cy, r):
    ang = {'T': 90, 'L': 180, 'B': 270, 'R': 0}[north]
    ax.add_patch(Circle((cx, cy), r, fc='#fff', ec='#1d2b4f', lw=1.4))
    for k, lab in enumerate('NESW'):
        a = math.radians(ang - 90 * k)
        ax.text(cx + 1.25 * r * math.cos(a), cy + 1.25 * r * math.sin(a), lab, ha='center', va='center',
                fontsize=16 if lab == 'N' else 11, fontweight='bold', color='#b3261e' if lab == 'N' else '#1d2b4f')
    a = math.radians(ang)
    ax.add_patch(Polygon([(cx + 0.9 * r * math.cos(a), cy + 0.9 * r * math.sin(a)),
                          (cx + 0.22 * r * math.cos(a + 2.2), cy + 0.22 * r * math.sin(a + 2.2)),
                          (cx + 0.22 * r * math.cos(a - 2.2), cy + 0.22 * r * math.sin(a - 2.2))], fc='#b3261e', ec='none'))


def grade_head(d):
    return {'S': 'IDEAL', 'E': 'GOOD', 'W': 'COMPROMISE', 'N': 'AVOID'}[d]


def choice_rows(c, L):
    ch = L.choices
    rows = []
    corner = {'P1': 'dining, top-left', 'P2': 'living, top-right', 'P3': 'living, bottom-right', 'P4': 'living, bottom-left'}[ch['Pooja position']]
    rows.append(('Pooja (NE corner)', f"{corner}; devotee faces {ch['Devotee faces']}", 'IDEAL' if ch['Devotee faces'] == 'E' else 'GOOD'))
    rows.append(('Cooking', f"hob on {SIDE_WORD[ch['Hob wall (cook faces East)']].lower()} side, cook faces E", 'IDEAL'))
    for k, lab in (('Bedroom-1 bed head', 'BR-1 Parents head'), ('Bedroom-2 bed head', 'BR-2 Son/Guest head'),
                   ('Bedroom-3 bed head', 'BR-3 Kids head'), ('Master bed head', 'BR-4 Master head')):
        d = c[ch[k]]
        rows.append((lab, f"towards {d}", grade_head(d)))
    sf = ch['Sofa faces']
    rows.append(('Sofa (seated facing)', sf, 'IDEAL' if sf in ('N', 'E') else 'COMPROMISE'))
    return rows


GCOL = {'IDEAL': '#1e7d32', 'GOOD': '#3c8d40', 'ACCEPTABLE': '#8a6d00', 'COMPROMISE': '#b36b00', 'NOT IDEAL': '#b3261e', 'AVOID': '#b3261e'}


def table(ax, x, y, title, header, rows, colw, fs=8.2, rowh=0.0185):
    ax.text(x, y, title, fontsize=11, fontweight='bold', color='#5b3a7a', va='top'); y -= 0.024
    cx = x
    for h, w in zip(header, colw):
        ax.text(cx, y, h, fontsize=fs, fontweight='bold', va='top', color='#333'); cx += w
    y -= rowh * 0.9
    ax.plot([x, x + sum(colw) - 0.01], [y + 0.004, y + 0.004], color='#999', lw=0.6)
    for r in rows:
        cx = x
        for i, (val, w) in enumerate(zip(r, colw)):
            col = GCOL.get(val, '#222') if isinstance(val, str) else '#222'
            ax.text(cx, y, val, fontsize=fs, va='top', color=col, fontweight='bold' if val in GCOL else 'normal')
            cx += w
        y -= rowh
    return y - 0.012


def orientation_sheet(pdf, north, c, A, B):
    fig = plt.figure(figsize=(33.11, 23.39))
    axL = fig.add_axes([0.005, 0.505, 0.715, 0.485]); axU = fig.add_axes([0.005, 0.01, 0.715, 0.485])
    itemsL = prims_of(A, False) + prims_of(B, True)
    draw_plan(axL, 'lower', itemsL, 'LOWER LEVEL  ·  living · dining · kitchen · parents')
    draw_plan(axU, 'upper', itemsL, 'UPPER LEVEL  ·  master · kids · son / guest')
    for ax, x in ((axL, 9104), (axL, 2 * AX['lower'] - 9104)):
        ax.annotate('MAIN ENTRY', xy=(x, 9450), xytext=(x, 8300), ha='center', fontsize=9, fontweight='bold', color='#8b1a1a',
                    arrowprops=dict(arrowstyle='->', color='#8b1a1a', lw=1.3), zorder=7)
    # right panel
    R = fig.add_axes([0.725, 0.01, 0.27, 0.98]); R.axis('off'); R.set_xlim(0, 1); R.set_ylim(0, 1)
    R.add_patch(Rectangle((0, 0), 1, 1, fc='none', ec='#5b3a7a', lw=1.5))
    R.text(0.04, 0.985, f'FURNITURE LAYOUT — VASTU VARIANT {"TBLR".index(north) + 1} / 4', fontsize=15, fontweight='bold', color='#1d2b4f', va='top')
    R.text(0.04, 0.962, f'USE THIS SHEET IF NORTH IS AT THE {SIDE_WORD[north]} OF THE DRAWING', fontsize=11.5, color='#b3261e', fontweight='bold', va='top')
    R.text(0.04, 0.945, '4 BHK duplex · Unit A (left) and Unit B (mirror) · both levels', fontsize=10, color='#444', va='top')
    sub = R.inset_axes([0.70, 0.905, 0.26, 0.085]); sub.set_xlim(-1.6, 1.6); sub.set_ylim(-1.6, 1.6); sub.set_aspect('equal'); sub.axis('off')
    compass(sub, north, 0, 0, 1.0)
    rows = []
    ra, rb = choice_rows(c, A), choice_rows(Lo.mirror_compass(c), B)
    for (n, va, ga), (_, vb, gb) in zip(ra, rb):
        rows.append((n, va, ga, vb, gb))
    y = table(R, 0.04, 0.89, 'FURNITURE — VASTU RESOLUTION (strict)', ['Item', 'Unit A', '', 'Unit B', ''],
              rows, [0.22, 0.25, 0.115, 0.25, 0.115], fs=7.6)
    y = y - 0.01
    aa, ab = Lo.vastu_audit(c), Lo.vastu_audit(Lo.mirror_compass(c))
    rows = [(n, za, ga, zb, gb) for (n, za, ga), (_, zb, gb) in zip(aa, ab)]
    y = table(R, 0.04, y, 'BUILDER PLAN — VASTU AUDIT (fixed by structure)', ['Element', 'Unit A zone', '', 'Unit B zone', ''],
              rows, [0.22, 0.17, 0.195, 0.17, 0.195], fs=7.6)
    notes = []
    for L, u in ((A, 'A'), (B, 'B')):
        for k, v in L.choices.items():
            if 'head' in k and L.c[v] == 'W':
                notes.append(f'Unit {u}: {k.replace(" bed head", "")} — the S and E walls are glazing / the balcony route, so the head goes West (accepted fallback; never North).')
        if L.choices['Sofa faces'] not in ('N', 'E'):
            notes.append(f'Unit {u}: the sofa faces {L.choices["Sofa faces"]} — the TV stays on the solid party wall, away from the pooja. Put the owner\'s armchair facing N/E.')
        for n in L.notes:
            notes.append(f'Unit {u}: {n}')
    for n, za, ga, zb, gb in rows:
        if 'NOT IDEAL' in (ga, gb):
            notes.append(f'{n}: builder location is not ideal in Vastu terms and cannot be moved by furniture — discuss with client.')
    R.text(0.04, y, 'NOTES FOR THIS ORIENTATION', fontsize=11, fontweight='bold', color='#5b3a7a', va='top'); y -= 0.022
    import textwrap
    for n in dict.fromkeys(notes):
        for i, line in enumerate(textwrap.wrap(n, 66)):
            R.text(0.05 if i == 0 else 0.065, y, ('• ' if i == 0 else '') + line, fontsize=8.2, va='top', color='#222'); y -= 0.0148
        y -= 0.003
    y -= 0.01
    R.text(0.04, y, 'COMMON TO ALL VARIANTS', fontsize=11, fontweight='bold', color='#5b3a7a', va='top'); y -= 0.022
    common = ['Every layout passes an automatic check: no item overlaps another, every door swing is clear, and paths stay open.',
              'Beds: Indian King 72x78" (1830x1980) and Queen 60x78" (1525x1980); at least 750 mm clear on access sides.',
              'Kitchen: 850 mm counter height, 600 mm base / 350 mm wall units, hob kept 750 mm or more from the sink, chimney on a solid wall.',
              'Wardrobes are 600 deep with loft, never inside a door swing. Shutters are hinged where the passage is 900 mm or more.',
              'The parents\' room is on the lower level (no stairs); its toilet gets grab bars and an anti-skid floor.',
              'A jaali screen at the entry hides the dining room from the main door. The shoe cabinet is never next to the pooja.']
    for n in common:
        for i, line in enumerate(textwrap.wrap(n, 66)):
            R.text(0.05 if i == 0 else 0.065, y, ('• ' if i == 0 else '') + line, fontsize=8.2, va='top', color='#222'); y -= 0.0148
        y -= 0.003
    R.text(0.04, 0.05, 'LEGEND', fontsize=10, fontweight='bold', color='#5b3a7a')
    R.text(0.04, 0.02, 'Furniture: brown · Sanitary / AC / curtains: blue · Walls: black · Doors: red · Dashed: wall cabinets, AC (high level), dryer\n'
           'Drawing approx. 1:56 at A1 — N.T.S.; verify all sizes on site.  Project / client: ______________   Date: 19-11-26', fontsize=7.6, color='#444')
    pdf.savefig(fig); fig.savefig(f'Vastu_Variant_{"TBLR".index(north) + 1}_North-{SIDE_WORD[north].title()}.png', dpi=60)
    plt.close(fig)


SCHEDULE = [
    ('Living', 'Sofa, 3-seater', '2200 x 950', 1, 'Fabric, solid wood frame'),
    ('Living', 'Accent armchairs', '800 x 800', 2, 'Only 1 in the P3 variant'),
    ('Living', 'Coffee table', '1100 x 600', 1, 'Veneer / stone top'),
    ('Living', 'TV unit + back panel', '2100-2600 x 400', 1, 'For a 65" TV, viewing distance 2.6-2.9 m'),
    ('Living', 'Console OR floating TV partition', '1600 x 400 / 1900 x 400 full ht', 1, 'The partition is used where the party wall faces S/W'),
    ('Living', 'Rug', '2200 x 2300-2600', 1, ''),
    ('Entry', 'Shoe cabinet + mirror', '1100 x 400 (or 450 tall)', 1, 'Ventilated shutters'),
    ('Entry', 'CNC jaali screen', '1100 x 100, full height', 1, 'MDF / metal, optional'),
    ('Dining', 'Dining table, 6-seater', '1800 x 900', 1, '600 mm per diner'),
    ('Dining', 'Dining chairs', '450 x 450', 6, ''),
    ('Dining', 'Crockery / display unit', '1270-2570 x 450', 1, 'Length depends on pooja variant'),
    ('Pooja', 'Pooja unit', '1200 x 450', 1, 'NE corner; devotee faces E or N'),
    ('Kitchen', 'Base counter (L / parallel)', '600 deep, 850 high', '~6.5 rm', 'Quartz top, BWP ply carcass'),
    ('Kitchen', 'Wall units', '350 deep', '~3 rm', 'Not over the window'),
    ('Kitchen', 'Hob 4-burner + chimney', '860 x 510 / 900', 1, 'Island chimney only in the "hob on peninsula" variant'),
    ('Kitchen', 'Double-bowl sink + dishwasher', '1000 x 500 / 600', 1, 'Sink under the window'),
    ('Kitchen', 'Double-door fridge + tall pantry', '650 x 720 + 600 x 600', 1, 'Microwave / OTG in the tall unit'),
    ('Wash', 'Utility counter + sink, W.M., ceiling dryer', '1200 x 600 / 650 x 650', 1, ''),
    ('Balcony', 'Jhula + 2 chairs + table', '1300 x 600 / 650 x 650', 1, 'Hook into the beam; 600 mm swing clearance'),
    ('BR-1 Parents', 'King bed + 2 side tables', '1930 x 2130 / 450 x 450', 1, 'Low bed height for elders (450 mm)'),
    ('BR-1 Parents', 'Wardrobe + loft', '3220-3420 x 600', 1, 'Hinged shutters'),
    ('BR-1 Parents', 'Dresser + stool, recliner', '1200 x 450 / 750 x 750', 1, ''),
    ('BR-2 Son/Guest', 'King bed + 2 side tables', '1930 x 2130', 1, ''),
    ('BR-2 Son/Guest', 'Wardrobe + loft', '3220-3320 x 600', 1, ''),
    ('BR-2 Son/Guest', 'Study / dresser + chair, armchair', '1400 x 450', 1, ''),
    ('BR-3 Kids', 'Queen bed + 2 side tables', '1625 x 2130', 1, 'Storage bed (hydraulic)'),
    ('BR-3 Kids', 'Wardrobe + loft', '2595-2600 x 600', 1, ''),
    ('BR-3 Kids', 'Study table + chair, bookshelf', '1200 x 600 / 600 x 300', 1, 'Roller blind at the study window'),
    ('BR-4 Master', 'King bed + 2 side tables', '1930 x 2130', 1, 'Upholstered headboard'),
    ('BR-4 Master', 'Wardrobes (dress + room)', '1845 + 1900 (or 1625) x 600', 2, 'Walk-through dress area'),
    ('BR-4 Master', 'TV unit / bed-end bench, armchair', '1800 x 400 / 1400 x 450', 1, 'Depends on bed variant'),
    ('Upper lobby', 'Low bookshelf + 2 armchairs', '1630 x 350 / 700 x 700', 1, 'Reading nook'),
    ('All bedrooms', 'Split AC (IDU)', '1000 x 230', 5, 'Living gets a 2 T unit; dining and bedrooms 1.5 T'),
    ('All', 'Curtains / blinds', '-', '-', 'Sheer + blackout in bedrooms'),
]
STANDARDS = [
    ('Mattress, Indian King', '72" x 78"  (1830 x 1980 mm)'), ('Mattress, Indian Queen', '60" x 78"  (1525 x 1980 mm)'),
    ('Bed frame allowance', '+100 width, +150 length (headboard)'), ('Passage beside bed / foot', '750 min, 900+ preferred'),
    ('Wardrobe depth / front clearance', '600 / 900 for hinged shutters'), ('Kitchen counter height / depth', '850 / 600 mm'),
    ('Kitchen wall unit depth', '300-350 mm; 450-600 above the counter'), ('Kitchen aisle', '1000-1200 mm'),
    ('Hob to sink separation', '750 mm min (Vastu: fire and water apart)'), ('Dining space per person', '600 mm; 750-900 behind chairs'),
    ('TV viewing distance', '1.5-2.5 x screen diagonal'), ('Pooja standing space', '850 mm min in front of the unit'),
]
VASTU = [
    ('Pooja', 'North-East corner; deity faces W (devotee faces E) or deity faces S (devotee faces N)'),
    ('Cooking', 'Cook faces East; hob towards the South-East (Agni)'),
    ('Bed head', 'South best, East good; West only as a fallback; never North'),
    ('Master bedroom', 'South-West zone preferred (shown in the audit)'),
    ('Heavy storage', 'On South / West walls where the layout allows'),
    ('Main door', 'North / East facing best (shown in the audit)'),
    ('Toilets', 'Avoid NE, SW and the centre (builder element: audited only)'),
]
SOURCES = [
    'Wakefit — Indian mattress & bed size guide: wakefit.co/blog/indian-mattress-bed-size-guide/',
    'Sealy India — Mattress size chart: sealy.in/pages/mattress-sizes',
    'Sunday Rest — King vs Queen in India: sundayrest.com/blogs/sunday/difference-between-king-and-queen-size-bed-in-india',
    'Design Cafe — Standard kitchen dimensions in India: designcafe.com/blog/modular-kitchen-interiors/standard-kitchen-dimensions/',
    'Asian Paints — Standard kitchen cabinet sizes: asianpaints.com/.../standard-kitchen-cabinet-sizes.html',
    'Casagrand — Vaastu compliance for interiors: casagrand.co.in/blog/tips-to-ensure-vaastu-shastra-compliance-for-the-interiors-of-your-home/',
    'Rustomjee — Vastu for bedroom tips: rustomjee.com/blog/essential-vastu-for-bedroom-tips',
    'Housing.com — Vastu tips for a peaceful bedroom: housing.com/news/vastu-tips-peaceful-bedroom/',
]


def schedule_sheet(pdf):
    fig = plt.figure(figsize=(33.11, 23.39)); ax = fig.add_axes([0, 0, 1, 1]); ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.02, 0.975, 'FURNITURE SCHEDULE · DESIGN STANDARDS · VASTU RULES — 4 BHK DUPLEX', fontsize=20, fontweight='bold', color='#1d2b4f', va='top')
    ax.text(0.02, 0.952, 'Sheet 5 / 5 — applies to every Vastu variant (sheets 1-4). Quantities are per unit.', fontsize=11, color='#444', va='top')
    y = table(ax, 0.02, 0.93, 'FURNITURE SCHEDULE (per unit)', ['Room', 'Item', 'Size (mm)', 'Qty', 'Notes / spec'],
              [(a, b, c, str(d), e) for a, b, c, d, e in SCHEDULE], [0.07, 0.16, 0.12, 0.03, 0.17], fs=9, rowh=0.0215)
    y2 = table(ax, 0.62, 0.93, 'DESIGN STANDARDS USED', ['Parameter', 'Value'], STANDARDS, [0.15, 0.2], fs=9.5, rowh=0.022)
    y2 = table(ax, 0.62, y2 - 0.01, 'VASTU RULES APPLIED (strict mode)', ['Element', 'Rule'], VASTU, [0.09, 0.27], fs=9.5, rowh=0.022)
    ax.text(0.62, y2 - 0.01, 'HOW TO USE THIS SET', fontsize=11, fontweight='bold', color='#5b3a7a', va='top')
    howto = ['1. Find North on site (compass app or the society\'s site plan).',
             '2. Pick the sheet whose heading matches: North at the top / bottom / left / right of the drawing.',
             '3. Unit A and Unit B on that sheet are each resolved separately (they are mirror images).',
             '4. The matching DXF has the same furniture on layers A-FURN-*, ready for working drawings.',
             '5. The "builder plan audit" table shows Vastu issues that furniture cannot fix.']
    yy = y2 - 0.035
    for h in howto:
        ax.text(0.625, yy, h, fontsize=9.5, va='top'); yy -= 0.02
    ax.text(0.62, yy - 0.01, 'RESEARCH SOURCES', fontsize=11, fontweight='bold', color='#5b3a7a', va='top'); yy -= 0.035
    for s in SOURCES:
        ax.text(0.625, yy, '• ' + s, fontsize=8.5, va='top', color='#333'); yy -= 0.017
    ax.add_patch(Rectangle((0.005, 0.005), 0.99, 0.99, fc='none', ec='#5b3a7a', lw=1.5))
    pdf.savefig(fig); fig.savefig('Sheet5_Schedule_Standards.png', dpi=50); plt.close(fig)


def export_dxf(north, A, B):
    import ezdxf
    doc = ezdxf.new('R2013', setup=True); doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()
    cols = {'A-FURN': 30, 'A-FURN-BED': 32, 'A-FURN-SOFA': 34, 'A-FURN-WARD': 42, 'A-FURN-KIT': 8, 'A-FURN-RUG': 211,
            'A-FURN-PLANT': 94, 'A-FURN-POOJA': 40, 'A-FURN-SAN': 150, 'A-FURN-AC': 140, 'A-FURN-CURTAIN': 150,
            'A-FURN-TEXT': 7, 'A-ROOM-TEXT': 5}
    for n, c in cols.items(): doc.layers.add(n, color=c)
    for k, L, v in P:
        if 'FIX FURNITURE' in L: continue
        if L not in doc.layers: doc.layers.add(L, color=7 if 'WALL' in L.upper() else 8)
        msp.add_lwpolyline(v, dxfattribs={'layer': L})
    for e in DB['entities']:
        if e['type'] in ('MTEXT', 'TEXT') and 'SECLINE' not in e.get('layer', ''):
            p = e.get('insertionPoint') or e.get('startPoint')
            if abs(p['x']) > 200000: continue
            t = re.sub(r'\\[A-Za-z][^;]*;', '', e.get('text', '')).replace('{', '').replace('}', '').replace('\\P', ' ')
            L = e.get('layer', '0')
            if L not in doc.layers: doc.layers.add(L)
            msp.add_text(t, height=min(e.get('textHeight', 150) or 150, 200), dxfattribs={'layer': L}).set_placement((p['x'], p['y']))
    for e in prims_of(A, False) + prims_of(B, True):
        ls = 'DASHED' if e.get('ls') == '--' else 'CONTINUOUS'
        if e['kind'] == 'poly':
            msp.add_lwpolyline(e['pts'], close=e['closed'], dxfattribs={'layer': e['layer'], 'linetype': ls})
        elif e['kind'] == 'circle' and e['r'] > 1:
            msp.add_circle(e['c'], e['r'], dxfattribs={'layer': e['layer']})
        elif e['kind'] == 'text' and e['s']:
            for i, line in enumerate(e['s'].split('\n')):
                msp.add_text(line, height=e['h'] * 0.8, dxfattribs={'layer': e['layer']}).set_placement(
                    (e['p'][0], e['p'][1] - i * e['h'] * 1.1), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    doc.saveas(f'Furniture_Layout_Variant{"TBLR".index(north) + 1}_North-{SIDE_WORD[north].title()}.dxf')


if __name__ == '__main__':
    with PdfPages('Furniture_Layout_4BHK_Duplex_Vastu_Set.pdf') as pdf:
        for north in 'TBLR':
            c, A, B = layout_pair(north)
            orientation_sheet(pdf, north, c, A, B)
            export_dxf(north, A, B)
            print('sheet', north, 'ok')
        schedule_sheet(pdf)
    print('done')
