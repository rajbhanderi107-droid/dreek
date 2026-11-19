"""Furniture layout for the 4BHK duplex (Unit A = left unit; Unit B is its mirror).
All coordinates are in mm, in the original DWG coordinate system."""
import math

F = []  # list of primitives: dict(kind, layer, ...)

def poly(pts, layer, fill=None, closed=True, lw=0.5, ls='-'):
    F.append(dict(kind='poly', pts=[tuple(p) for p in pts], layer=layer, fill=fill, closed=closed, lw=lw, ls=ls))
def circ(c, r, layer, fill=None, lw=0.5):
    F.append(dict(kind='circle', c=tuple(c), r=r, layer=layer, fill=fill, lw=lw))
def text(p, s, h=110, layer='A-ANNO', bold=False, color='#333'):
    F.append(dict(kind='text', p=tuple(p), s=s, h=h, layer=layer, bold=bold, color=color))

class Frame:
    """Local frame on a rectangle: u along the back wall, v from back wall (0) to front (D)."""
    def __init__(self, x0, y0, x1, y1, front):
        self.x0, self.y0, self.x1, self.y1, self.f = x0, y0, x1, y1, front
        self.W = (x1 - x0) if front in 'NS' else (y1 - y0)
        self.D = (y1 - y0) if front in 'NS' else (x1 - x0)
    def t(self, u, v):
        f = self.f
        if f == 'S': return (self.x0 + u, self.y1 - v)
        if f == 'N': return (self.x0 + u, self.y0 + v)
        if f == 'E': return (self.x0 + v, self.y0 + u)
        return (self.x1 - v, self.y0 + u)
    def rect(self, u0, v0, u1, v1, layer, fill=None, lw=0.5, ls='-'):
        poly([self.t(u0, v0), self.t(u1, v0), self.t(u1, v1), self.t(u0, v1)], layer, fill, True, lw, ls)
    def line(self, u0, v0, u1, v1, layer, lw=0.4, ls='-'):
        poly([self.t(u0, v0), self.t(u1, v1)], layer, None, False, lw, ls)
    def circ(self, u, v, r, layer, fill=None, lw=0.4):
        circ(self.t(u, v), r, layer, fill, lw)
    def arc(self, u, v, r, a0, a1, layer, n=16, lw=0.4):
        pts = [self.t(u + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), v + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        poly(pts, layer, None, False, lw)

WOOD = '#efe0c8'; SOFT = '#e6ddd0'; BED = '#f6f1e8'; LINEN = '#ffffff'; STONE = '#e3e3e0'; GREEN = '#cfe3c4'; METAL = '#dfe4ea'

# ---------------------------------------------------------------- items
def bed(x0, y0, x1, y1, head):
    """head = side of the headboard wall ('W','E','N','S'); the bed faces away from it."""
    front = {'W': 'E', 'E': 'W', 'N': 'S', 'S': 'N'}[head]
    f = Frame(x0, y0, x1, y1, front); W, D = f.W, f.D
    f.rect(0, 0, W, D, 'A-FURN-BED', BED, 0.6)
    f.rect(0, 0, W, 90, 'A-FURN-BED', WOOD, 0.6)                    # headboard
    f.rect(40, 90, W - 40, D - 40, 'A-FURN-BED', LINEN, 0.4)         # mattress
    pw = (W - 80 - 3 * 60) / 2
    for i in range(2):
        u = 40 + 60 + i * (pw + 60)
        f.rect(u, 150, u + pw, 520, 'A-FURN-BED', '#f2ece2', 0.4)  # pillows
    f.line(40, D * 0.45, W - 40, D * 0.45, 'A-FURN-BED', 0.4)      # duvet fold
    f.line(W - 40, D * 0.45, W - 380, D * 0.45 + 340, 'A-FURN-BED', 0.3)
    f.line(W - 380, D * 0.45 + 340, W - 40, D * 0.45 + 340, 'A-FURN-BED', 0.3)
    f.rect(40, D * 0.72, W - 40, D * 0.72 + 260, 'A-FURN-BED', '#e9dcc6', 0.3)  # bed runner

def side_table(x0, y0, s=450):
    poly([(x0, y0), (x0 + s, y0), (x0 + s, y0 + s), (x0, y0 + s)], 'A-FURN', WOOD)
    circ((x0 + s / 2, y0 + s / 2), s * 0.28, 'A-FURN', '#fff', 0.3)
    circ((x0 + s / 2, y0 + s / 2), s * 0.10, 'A-FURN', None, 0.3)

def wardrobe(x0, y0, x1, y1, front, label='WARDROBE', loft=True):
    f = Frame(x0, y0, x1, y1, front); W, D = f.W, f.D
    f.rect(0, 0, W, D, 'A-FURN-WARD', WOOD, 0.6)
    f.line(0, D - 25, W, D - 25, 'A-FURN-WARD', 0.3)
    n = max(2, round(W / 550))
    for i in range(1, n): f.line(W * i / n, D - 25, W * i / n, D, 'A-FURN-WARD', 0.3)
    f.line(30, D * 0.5, W - 30, D * 0.5, 'A-FURN-WARD', 0.3, '--')   # hanging rod
    for i in range(int(W / 160)):
        u = 80 + i * 160
        if u < W - 60: f.line(u - 60, D * 0.5 - 150, u + 60, D * 0.5 + 150, 'A-FURN-WARD', 0.2)
    cu, cv = W / 2, D / 2
    text(f.t(cu, cv + 40), label + (' + LOFT' if loft else ''), 70, 'A-FURN-TEXT')

def sofa(x0, y0, x1, y1, front, seats=3):
    f = Frame(x0, y0, x1, y1, front); W, D = f.W, f.D
    f.rect(0, 0, W, D, 'A-FURN-SOFA', SOFT, 0.6)
    f.rect(150, 0, W - 150, 220, 'A-FURN-SOFA', '#d9cdbd', 0.4)     # back
    f.rect(0, 0, 150, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    f.rect(W - 150, 0, W, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    cw = (W - 300) / seats
    for i in range(seats):
        f.rect(150 + i * cw + 15, 235, 150 + (i + 1) * cw - 15, D - 25, 'A-FURN-SOFA', '#efe7dc', 0.35)
    f.rect(170, 230, 370, 330, 'A-FURN-SOFA', '#b9a58a', 0.3)       # cushion
    f.rect(W - 370, 230, W - 170, 330, 'A-FURN-SOFA', '#b9a58a', 0.3)

def armchair(x0, y0, x1, y1, front):
    f = Frame(x0, y0, x1, y1, front); W, D = f.W, f.D
    f.rect(0, 0, W, D, 'A-FURN-SOFA', SOFT, 0.6)
    f.rect(110, 0, W - 110, 180, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    f.rect(0, 0, 110, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    f.rect(W - 110, 0, W, D, 'A-FURN-SOFA', '#d9cdbd', 0.4)
    f.rect(125, 195, W - 125, D - 25, 'A-FURN-SOFA', '#efe7dc', 0.35)

def chair(cx, cy, facing, s=450):
    """dining chair centred at (cx, cy); facing = direction the sitter looks."""
    x0, y0 = cx - s / 2, cy - s / 2
    back = {'E': 'W', 'W': 'E', 'N': 'S', 'S': 'N'}[facing]
    f = Frame(x0, y0, x0 + s, y0 + s, facing)
    f.rect(0, 0, s, s, 'A-FURN', WOOD, 0.5)
    f.rect(0, 0, s, 70, 'A-FURN', '#c9a77d', 0.4)

def rect(x0, y0, x1, y1, layer='A-FURN', fill=WOOD, lw=0.5, ls='-'):
    poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer, fill, True, lw, ls)

def tv_unit(x0, y0, x1, y1, front, tv=1450):
    f = Frame(x0, y0, x1, y1, front); W, D = f.W, f.D
    f.rect(0, 0, W, D, 'A-FURN', WOOD, 0.5)
    f.line(0, D - 30, W, D - 30, 'A-FURN', 0.3)
    f.rect(W / 2 - tv / 2, 40, W / 2 + tv / 2, 100, 'A-FURN', '#555', 0.4)
    text(f.t(W / 2, D * 0.62), 'TV UNIT', 65, 'A-FURN-TEXT')

def rug(x0, y0, x1, y1, fill='#ede4f1'):
    rect(x0, y0, x1, y1, 'A-FURN-RUG', fill, 0.4)
    rect(x0 + 80, y0 + 80, x1 - 80, y1 - 80, 'A-FURN-RUG', None, 0.3, '--')

def plant(cx, cy, r=220):
    circ((cx, cy), r, 'A-FURN-PLANT', GREEN, 0.4)
    for a in range(0, 360, 45):
        poly([(cx, cy), (cx + r * 0.85 * math.cos(math.radians(a)), cy + r * 0.85 * math.sin(math.radians(a)))], 'A-FURN-PLANT', None, False, 0.25)
    circ((cx, cy), r * 0.3, 'A-FURN-PLANT', '#a9c99b', 0.3)

def counter(x0, y0, x1, y1, front):
    f = Frame(x0, y0, x1, y1, front)
    f.rect(0, 0, f.W, f.D, 'A-FURN-KIT', STONE, 0.6)
    f.line(0, f.D - 40, f.W, f.D - 40, 'A-FURN-KIT', 0.25, '--')
    return f

def hob(f, u):
    f.rect(u, 60, u + 860, 540, 'A-FURN-KIT', '#cfd2d6', 0.4)
    for du, dv, r in [(200, 170, 85), (660, 170, 85), (200, 420, 70), (660, 420, 105)]:
        f.circ(u + du, dv, r, 'A-FURN-KIT', None, 0.4)
        f.circ(u + du, dv, r * 0.45, 'A-FURN-KIT', None, 0.25)
    f.rect(u - 20, -10, u + 880, 500, 'A-FURN-KIT', None, 0.3, '--')  # chimney above

def sink(f, u, w=1000):
    f.rect(u, 70, u + w, 520, 'A-FURN-KIT', METAL, 0.4)
    f.rect(u + 40, 110, u + w * 0.55, 480, 'A-FURN-KIT', '#fff', 0.35)
    f.rect(u + w * 0.6, 110, u + w - 40, 480, 'A-FURN-KIT', '#fff', 0.35)
    f.circ(u + w * 0.58, 60, 25, 'A-FURN-KIT', None, 0.3)

def label(x, y, name, w_mm=None, d_mm=None, h=150):
    text((x, y + 70), name, h, 'A-ROOM-TEXT', True, '#1d2b4f')
    if w_mm:
        text((x, y - 120), f"{ft(w_mm)} x {ft(d_mm)}", h * 0.7, 'A-ROOM-TEXT', False, '#4a5a80')

def ft(mm):
    inch = round(mm / 25.4)
    return f"{inch // 12}'{inch % 12}\""

# ================================================================= LOWER FLOOR (Unit A)
# ---- Entrance / foyer
f = Frame(9764, 9541, 10864, 9941, 'N')                  # shoe cabinet on column face, beside main door
f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6); f.line(0, 0, f.W, f.D, 'A-FURN', 0.25); f.line(f.W, 0, 0, f.D, 'A-FURN', 0.25)
text((10314, 10040), 'SHOE CABINET + MIRROR', 60, 'A-FURN-TEXT')

# ---- Dining (6 seater, oriented N-S, next to kitchen)
rect(8050, 11300, 8950, 13100, 'A-FURN', '#e2cba8', 0.7)
rect(8110, 11360, 8890, 13040, 'A-FURN', None, 0.3)
for cy in (11600, 12200, 12800):
    chair(7725, cy, 'E'); chair(9275, cy, 'W')
text((8500, 12200), '6 SEATER\nDINING', 70, 'A-FURN-TEXT')
# pooja unit + crockery on the north wall of dining
f = Frame(7044, 13966, 8244, 14416, 'S')
f.rect(0, 0, f.W, f.D, 'A-FURN-POOJA', '#f7e3b5', 0.7)
f.arc(f.W / 2, 140, 330, 0, 180, 'A-FURN-POOJA', 20, 0.4)
f.circ(f.W / 2, 170, 60, 'A-FURN-POOJA', '#e8a33d', 0.4)
text(f.t(f.W / 2, 340), 'POOJA UNIT', 65, 'A-FURN-TEXT', True, '#8a4b00')
f = Frame(8344, 13966, 9614, 14416, 'S')
f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6); f.line(f.W / 2, 0, f.W / 2, f.D, 'A-FURN', 0.3)
text(f.t(f.W / 2, 250), 'CROCKERY / BAR', 60, 'A-FURN-TEXT')
# ---- Living
rug(12450, 10650, 14650, 13250)
sofa(11450, 10900, 12400, 13000, 'E', 3)
rect(12850, 11400, 13450, 12500, 'A-FURN', '#e2cba8', 0.6); rect(12900, 11450, 13400, 12450, 'A-FURN', None, 0.3)
armchair(12800, 9700, 13600, 10500, 'N'); armchair(13800, 9700, 14600, 10500, 'N')
circ((13700, 10100), 180, 'A-FURN', WOOD)
tv_unit(15109, 10600, 15509, 13200, 'W', 1450)
rect(10950, 11150, 11350, 12750, 'A-FURN', WOOD, 0.5)   # console behind sofa
text((11150, 11950), 'CONSOLE', 55, 'A-FURN-TEXT')
plant(15150, 13750); plant(15150, 9950, 180); circ((11250, 13300), 140, 'A-FURN', '#fff')
# ---- Kitchen  (west counter, hob on solid wall, sink under window, fridge+tall unit as divider)
kw = counter(3919, 11900, 4519, 16361, 'E')           # u along y from 11900
hob(kw, 400); sink(kw, 2050, 1000)
text((4219, 15000), 'RO', 60, 'A-FURN-TEXT')
kn = counter(4519, 15761, 6779, 16361, 'S')
text((5650, 16060), 'PREP COUNTER\nMICROWAVE / OTG', 55, 'A-FURN-TEXT')
rect(6129, 11900, 6779, 12620, 'A-FURN-KIT', '#d9dee6', 0.6); text((6454, 12260), 'DOUBLE DR.\nFRIDGE', 55, 'A-FURN-TEXT')
rect(6179, 12620, 6779, 13250, 'A-FURN-KIT', WOOD, 0.6); text((6479, 12935), 'TALL UNIT\nPANTRY', 55, 'A-FURN-TEXT')
poly([(6779, 13250), (6779, 14416)], 'A-FURN-KIT', None, False, 0.5, '--')
text((7030, 13750), 'OPT. GLASS\nSLIDER', 50, 'A-FURN-TEXT', False, '#777')
# ---- Wash area
f = Frame(7950, 15761, 9149, 16361, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN-KIT', STONE, 0.6)
f.rect(300, 80, 900, 500, 'A-FURN-KIT', METAL, 0.4); text(f.t(f.W / 2, 300), 'UTILITY SINK', 55, 'A-FURN-TEXT')
rect(9199, 15711, 9849, 16361, 'A-FURN-KIT', '#fff', 0.6); circ((9524, 16036), 230, 'A-FURN-KIT', None, 0.4)
text((9524, 15600), 'W.M.', 60, 'A-FURN-TEXT')
rect(7700, 14750, 9700, 15450, 'A-FURN', None, 0.3, '--'); text((8700, 15100), 'CEILING CLOTH DRYER', 55, 'A-FURN-TEXT', False, '#777')
# ---- Balcony (jhula + sit-out)
f = Frame(13900, 15500, 15200, 16100, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN-SOFA', SOFT, 0.6); f.rect(0, 0, f.W, 150, 'A-FURN-SOFA', '#d9cdbd', 0.4)
for u in (100, f.W - 100): f.line(u, -150, u, 0, 'A-FURN', 0.4)
text((14550, 15350), 'JHULA (SWING)', 60, 'A-FURN-TEXT')
armchair(11950, 15500, 12600, 16150, 'S'); armchair(12950, 15500, 13600, 16150, 'S'); circ((12775, 15300), 200, 'A-FURN', WOOD)
for x in (10300, 10800, 11300): plant(x, 16050, 200)
plant(10450, 15000, 160)
# ---- Bedroom-1 (Parents) — ground floor, no stairs to climb
bed(3919, 4400, 5919, 6200, 'W')
side_table(3919, 3950); side_table(3919, 6200)
wardrobe(7284, 3516, 7884, 6736, 'W')
f = Frame(4569, 7236, 5769, 7686, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6); f.rect(100, 0, f.W - 100, 40, 'A-FURN', '#bcd3e6', 0.3)
f.circ(f.W / 2, 650, 170, 'A-FURN', SOFT); text(f.t(f.W / 2, 260), 'DRESSER', 60, 'A-FURN-TEXT')
armchair(6100, 3560, 6850, 4310, 'N'); text((6475, 4450), 'RECLINER', 55, 'A-FURN-TEXT')
# lower toilet: glass shower partition
poly([(6050, 7801), (6050, 8650)], 'A-FURN-SAN', None, False, 0.6)
# under-stair
text((5350, 10150), 'UNDER-STAIR STORAGE\n(below 2nd flight)', 55, 'A-FURN-TEXT', False, '#777')

# room labels — lower
label(13300, 13900, 'LIVING', 8730 - 3800, 4875)
label(8500, 10850, 'DINING', 3300, 4875)
label(5100, 14750, 'KITCHEN', 2860, 4570)
label(8250, 15450, 'WASH', 3005, 1830, 120)
label(12700, 14950, 'BALCONY', 5495, 1830, 120)
label(5450, 5300, 'BEDROOM-1', 3965, 4270)
text((5450, 5000), '(PARENTS)', 90, 'A-ROOM-TEXT', False, '#4a5a80')
label(5450, 9000, 'TOILET', 2135, 1625, 110)

# ================================================================= UPPER FLOOR (Unit A)
# ---- Bedroom-2 (Son / Guest)
bed(42776, 4870, 44776, 6670, 'W')
side_table(42776, 4420); side_table(42776, 6670)
wardrobe(46141, 3736, 46741, 7006, 'W')
f = Frame(43426, 7456, 44826, 7906, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6)
f.circ(f.W / 2, 650, 170, 'A-FURN', SOFT); text(f.t(f.W / 2, 250), 'STUDY / DRESSER', 60, 'A-FURN-TEXT')
armchair(45250, 3740, 45950, 4440, 'N')
# ---- Bedroom-3 (Kids) — queen bed + study under window
bed(42776, 13450, 44776, 14950, 'W')
side_table(42776, 13000); side_table(42776, 14950)
wardrobe(46025, 13886, 46625, 16481, 'W')
f = Frame(44050, 15981, 45250, 16581, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.6)
text(f.t(f.W / 2, 300), 'STUDY TABLE', 60, 'A-FURN-TEXT')
chair(44650, 15700, 'N')
f = Frame(42876, 16281, 43926, 16581, 'S'); f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.5)
for u in range(150, 1050, 150): f.line(u, 0, u, f.D, 'A-FURN', 0.2)
text((43400, 16150), 'BOOKSHELF', 55, 'A-FURN-TEXT')
# ---- Upper lobby — reading nook
f = Frame(46840, 9761, 48470, 10111, 'N'); f.rect(0, 0, f.W, f.D, 'A-FURN', WOOD, 0.5)
for u in range(200, 1630, 200): f.line(u, 0, u, f.D, 'A-FURN', 0.2)
text((47655, 9930), 'LOW BOOKSHELF / DISPLAY', 55, 'A-FURN-TEXT')
armchair(46950, 10250, 47650, 10950, 'N'); armchair(47750, 10250, 48450, 10950, 'N')
circ((47700, 10120), 0.1, 'A-FURN')
# ---- Master Bedroom-4 (largest; dress + bath + balcony)
wardrobe(48735, 9761, 50580, 10361, 'N', 'WALK-THRU WARDROBE')
wardrobe(50630, 9761, 52530, 10361, 'N')
bed(52365, 11300, 54365, 13100, 'E')
side_table(53915, 10850); side_table(53915, 13100)
tv_unit(50630, 12200, 51030, 14000, 'E', 1250)
armchair(53500, 13750, 54250, 14500, 'W'); circ((53300, 14350), 160, 'A-FURN', WOOD)
rug(51300, 11400, 52250, 13000, '#efe4da')
# master balcony
armchair(50900, 15300, 51550, 15950, 'E'); armchair(52150, 15300, 52800, 15950, 'W'); circ((51850, 15625), 220, 'A-FURN', WOOD)
plant(52850, 14950, 160)

label(44350, 6100 - 1000, 'BEDROOM-2', 3965, 4270)
text((44350, 4800), '(SON / GUEST)', 90, 'A-ROOM-TEXT', False, '#4a5a80')
label(45000, 12650 + 1300, 'BEDROOM-3', 3850, 4455)
text((45000, 13650), '(KIDS)', 90, 'A-ROOM-TEXT', False, '#4a5a80')
label(52300, 14150, 'MASTER BED-4', 3735, 4875)
label(49650, 10850, 'DRESS', 1945, 2250, 110)
label(47000, 11500, 'FAMILY LOBBY', 3045, 2250, 110)
label(47650, 14300, 'TOILET', 1830, 4455, 110)
label(49600, 14300, 'TOILET', 1830, 4455, 110)
label(44550, 8850, 'TOILET', 2135, 1625, 110)
label(51850, 16000 - 900, '', None, None, 100)
text((51850, 14950), 'BALCONY', 100, 'A-ROOM-TEXT', True, '#1d2b4f')

# ---------------------------------------------------------------- floor tints (rendering only)
LOWER_ROOMS = [
    ((6894, 9541, 15509, 14416), '#fbf7f0'), ((3919, 11850, 6779, 16361), '#f4f1ec'), ((6894, 14531, 9899, 16361), '#e8f2f8'),
    ((10014, 14531, 15509, 16361), '#eef5ea'), ((3919, 3416, 7884, 7686), '#f8f3ea'), ((4644, 7801, 6779, 9426), '#e8f2f8'),
    ((6894, 7801, 7884, 9541), '#fbf7f0'), ((3919, 9541, 6779, 11850), '#f1f1f1')]
UPPER_ROOMS = [
    ((42776, 3636, 46741, 7906), '#f8f3ea'), ((45750, 8021, 46740, 9646), '#f8f3ea'), ((43500, 8021, 45635, 9646), '#e8f2f8'),
    ((42776, 12126, 46625, 16581), '#eef3f8'), ((46740, 12126, 48570, 16581), '#e8f2f8'), ((48685, 12126, 50515, 16581), '#e8f2f8'),
    ((45525, 9761, 48570, 12011), '#fbf7f0'), ((42776, 9761, 45525, 12011), '#f1f1f1'), ((48685, 9761, 50630, 12011), '#f6efe6'),
    ((50630, 9761, 54365, 14636), '#f6efe6'), ((50630, 14751, 53081, 16176), '#eef5ea')]
