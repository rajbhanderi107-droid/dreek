import json, re, sys
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle
import furniture as FU

SCR = sys.argv[1]  # scratch dir with prims.json / db.json
P = json.load(open(f'{SCR}/prims.json'))
DB = json.load(open(f'{SCR}/db.json'))
SKIP = ('FIX FURNITURE', 'DIM', 'SECLINE', 'NOTES')

def style(L):
    U = L.upper()
    if 'WALL' in U and 'LOW' not in U: return '#111', 1.1, 5
    if 'COLUMN' in U: return '#111', 1.1, 5
    if 'WINDOW' in U: return '#1f5fbf', 0.5, 5
    if 'DOOR' in U: return '#8b1a1a', 0.5, 5
    if 'SANITORY' in U: return '#555', 0.35, 4
    if 'STAIR' in U or U == 'STAIR': return '#666', 0.35, 4
    if 'RAILING' in U or 'LOW HT' in U: return '#444', 0.5, 4
    if U.startswith('B-'): return '#c9c9c9', 0.25, 1
    return '#bdbdbd', 0.25, 1

def draw(ax, box, rooms, title):
    x0, x1, y0, y1 = box
    for (a, b, c, d), col in rooms:
        ax.add_patch(Rectangle((a, b), c - a, d - b, fc=col, ec='none', zorder=0))
    for k, L, v in P:
        if any(s in L for s in SKIP): continue
        if not any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in v): continue
        c, lw, z = style(L)
        ax.plot([p[0] for p in v], [p[1] for p in v], color=c, lw=lw, zorder=z, solid_capstyle='butt')
    for e in FU.F:
        if e['kind'] == 'poly':
            pts = e['pts']
            if not any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in pts): continue
            if e['closed']:
                ax.add_patch(Polygon(pts, closed=True, fc=e['fill'] or 'none', ec='#6b4a2b' if 'SAN' not in e['layer'] else '#2a6fa8', lw=e['lw'], ls=e['ls'], zorder=3))
            else:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], color='#6b4a2b' if 'SAN' not in e['layer'] else '#2a6fa8', lw=e['lw'], ls=e['ls'], zorder=3)
        elif e['kind'] == 'circle':
            c = e['c']
            if x0 <= c[0] <= x1 and y0 <= c[1] <= y1 and e['r'] > 1:
                ax.add_patch(Circle(c, e['r'], fc=e['fill'] or 'none', ec='#6b4a2b', lw=e['lw'], zorder=3.5))
        elif e['kind'] == 'text':
            p = e['p']
            if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
                ax.text(p[0], p[1], e['s'], fontsize=e['h'] / 21, ha='center', va='center', color=e['color'],
                        fontweight='bold' if e['bold'] else 'normal', zorder=6, linespacing=1.05)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title, fontsize=13, fontweight='bold', color='#1d2b4f', loc='left', pad=6)

fig = plt.figure(figsize=(23.4, 16.5))   # A2 landscape
axL = fig.add_axes([0.01, 0.06, 0.40, 0.88])
axU = fig.add_axes([0.41, 0.06, 0.40, 0.88])
draw(axL, (3000, 16200, 2600, 17500), FU.LOWER_ROOMS, 'LOWER LEVEL  (living · dining · kitchen · parents bedroom)')
draw(axU, (41900, 55100, 2600, 17500), FU.UPPER_ROOMS, 'UPPER LEVEL  (master · kids · son/guest bedroom)')
# main door arrow
axL.annotate('MAIN\nENTRY', xy=(9100, 9300), xytext=(9100, 8300), ha='center', fontsize=8, fontweight='bold', color='#8b1a1a',
             arrowprops=dict(arrowstyle='->', color='#8b1a1a', lw=1.2), zorder=7)
for ax, x in ((axL, 3200), (axU, 42100)):
    ax.plot([x, x + 1000], [2850, 2850], 'k', lw=2); ax.plot([x, x + 2000], [2850, 2850], 'k', lw=0.6)
    ax.text(x, 2700, '0', fontsize=6, ha='center'); ax.text(x + 1000, 2700, '1m', fontsize=6, ha='center'); ax.text(x + 2000, 2700, '2m', fontsize=6, ha='center')

# title block
tb = fig.add_axes([0.815, 0.06, 0.175, 0.88]); tb.axis('off'); tb.set_xlim(0, 1); tb.set_ylim(0, 1)
tb.add_patch(Rectangle((0, 0), 1, 1, fc='none', ec='#5b3a7a', lw=1.2))
y = 0.965
def blk(head, body, gap=0.012, fs=7.4):
    global y
    tb.text(0.05, y, head, fontsize=10, fontweight='bold', color='#5b3a7a', va='top'); y -= 0.024
    tb.text(0.06, y, body, fontsize=fs, va='top', linespacing=1.35, color='#222'); y -= (body.count('\n') + 1) * 0.0135 + gap
    tb.plot([0.03, 0.97], [y + 0.004, y + 0.004], color='#ccc', lw=0.6)
blk('DRAWING', 'FURNITURE LAYOUT\n4 BHK DUPLEX – UNIT A\n(Unit B identical, mirrored)')
blk('PROJECT / CLIENT', '______________________\n______________________')
blk('DATE / SCALE', '19-11-26        N.T.S. (1:75 at A2)')
blk('ZONING LOGIC',
    '• Lower level = public + elders:\n  living, dining, kitchen,\n  parents bedroom (no stairs)\n'
    '• Upper level = private:\n  master, kids, son/guest\n'
    '• Main door opens to dining;\n  living kept away from entry\n  for privacy, TV on solid\n  party wall (no glare)')
blk('KEY DECISIONS',
    '• Hob on solid wall (chimney),\n  sink under window, fridge +\n  tall pantry form a half-wall\n  between kitchen & dining\n'
    '• Work triangle ≈ 6.9 m\n'
    '• Pooja unit on dining wall,\n  ~900 mm clear in front\n'
    '• 6-seater dining, min 600 mm\n  clear around chairs\n'
    '• Wardrobes on walls with no\n  door swing; 1.2–1.36 m clear\n  at bed foot in every room\n'
    '• Kids room: study under\n  window + bookshelf\n'
    '• Master: walk-thru wardrobe\n  in dress area, TV on toilet\n  wall, armchair by window\n'
    '• Balcony jhula + sit-out;\n  wash area: W.M. + utility\n  sink + ceiling dryer')
blk('VERIFY ON SITE',
    '• North direction not in CAD –\n  confirm before fixing pooja\n  & bed head (Vastu)\n'
    '• Ceiling hook for jhula on\n  beam\n• Kitchen open edge: optional\n  fluted-glass slider')
tb.text(0.05, 0.02, 'Furniture: brown  |  Walls: black\nWindows: blue  |  Doors: red', fontsize=7, color='#555')
fig.savefig('Furniture_Layout_4BHK_Duplex.pdf'); fig.savefig('Furniture_Layout_4BHK_Duplex.png', dpi=110)
print('saved')
